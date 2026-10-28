"""One serialized worker boundary for legacy Sheets contracts.

Single writer process required. No automatic retry of non-idempotent inserts.
"""
import asyncio
import logging
from types import SimpleNamespace
from utils.coastal_applications.__ca_logic import load_content
from utils.coastal_guide.__cg_logic import load_guide_content
from utils.core_features.__constants import CAPTAIN_SERVICE_ACCOUNT, SHEET_DEFAULTS


class SheetsInitializationError(RuntimeError):
    """A sanitized startup failure; never include Google payloads or credential contents."""

SCOPES = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/spreadsheets",
          "https://www.googleapis.com/auth/drive.file", "https://www.googleapis.com/auth/drive"]


class SheetsService:
    def __init__(self, settings, *, client_factory=None):
        self.settings = settings
        self.client_factory = client_factory
        self.lock = asyncio.Lock()
        self.ready = False

    @staticmethod
    def _open(client, settings, kind):
        key = settings.get(f"{kind}_sheet_id")
        if key:
            return client.open_by_key(key)
        return client.open(settings.get(f"{kind}_sheet", SHEET_DEFAULTS[f"{kind}_sheet"]))

    def _connect(self):
        stage = "credentials"
        try:
            if self.client_factory is not None:
                client = self.client_factory()
            else:
                import gspread
                from oauth2client.service_account import ServiceAccountCredentials
                creds = ServiceAccountCredentials.from_json_keyfile_name(self.settings["credentials_path"], SCOPES)
                if creds.service_account_email != CAPTAIN_SERVICE_ACCOUNT:
                    raise SheetsInitializationError("Configure Captain's dedicated service account in the private credentials file.")
                client = gspread.authorize(creds)
            client.set_timeout(30)
            stage = "applications spreadsheet (first worksheet)"
            applications = self._open(client, self.settings, "application").sheet1
            stage = "markers spreadsheet"
            markers_book = self._open(client, self.settings, "markers")
            markers = {}
            for name in ("Overworld", "Nether", "End"):
                stage = f"required markers worksheet {name}"
                markers[name] = markers_book.worksheet(name)
            stage = "required markers worksheet Questions"
            questions = markers_book.worksheet("Questions")
            stage = "application metadata and questions (rows 1 and 2)"
            application_content = load_content(applications)
            for page in application_content.pages:
                if any(not isinstance(label, str) or not label.strip() for _, label in page["questions"]):
                    raise ValueError("Application question labels are missing")
            stage = "POI prompts (Questions B1:B6)"
            poi_content = SimpleNamespace(**{name: questions.acell(f"B{i}").value for i, name in enumerate(
                ("poidesc", "Qtext1", "Qtext2", "Qtext3", "Qtextcolor", "Qmarkertype"), 1)})
            stage = "configured Season 10 guide content"
            guide_content = load_guide_content(self.settings, questions)
            if not guide_content.configured:
                logging.getLogger(__name__).warning("Season 10 guide needs operator-supplied links, question and answer; guide role assignment is unavailable until configured.")
            # Publish only a fully initialized integration. Failed startup never exposes half-ready state.
            self.applications = applications
            self.markers = markers
            self.application_content = application_content
            self.poi_content = poi_content
            self.guide_content = guide_content
            self.ready = True
        except SheetsInitializationError:
            raise
        except Exception:
            raise SheetsInitializationError(f"Unable to initialize {stage}. Check Captain service-account access, selected spreadsheet and required worksheet/ranges.") from None

    async def _run(self, operation):
        async with self.lock:
            # Hold the lock even when caller cancellation occurs: a worker may still be writing.
            task = asyncio.create_task(asyncio.to_thread(operation))
            try:
                return await asyncio.shield(task)
            except asyncio.CancelledError:
                try:
                    await task
                finally:
                    raise

    async def initialize(self):
        def connect_once():
            if not self.ready:
                self._connect()
        await self._run(connect_once)

    @staticmethod
    def _insert(sheet, row, position):
        # Read all IDs rather than assuming the newest row holds the maximum.
        ids = [int(v) for v in sheet.col_values(1)[position - 1:] if str(v).strip().isdigit()]
        entry = max(ids, default=0) + 1
        row = list(row)
        row[0] = entry
        sheet.insert_row(row, position, value_input_option="USER_ENTERED")
        return entry

    async def submit_application(self, row):
        return await self._run(lambda: self._insert(self.applications, row, 3))

    async def submit_poi(self, dimension, row):
        return await self._run(lambda: self._insert(self.markers[dimension], row, 2))

    def _find_row(self, appnumber):
        # Row 1 metadata and row 2 questions are never applicants.
        ids = self.applications.col_values(1)
        matches = [i for i, value in enumerate(ids, 1) if i >= 3 and str(value) == str(appnumber)]
        if len(matches) != 1:
            raise ValueError("Application ID missing or ambiguous")
        return matches[0]

    async def application_record(self, appnumber):
        def read():
            return self.applications.row_values(self._find_row(appnumber))
        return await self._run(read)

    async def decide_application(self, appnumber, status):
        if status not in ("Yes", "No"):
            raise ValueError("Invalid application status")
        def write():
            # Resolve again under lock: an intervening insertion can shift rows.
            self.applications.update_cell(self._find_row(appnumber), 21, status)
        await self._run(write)
