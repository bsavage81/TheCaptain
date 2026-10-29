import hashlib
import json
import time
from datetime import datetime, timezone
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock, Mock

import pytest

from test_captain import Sheet, service, settings, interaction
from utils.coastal_applications import web_portal as web
from utils.coastal_applications.__ca_logic import load_content

SECRET = 'offline-test-secret-32-characters-only'
UID = 123456789012345678


class User:
    id = UID
    display_name = 'Synthetic nickname'
    mention = '<@123456789012345678>'

    def __str__(self):
        return 'synthetic_user'


def test_ticket_signature_expiry_and_unicode():
    user = User()
    user.display_name = 'Synthetic 🌊'
    code = web.issue_ticket(user, SECRET)
    created = datetime.now(timezone.utc).isoformat()
    assert web.verify_ticket(code, SECRET, submitted_at=created)['uid'] == str(UID)
    with pytest.raises(ValueError):
        web.verify_ticket(code+'x', SECRET, submitted_at=created)
    old = web.issue_ticket(user, SECRET, now=int(time.time())-90000)
    with pytest.raises(ValueError):
        web.verify_ticket(old, SECRET, submitted_at=created)
    # A queued application remains valid if collected after ticket expiration.
    issued = int(time.time())-90000
    then = datetime.fromtimestamp(issued+60, timezone.utc).isoformat()
    assert web.verify_ticket(old, SECRET, submitted_at=then)['uid'] == str(UID)


def test_optional_configuration_and_url_validation(monkeypatch):
    for key in ('APPLICATION_WEB_URL', 'APPLICATION_WEB_SECRET', 'APPLICATION_INBOX_ID'):
        monkeypatch.delenv(key, raising=False)
    assert web.portal_config() is None
    monkeypatch.setenv('APPLICATION_WEB_URL', 'https://example.invalid/exec')
    with pytest.raises(ValueError):
        web.portal_config()
    monkeypatch.setenv('APPLICATION_WEB_URL', 'https://script.google.com/macros/s/SYNTHETIC/exec')
    monkeypatch.setenv('APPLICATION_WEB_SECRET', SECRET)
    monkeypatch.setenv('APPLICATION_INBOX_ID', 'inbox')
    assert web.portal_config().inbox == 'inbox'


def test_answers_validate_like_browser():
    data = dict.fromkeys(web.KEYS, 'Synthetic')
    assert web.validate_answers(data)['age'] == 'Synthetic'
    for bad in (' ', 'x'*201, '🌊'*101, None, 10):
        with pytest.raises(ValueError):
            web.validate_answers(dict(data, age=bad))
    assert web.validate_answers(dict(data, age='🌊'*100))['age'] == '🌊'*100


def test_deployment_defaults_need_private_secret(monkeypatch):
    for key in ('APPLICATION_WEB_URL', 'APPLICATION_WEB_SECRET', 'APPLICATION_INBOX_ID'):
        monkeypatch.delenv(key, raising=False)
    assert web.portal_config() is None
    monkeypatch.setenv('APPLICATION_WEB_SECRET', SECRET)
    config = web.portal_config()
    assert config.url == web.DEFAULT_WEB_URL
    assert config.inbox == web.DEFAULT_INBOX_ID
    monkeypatch.setenv('APPLICATION_WEB_SECRET', 'too-short')
    with pytest.raises(ValueError):
        web.portal_config()


def fixture():
    sheets = service()
    headers = ['entryID','Discord Name','Discord Nickname','Discord Long ID'] + [f'Question {key}' for key in web.KEYS] + ['Timestamp','Approved?']
    metadata = ['Coastal Craft','Welcome','Process','References','Thanks','Wait','About','Minecraft','Rules']
    sheets.applications.rows = [metadata, headers]
    sheets.applications.cell = lambda r,c: NS(value=(sheets.applications.rows[r-1]+['']*21)[c-1])
    sheets.applications.spreadsheet_id = 'live-sheet'
    content = load_content(sheets.applications)
    channel = NS(send=AsyncMock(return_value=NS(add_reaction=AsyncMock())))
    guild = NS(get_channel=Mock(return_value=channel), get_role=Mock(return_value=NS(mention='<@&synthetic>')))
    bot = NS(sheets=sheets, settings=settings(), application_content=content,
             get_guild=Mock(return_value=guild), get_user=Mock(return_value=User()), fetch_user=AsyncMock())
    portal = web.WebPortal(bot, NS(secret=SECRET, inbox='inbox'))
    code = web.issue_ticket(User(), SECRET)
    data = web.verify_ticket(code, SECRET, submitted_at=datetime.now(timezone.utc).isoformat())
    raw = [(row+['']*21)[:21] for row in sheets.applications.rows]
    version = web.b64(hashlib.sha256(json.dumps(raw, ensure_ascii=False,separators=(',',':')).encode()).digest())
    answers = dict.fromkeys(web.KEYS, 'Synthetic answer')
    answers['gamertag'] = '=FORMULA()'
    row = [data['nonce'],'queued',datetime.now(timezone.utc).isoformat(),code,json.dumps(answers),version,'','']
    inbox = Sheet([list(web.HEADERS),row])
    def update(*, range_name, values, **kwargs):
        inbox.rows[1][6:8] = values[0]
    inbox.update = update
    sheets.client = NS(open_by_key=Mock(return_value=NS(worksheet=Mock(return_value=inbox))))
    inbox.get_all_values = lambda: [list(r) for r in inbox.rows]
    return portal, sheets, inbox, channel


async def test_real_submission_and_review_preserve_contract_and_raw_text():
    portal, sheets, inbox, channel = fixture()
    await portal.poll()
    assert inbox.rows[1][1] == 'complete'
    assert inbox.rows[1][6] == '1'
    row, position, options = sheets.applications.inserts[0]
    assert len(row) == 20 and position == 3
    assert row[3] == str(UID) and row[4] == '=FORMULA()'
    assert options == {'value_input_option':'RAW'}
    assert channel.send.await_count == 3
    assert channel.send.return_value.add_reaction.await_count == 3
    await portal.poll()
    assert len(sheets.applications.inserts) == 1
    await sheets.decide_application(1,'Yes')
    assert (await sheets.application_record(1))[20] == 'Yes'


async def test_notification_failure_is_saved_without_repeat():
    portal, sheets, inbox, channel = fixture()
    channel.send.side_effect = RuntimeError('synthetic failure')
    await portal.poll()
    assert inbox.rows[1][1] == 'saved_notification_failed'
    assert inbox.rows[1][6] == '1'
    await portal.poll()
    assert len(sheets.applications.inserts) == 1


async def test_uncertain_insert_is_held_for_operator():
    portal, sheets, inbox, channel = fixture()
    sheets.applications.insert_row = Mock(side_effect=TimeoutError('uncertain transport'))
    await portal.poll()
    assert inbox.rows[1][1] == 'needs_attention'
    assert 'write_uncertain' in inbox.rows[1][7]
    await portal.poll()
    assert sheets.applications.insert_row.call_count == 1


async def test_lost_acknowledgement_does_not_retry_insert():
    portal, sheets, inbox, channel = fixture()
    inbox.update = Mock(side_effect=TimeoutError('lost ack'))
    with pytest.raises(TimeoutError):
        await portal.poll()
    assert inbox.rows[1][1] == 'processing'
    await portal.poll()
    assert len(sheets.applications.inserts) == 1


@pytest.mark.parametrize('change', ['signature','version','answers'])
async def test_invalid_inbox_never_writes_database(change):
    portal, sheets, inbox, channel = fixture()
    if change == 'signature':
        inbox.rows[1][3] += 'x'
    elif change == 'version':
        inbox.rows[1][5] = 'changed'
    else:
        inbox.rows[1][4] = '{}'
    await portal.poll()
    assert inbox.rows[1][1] == 'needs_attention'
    assert not sheets.applications.inserts
    channel.send.assert_not_awaited()


async def test_existing_discord_command_kept_when_unconfigured():
    from utils.coastal_applications.__ca_commands import CoastalAppCMD
    portal, sheets, inbox, channel = fixture()
    cog = CoastalAppCMD(portal.bot)
    i = interaction()
    await cog.applycoastal.callback(cog, i)
    assert 'embeds' in i.response.send_message.call_args.kwargs


async def test_web_command_issues_private_code_without_identity_fields():
    from utils.coastal_applications.__ca_commands import CoastalAppCMD
    portal, sheets, inbox, channel = fixture()
    portal.config.url = 'https://script.google.com/macros/s/SYNTHETIC/exec'
    cog = CoastalAppCMD(portal.bot)
    cog.web_portal = portal
    i = interaction()
    i.user = User()
    await cog.applycoastal.callback(cog, i)
    call = i.response.send_message.call_args
    assert call.kwargs['ephemeral'] is True
    i.followup.send.assert_awaited_once()
    followup = i.followup.send.call_args
    assert followup.kwargs == {'ephemeral': True}
    code = followup.args[0]
    assert len(followup.args) == 1 and code == code.strip()
    assert '`' not in code and '\n' not in code and ' ' not in code
    assert code not in call.args[0]
    assert web.verify_ticket(code, SECRET, submitted_at=datetime.now(timezone.utc).isoformat())['uid'] == str(UID)
