"""Read-only archive discovery, paged Sheets reads, and explicit layout adapters."""
from datetime import datetime
import asyncio
import re
from .registry import stable_id

ARCHIVE_ID = "0B43virBKP-AQQk9EX0duN2pjQ1E"
ARCHIVE_RESOURCE_KEY = "0-qlRkq_vdrxrR1FmkpM_qIA"
FOLDER = "application/vnd.google-apps.folder"
SHEET = "application/vnd.google-apps.spreadsheet"


def application_date(value):
    value = str(value or "").strip()
    for fmt in ("%m/%d/%Y %H:%M:%S", "%m/%d/%Y %I:%M:%S %p", "%Y-%m-%d %H:%M:%S", "%m/%d/%Y"):
        try:
            return datetime.strptime(value, fmt).isoformat()
        except ValueError:
            pass
    try:
        return datetime.fromisoformat(value).isoformat() if value else None
    except ValueError:
        return None


def parse_rows(rows, *, season, source, header_row, start_row=1, trusted_ids=False):
    """Only selected identity columns are retained; never import personal answers."""
    if len(rows) < header_row:
        raise ValueError("Header missing")
    headers = [str(v or "").strip().casefold() for v in rows[header_row-1]]
    def column(*labels):
        matches = [i for i, h in enumerate(headers) if h in labels]
        if len(matches) > 1:
            raise ValueError("Ambiguous identity columns")
        return matches[0] if matches else None
    fields = {"gamertag": column("gamertag", "what is your gamertag?"),
              "discord_id": column("discord long id", "discord user id", "discord id"),
              "discord_name": column("discord name", "discord username"),
              "application_date": column("timestamp"), "application_status": column("approved?"),
              "entry": column("entryid")}
    if fields["gamertag"] is None:
        raise ValueError("Unsupported identity layout; configure an audited adapter")
    records = []
    for number, values in enumerate(rows[header_row:], start_row + header_row):
        if not any(str(v or "").strip() for v in values):
            continue
        get = lambda name: str(values[fields[name]] or "").strip() if fields[name] is not None and fields[name] < len(values) else ""
        tag = get("gamertag")
        if not tag:
            continue
        raw_id = get("discord_id")
        discord_id = stable_id(raw_id)
        date = application_date(get("application_date"))
        issues = []
        if raw_id and discord_id is None:
            issues.append("malformed_discord_id")
        if get("application_date") and date is None:
            issues.append("unparsed_date")
        if raw_id and not trusted_ids:
            issues.append("unverified_discord_id")
        # Immutable source entry IDs survive insertions; older forms use content fingerprints.
        reference = f"{source}#entry={get('entry')}" if get("entry") else source
        record = dict(source=reference, season=season, gamertag=tag,
                      discord_id=discord_id, discord_id_verified=bool(discord_id and trusted_ids),
                      discord_name=get("discord_name"), application_date=date,
                      application_date_raw=get("application_date"),
                      application_status={"yes": "approved", "no": "denied"}.get(get("application_status").casefold(), "unknown"),
                      issues=issues)
        # No row numbers in idempotency key: inserting/sorting rows must not duplicate applicants.
        records.append(record)
    return records


class ArchiveDiscovery:
    def __init__(self, sheets, settings):
        self.sheets = sheets
        self.settings = settings
        self._read = lambda operation: operation()

    def _children(self, folder_id, resource_key=None):
        """Existing gspread authenticated session, existing scopes; no new credentials."""
        token = None
        while True:
            params = {"q": f"'{folder_id}' in parents and trashed = false", "pageSize": 100,
                      "fields": "nextPageToken,files(id,name,mimeType,resourceKey)",
                      "supportsAllDrives": True, "includeItemsFromAllDrives": True}
            if token:
                params["pageToken"] = token
            headers = {"X-Goog-Drive-Resource-Keys": f"{folder_id}/{resource_key}"} if resource_key else {}
            response = self._read(lambda: self.sheets.client.http_client.request(
                "get", "https://www.googleapis.com/drive/v3/files", params=params, headers=headers))
            payload = response.json()
            yield from payload.get("files", [])
            token = payload.get("nextPageToken")
            if not token:
                break

    def discover(self):
        records, issues, sources = [], [], []
        seen = set()
        queue = [(ARCHIVE_ID, None, ARCHIVE_RESOURCE_KEY)]
        overrides = self.settings.get("profile_sources", {})
        while queue:
            folder, season, resource_key = queue.pop(0)
            if folder in seen:
                continue
            seen.add(folder)
            try:
                children = list(self._children(folder, resource_key))
            except Exception as error:
                issues.append({"source": folder, "issue": "inaccessible_folder", "error": type(error).__name__})
                continue
            for file in children:
                match = re.search(r"(?:season\s*|coastal\s*)(\d+)", file["name"], re.I)
                number = int(match[1]) if match else season
                if file["mimeType"] == FOLDER:
                    # Follow season roots, avoiding unrelated world-image trees.
                    if match and 3 <= number <= self.settings.get("checkin_season", 10):
                        queue.append((file["id"], number, file.get("resourceKey")))
                    continue
                if number is None or number < 3:
                    continue
                if not any(word in file["name"].casefold() for word in ("application", "members")):
                    continue
                if file["mimeType"] != SHEET:
                    issues.append({"source": file["id"], "issue": "unsupported_file", "type": file["mimeType"]})
                    continue
                sources.append({"id": file["id"], "name": file["name"], "season": number})
                try:
                    book = self._read(lambda: self.sheets.client.open_by_key(file["id"]))
                    option = overrides.get(file["id"], {})
                    sheet = self._read(lambda: book.worksheet(option["worksheet"]) if option.get("worksheet") else book.sheet1)
                    from gspread.utils import rowcol_to_a1
                    last = rowcol_to_a1(1, min(sheet.col_count, 27))[:-1]
                    header_row = option.get("header_row", 4 if number == 3 else 2 if number >= 8 else 1)
                    header = self._read(lambda: sheet.get(f"A{header_row}:{last}{header_row}"))
                    if not header:
                        raise ValueError("Missing header")
                    for start in range(header_row+1, sheet.row_count+1, 200):
                        values = self._read(lambda: sheet.get(f"A{start}:{last}{min(start+199, sheet.row_count)}"))
                        records.extend(parse_rows(header + values, season=option.get("season", number),
                            source=f"https://docs.google.com/spreadsheets/d/{file['id']}/edit#gid={sheet.id}",
                            header_row=1, start_row=start-1,
                            trusted_ids=option.get("trusted_discord_ids", number >= 8)))
                except Exception as error:
                    issues.append({"source": file["id"], "issue": "unreadable_or_unsupported_sheet", "error": type(error).__name__})
        # Current configured applications can be outside the archive.
        try:
            sheet = self.sheets.applications
            if sheet.spreadsheet_id not in {s["id"] for s in sources}:
                from gspread.utils import rowcol_to_a1
                last = rowcol_to_a1(1, min(sheet.col_count, 27))[:-1]
                header = self._read(lambda: sheet.get(f"A2:{last}2"))
                for start in range(3, sheet.row_count+1, 200):
                    values = self._read(lambda: sheet.get(f"A{start}:{last}{min(start+199, sheet.row_count)}"))
                    records.extend(parse_rows(header + values,
                        season=self.settings.get("checkin_season", 10), source=f"https://docs.google.com/spreadsheets/d/{sheet.spreadsheet_id}/edit#gid={sheet.id}",
                        header_row=1, trusted_ids=True))
        except Exception as error:
            issues.append({"source": "configured_current_applications", "issue": "inaccessible", "error": type(error).__name__})
        return {"records": records, "sources": sources, "issues": issues}

    async def run(self):
        # Serialize individual Google requests, letting normal applications/markers run
        # between archive pages. Never hold the integration lock for an entire archive.
        loop = asyncio.get_running_loop()
        self._read = lambda operation: asyncio.run_coroutine_threadsafe(self.sheets._run(operation), loop).result()
        task = asyncio.create_task(asyncio.to_thread(self.discover))
        try:
            return await asyncio.shield(task)
        except asyncio.CancelledError:
            await task
            raise
        finally:
            self._read = lambda operation: operation()
