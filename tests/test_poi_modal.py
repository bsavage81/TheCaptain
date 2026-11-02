from types import SimpleNamespace as NS
from unittest.mock import AsyncMock, Mock

import pytest

from utils.coastal_poi.modal import EndCityClaimModal, POIModal, open_poi_modal


def context():
    notification = NS(send=AsyncMock())
    guild = NS(get_channel=Mock(return_value=notification), get_role=Mock(return_value=NS(id=7, mention="<@&7>")))
    bot = NS(sheets=NS(submit_poi=AsyncMock(return_value=42)), get_guild=Mock(return_value=guild),
             settings={"Coastal": 1, "CoastalMapUpdates": 2, "CoastalOPTeam": 7})
    interaction = NS(user=NS(id=9), response=NS(send_message=AsyncMock(), defer=AsyncMock(), send_modal=AsyncMock()),
                     followup=NS(send=AsyncMock()))
    return bot, interaction, notification


@pytest.mark.parametrize("dimension", ["Overworld", "Nether", "End"])
@pytest.mark.parametrize("kind,category,size", [("base", "Player Bases", 8), ("shop", "Shops", 10),
                                              ("portal", "Portals", 12), ("community", "Community", 10)])
async def test_modal_saves_exact_row_and_private_confirmation(dimension, kind, category, size):
    bot, interaction, notification = context()
    modal = POIModal(bot, 9, dimension, 12, -34, kind)
    assert len(modal.children) == (5 if kind == "base" else 4)
    modal.text1._value = " First "
    modal.text2._value = " NO "
    modal.text3._value = " Third "
    modal.color._value = " #33aaff "
    await modal.on_submit(interaction)
    bot.sheets.submit_poi.assert_awaited_once_with(dimension,
        [None, 12, -34, "-1", "", "", "First", "", "Third", "#33aaff", "#ffffff", "0", "0",
         f"900 {size}px 'Font Awesome 6 Free'", category, ""])
    assert interaction.followup.send.call_args.kwargs["ephemeral"]
    assert category in interaction.followup.send.call_args.args[0]
    assert any(f.name == "Category" and f.value == category for f in notification.send.call_args.kwargs["embed"].fields)
    await modal.on_submit(interaction)
    assert bot.sheets.submit_poi.await_count == 1


async def test_modal_link_and_command_parameters_are_passed_through():
    bot, interaction, _ = context()
    await open_poi_modal(bot, interaction, "Nether", -1, 2, "portal")
    modal = interaction.response.send_modal.call_args.args[0]
    assert (modal.x, modal.z, modal.category) == (-1, 2, "Portals")
    assert "https://fontawesome.com/search?ic=free" in interaction.followup.send.call_args.args[0]
    assert interaction.followup.send.call_args.kwargs["ephemeral"]


@pytest.mark.parametrize("dimension", ["Overworld", "Nether", "End"])
@pytest.mark.parametrize("value,expected", [("", ""), ("0", 0), (" 150 ", 150), ("00025", 25)])
async def test_base_radius_is_numeric_and_in_column_p(dimension, value, expected):
    bot, interaction, notification = context()
    modal = POIModal(bot, 9, dimension, 12, -34, "base")
    modal.text1._value = "Base"
    modal.color._value = "white"
    modal.radius._value = value
    await modal.on_submit(interaction)
    row = bot.sheets.submit_poi.call_args.args[1]
    assert len(row) == 16 and row[14:] == ["Player Bases", expected]
    assert any(f.name == "Base radius" for f in notification.send.call_args.kwargs["embed"].fields)


@pytest.mark.parametrize("value", ["-1", "1.5", "nan", "infinity", "100 blocks", "1e3", "+10"])
async def test_invalid_radius_never_saves(value):
    bot, interaction, notification = context()
    modal = POIModal(bot, 9, "Overworld", 1, 2, "base")
    modal.text1._value = "Base"
    modal.color._value = "white"
    modal.radius._value = value
    await modal.on_submit(interaction)
    bot.sheets.submit_poi.assert_not_awaited()
    notification.send.assert_not_awaited()
    assert "whole number" in interaction.response.send_message.call_args.args[0]


@pytest.mark.parametrize("problem", ["wrong_user", "blank_text", "blank_color"])
async def test_invalid_modal_never_saves(problem):
    bot, interaction, notification = context()
    modal = POIModal(bot, 9, "End", 1, 2, "base")
    modal.text1._value = "Text"
    modal.color._value = "red"
    if problem == "wrong_user":
        interaction.user.id = 10
    elif problem == "blank_text":
        modal.text1._value = "  "
    else:
        modal.color._value = "  "
    await modal.on_submit(interaction)
    bot.sheets.submit_poi.assert_not_awaited()
    notification.send.assert_not_awaited()


@pytest.mark.parametrize("problem", ["save", "notification"])
async def test_failure_does_not_invite_duplicate_submissions(problem):
    bot, interaction, notification = context()
    modal = POIModal(bot, 9, "Overworld", 1, 2, "shop")
    modal.text1._value = "Text"
    modal.color._value = "blue"
    (bot.sheets.submit_poi if problem == "save" else notification.send).side_effect = RuntimeError("synthetic")
    await modal.on_submit(interaction)
    result = interaction.followup.send.call_args.args[0]
    assert ("Contact an OP before retrying" if problem == "save" else "your marker is saved") in result
    await modal.on_submit(interaction)
    assert bot.sheets.submit_poi.await_count == 1


@pytest.mark.parametrize("gamertag", [" Player One ", "No"])
async def test_end_city_claim_modal_preserves_special_marker_row(gamertag):
    bot, interaction, notification = context()
    modal = EndCityClaimModal(bot, 9, -120, 450)
    assert [field.label for field in modal.children] == ["Gamertag", "Text color"]
    assert modal.radius is None
    modal.text1._value = gamertag
    modal.color._value = " green "
    await modal.on_submit(interaction)
    bot.sheets.submit_poi.assert_awaited_once_with("End", [None, -120, 450, "-1", "", "", "\uf06a",
        gamertag.strip(), "", "green", "#ffffff", "0", "0", "900 10px 'Font Awesome 6 Free'", "Community", ""])
    assert "Category: Community" in interaction.followup.send.call_args.args[0]
    assert "radius" not in interaction.followup.send.call_args.args[0]
    await modal.on_submit(interaction)
    assert bot.sheets.submit_poi.await_count == 1


async def test_claim_command_opens_modal_without_chat_questions():
    from utils.coastal_poi.__poi_commands import CoastalPOICMD
    bot, interaction, _ = context()
    cog = CoastalPOICMD(bot)
    await cog.addpoi_endcity_claim.callback(cog, interaction, 10, -20)
    modal = interaction.response.send_modal.call_args.args[0]
    assert isinstance(modal, EndCityClaimModal)
    assert (modal.x, modal.z) == (10, -20)
    bot.sheets.submit_poi.assert_not_awaited()


@pytest.mark.parametrize("problem", ["wrong_user", "blank", "notification"])
async def test_end_city_claim_reuses_modal_safety_checks(problem):
    bot, interaction, notification = context()
    modal = EndCityClaimModal(bot, 9, 1, 2)
    modal.text1._value = "Player"
    modal.color._value = "white"
    if problem == "wrong_user":
        interaction.user.id = 100
    elif problem == "blank":
        modal.text1._value = "  "
    else:
        notification.send.side_effect = RuntimeError("synthetic")
    await modal.on_submit(interaction)
    if problem == "notification":
        assert bot.sheets.submit_poi.await_count == 1
        assert "your marker is saved" in interaction.followup.send.call_args.args[0]
    else:
        bot.sheets.submit_poi.assert_not_awaited()
