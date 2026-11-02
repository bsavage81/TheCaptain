"""Preview by default; explicitly prepare only marker headers and the shared prompt."""
import argparse
import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from utils.coastal_poi.__poi_logic import MARKER_TYPE_QUESTION

HEADERS = ["entryid", "x", "z", "minmapzoom", "image", "imageAnchor", "text1", "text2",
           "text3", "textColor", "strokeColor", "offsetX", "offsetY", "font"]
SEASON10_ID = "11xN9e9hXOsj0oBlrVYHxPFEJJoWAzfBPRR-5bOk4Hy8"


def prepare_categories(book, *, apply=False):
    if book.id != SEASON10_ID:
        raise ValueError("Expected Season 10 marker spreadsheet")
    changes = []
    # Inspect every target before performing any writes. Never overwrite another field.
    for name in ("Overworld", "Nether", "End"):
        sheet = book.worksheet(name)
        headers = sheet.row_values(1)
        if headers[:14] != HEADERS or (len(headers) > 14 and headers[14] not in ("", "category")):
            raise ValueError(f"Unexpected {name} marker schema")
        if len(headers) < 15 or headers[14] != "category":
            changes.append((sheet, "O1", "category"))
    questions = book.worksheet("Questions")
    if questions.acell("B6").value != MARKER_TYPE_QUESTION:
        changes.append((questions, "B6", MARKER_TYPE_QUESTION))
    if apply:
        for sheet, cell, value in changes:
            sheet.update_acell(cell, value)
            if sheet.acell(cell).value != value:
                raise ValueError("Marker setup readback failed")
    return [{"sheet": sheet.title, "cell": cell, "value": value} for sheet, cell, value in changes]


async def main():
    from dotenv import load_dotenv
    from utils.configuration import load_bootstrap, read_database_settings
    from utils.database.__database import make_database
    from utils.integrations.__google_sheets import SheetsService

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    load_dotenv(ROOT / ".env")
    bootstrap = load_bootstrap()
    backend = make_database(bootstrap)
    with backend.connection_context():
        settings = {**bootstrap, **read_database_settings(backend)}
    service = SheetsService(settings)
    await service.initialize()
    def prepare():
        book = service._open(service.client, settings, "markers")
        return prepare_categories(book, apply=args.apply)
    changes = await service._run(prepare)
    print(json.dumps({"applied": args.apply, "changes": changes}, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
