"""One serialized worker boundary for legacy Sheets contracts.

Single writer process required. No automatic retry of non-idempotent inserts.
"""
import asyncio
from types import SimpleNamespace
from utils.coastal_applications.__ca_logic import load_content

SCOPES = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/spreadsheets",
          "https://www.googleapis.com/auth/drive.file", "https://www.googleapis.com/auth/drive"]


class SheetsService:
    def __init__(self, settings, *, client_factory=None):
        self.settings = settings
        self.client_factory = client_factory
        self.lock = asyncio.Lock()
        self.ready = False

    def _connect(self):
        if self.client_factory is not None:
            client = self.client_factory()
        else:
            import gspread
            from oauth2client.service_account import ServiceAccountCredentials
            creds = ServiceAccountCredentials.from_json_keyfile_name(self.settings["credentials_path"], SCOPES)
            client = gspread.authorize(creds)
        self.applications = client.open("CCS9 Realm Application").sheet1
        markers = client.open("Coastal Markers")
        self.markers = {name: markers.worksheet(name) for name in ("Overworld", "Nether", "End")}
        questions = markers.worksheet("Questions")
        self.application_content = load_content(self.applications)
        self.poi_content = SimpleNamespace(**{name: questions.acell(f"B{i}").value for i, name in enumerate(
            ("poidesc", "Qtext1", "Qtext2", "Qtext3", "Qtextcolor", "Qmarkertype"), 1)})
        self.ready = True

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
        if not self.ready:
            await self._run(self._connect)

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
