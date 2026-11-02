import asyncio
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock, Mock

import pytest

from test_captain import interaction, service, settings
from utils.coastal_poi import __poi_logic as logic
from scripts.prepare_marker_categories import HEADERS, SEASON10_ID, prepare_categories


@pytest.mark.parametrize("dimension", ["Overworld", "Nether", "End"])
@pytest.mark.parametrize("answer,category,size", [
    (" BASE ", "Player Bases", 8), ("\tShOp\n", "Shops", 10),
    (" Portal ", "Portals", 12), (" CoMmUnItY ", "Community", 10),
])
async def test_category_row_and_confirmation(dimension, answer, category, size, monkeypatch):
    monkeypatch.setattr(logic.asyncio, "sleep", AsyncMock())
    sheets = service()
    sheets.markers[dimension].rows[0] = HEADERS + ["category"]
    channel = NS(send=AsyncMock())
    updates = NS(send=AsyncMock())
    guild = NS(get_channel=Mock(return_value=updates), get_role=Mock(return_value=NS(mention="staff")))
    user = NS(id=1, name="Synthetic", display_name="Synthetic", discriminator="0")
    answers = iter(["First", "No", "Third", "blue", "unknown", "other", answer])
    async def wait_for(*args, **kwargs):
        return NS(content=next(answers))
    bot = NS(settings=settings(), sheets=sheets, get_guild=Mock(return_value=guild), wait_for=wait_for,
             poi_content=NS(poidesc="Intro", Qtext1="Text1", Qtext2="Text2", Qtext3="Text3", Qtextcolor="Color"))
    i = interaction(); i.user = user; i.channel = channel
    await logic.run_poi(NS(bot=bot), i, 12, -34, getattr(logic, "addpoi_" + dimension.lower()))
    row, position, options = sheets.markers[dimension].inserts[0]
    assert row == [1, 12, -34, "-1", "", "", "First", "", "Third", "blue", "#ffffff", "0", "0",
                   f"900 {size}px 'Font Awesome 6 Free'", category]
    assert position == 2 and options == {"value_input_option": "USER_ENTERED"}
    assert len(sheets.markers[dimension].inserts) == 1
    prompts = [call.args[0] for call in channel.send.call_args_list if call.args]
    assert prompts.count("Unrecognized marker type. " + logic.MARKER_TYPE_QUESTION) == 2
    assert f"Success! Category: {category}" in prompts
    embed = updates.send.call_args.kwargs["embed"]
    assert any(field.name == "Category" and field.value == category for field in embed.fields)


async def test_invalid_type_then_timeout_never_writes():
    channel = NS(send=AsyncMock())
    bot = NS(wait_for=AsyncMock(side_effect=[NS(content="other"), asyncio.TimeoutError()]))
    with pytest.raises(asyncio.TimeoutError):
        await logic.ask_marker_type(bot, channel, NS())
    assert bot.wait_for.await_count == 2


async def test_missing_category_header_prevents_insert():
    sheets = service()
    with pytest.raises(ValueError, match="category header"):
        await sheets.submit_poi("Nether", [None] + [""] * 14)
    assert not sheets.markers["Nether"].inserts


async def test_radius_header_required_and_exact_16_column_insert():
    sheets = service()
    sheet = sheets.markers["Overworld"]
    sheet.rows[0] = HEADERS + ["category"]
    row = [None, 10, -20, "-1", "", "", "Base", "", "", "blue", "#ffffff", "0", "0",
           "900 8px 'Font Awesome 6 Free'", "Player Bases", 150]
    with pytest.raises(ValueError, match="radius header"):
        await sheets.submit_poi("Overworld", row)
    assert not sheet.inserts
    sheet.rows[0].append("radius")
    await sheets.submit_poi("Overworld", row)
    assert sheet.inserts == [([1] + row[1:], 2, {"value_input_option": "USER_ENTERED"})]


def book_fixture():
    sheets = {}
    for name in ("Overworld", "Nether", "End", "Questions"):
        cells = {"O1": "category" if name == "Overworld" else "", "B6": "Old prompt"}
        def update(cell, value, cells=cells):
            cells[cell] = value
        sheets[name] = NS(title=name, row_values=Mock(return_value=HEADERS + [cells["O1"]]),
                          acell=lambda cell, cells=cells: NS(value=cells[cell]), update_acell=Mock(side_effect=update))
    return NS(id=SEASON10_ID, worksheet=sheets.__getitem__), sheets


def test_schema_preparation_is_preview_first_and_changes_only_headers_and_prompt():
    book, sheets = book_fixture()
    preview = prepare_categories(book)
    assert [(change["sheet"], change["cell"]) for change in preview] == [
        ("Nether", "O1"), ("End", "O1"), ("Questions", "B6")]
    for sheet in sheets.values():
        sheet.update_acell.assert_not_called()
    assert prepare_categories(book, apply=True) == preview
    sheets["Overworld"].update_acell.assert_not_called()
    sheets["Nether"].update_acell.assert_called_once_with("O1", "category")
    sheets["End"].update_acell.assert_called_once_with("O1", "category")
    sheets["Questions"].update_acell.assert_called_once_with("B6", logic.MARKER_TYPE_QUESTION)


@pytest.mark.parametrize("problem", ["wrong_book", "occupied_o", "wrong_columns"])
def test_schema_preparation_preflights_every_target_before_writing(problem):
    book, sheets = book_fixture()
    if problem == "wrong_book":
        book.id = "not-season10"
    elif problem == "occupied_o":
        sheets["End"].row_values.return_value = HEADERS + ["unrelated"]
    else:
        sheets["End"].row_values.return_value = ["wrong"] * 14
    with pytest.raises(ValueError):
        prepare_categories(book, apply=True)
    for sheet in sheets.values():
        sheet.update_acell.assert_not_called()


def test_radius_schema_preparation_only_adds_missing_headers():
    book, sheets = book_fixture()
    for sheet in sheets.values():
        sheet.acell = lambda cell: NS(value=logic.MARKER_TYPE_QUESTION)
    sheets["Overworld"].row_values.return_value = HEADERS + ["category", "radius"]
    sheets["Nether"].row_values.return_value = HEADERS + ["category"]
    sheets["End"].row_values.return_value = HEADERS + ["category"]
    assert [(c["sheet"], c["cell"]) for c in prepare_categories(book, include_radius=True)] == [
        ("Nether", "P1"), ("End", "P1")]
    sheets["End"].row_values.return_value = HEADERS + ["category", "unrelated"]
    with pytest.raises(ValueError, match="column P"):
        prepare_categories(book, apply=True, include_radius=True)
    for sheet in sheets.values():
        sheet.update_acell.assert_not_called()
