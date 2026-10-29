"""Opt-in private inbox bridge; no public listener and no second database writer.

Run exactly one Captain process. A claimed submission is never retried automatically:
an interrupted insert may have succeeded. Operators reconcile 'processing' records.
"""
import asyncio
import base64
import hashlib
import hmac
import json
import logging
import os
import secrets
import time
from datetime import datetime
from dataclasses import dataclass
from types import SimpleNamespace
from urllib.parse import urlparse

from . import __ca_logic as logic

log = logging.getLogger(__name__)
KEYS = ("gamertag", "country", "age", "gender", "platform", "question_1", "question_2",
        "question_3", "question_4", "question_5", "rule_1", "rule_2", "ref_1", "ref_2", "ref_3")
HEADERS = ["request_id", "state", "created_at", "ticket", "answers_json", "schema_version", "entry_id", "detail"]
DOMAIN = "coastal-application-v1."
DEFAULT_WEB_URL = "https://script.google.com/macros/s/AKfycbwFPFDHdCN_wf811Gur7fV876RqdUTn13wOTJTiqRC1f5ty4kgk6cKMUmfaA2fv0AtLug/exec"
DEFAULT_INBOX_ID = "13jaecVN1wtBUXPMMnUUgbcxYD4joYMoz1WfxvAK8HBk"


def b64(value):
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def portal_config():
    values = [os.getenv(key, "").strip() for key in
              ("APPLICATION_WEB_URL", "APPLICATION_WEB_SECRET", "APPLICATION_INBOX_ID")]
    if not any(values):
        return None
    url, secret, inbox = values
    url = url or DEFAULT_WEB_URL
    inbox = inbox or DEFAULT_INBOX_ID
    parsed = urlparse(url)
    if (len(secret) < 32 or parsed.scheme != "https"
            or parsed.netloc != "script.google.com" or not parsed.path.startswith("/macros/s/")
            or not parsed.path.endswith("/exec") or parsed.query or parsed.fragment):
        raise ValueError("Configure the published Apps Script /exec URL, private inbox ID, and a 32+ character shared secret.")
    return SimpleNamespace(url=url, secret=secret, inbox=inbox)


def issue_ticket(user, secret, *, now=None):
    now = int(time.time()) if now is None else now
    data = dict(v=1, uid=str(user.id), name=str(user), nick=user.display_name,
                iat=now, exp=now+86400, nonce=secrets.token_hex(16))
    encoded = b64(json.dumps(data, separators=(",", ":"), ensure_ascii=False).encode())
    return encoded + "." + b64(hmac.new(secret.encode(), (DOMAIN+encoded).encode(), hashlib.sha256).digest())


def verify_ticket(ticket, secret, *, submitted_at):
    if not isinstance(ticket, str) or len(ticket) > 2048:
        raise ValueError("Invalid ticket")
    encoded, signature = ticket.split(".")
    expected = b64(hmac.new(secret.encode(), (DOMAIN+encoded).encode(), hashlib.sha256).digest())
    if not hmac.compare_digest(signature, expected):
        raise ValueError("Invalid ticket")
    data = json.loads(base64.urlsafe_b64decode(encoded+"="*(-len(encoded) % 4)))
    created = datetime.fromisoformat(submitted_at.replace("Z", "+00:00")).timestamp()
    uid, nonce = data.get("uid", ""), data.get("nonce", "")
    if (data.get("v") != 1 or not isinstance(uid, str) or not uid.isascii() or not uid.isdigit()
            or not 15 <= len(uid) <= 22 or not isinstance(nonce, str) or len(nonce) != 32
            or any(c not in "0123456789abcdef" for c in nonce)
            or not isinstance(data.get("name"), str) or len(data["name"]) > 100
            or not isinstance(data.get("nick"), str) or len(data["nick"]) > 100
            or type(data.get("iat")) is not int or type(data.get("exp")) is not int
            or data["exp"]-data["iat"] != 86400 or not data["iat"]-60 <= created <= data["exp"]
            or created > time.time()+60):
        raise ValueError("Invalid ticket claims")
    return data


def validate_answers(answers):
    if not isinstance(answers, dict) or set(answers) != set(KEYS):
        raise ValueError("Invalid answer keys")
    for value in answers.values():
        # Match HTML/JavaScript UTF-16 length, including astral characters.
        if not isinstance(value, str) or not 2 <= len(value.strip().encode("utf-16-le"))//2 <= 200:
            raise ValueError("Invalid answer length")
    return {key: answers[key].strip() for key in KEYS}


async def noop(**kwargs):
    pass


class RawApplications:
    def __init__(self, sheets):
        self.sheets = sheets

    async def submit_application(self, row):
        # Preserve Discord snowflakes and prevent formula evaluation of public input.
        return await self.sheets.submit_application(row, raw=True)


@dataclass(frozen=True)
class SignedApplicant:
    id: int
    name: str
    display_name: str

    def __str__(self):
        return self.name

    @property
    def mention(self):
        return f"<@{self.id}>"


class WebPortal:
    def __init__(self, bot, config):
        self.bot, self.config = bot, config
        self.task = None
        self.inbox_ready = False

    def start(self):
        self.task = asyncio.create_task(self.run(), name="coastal-application-inbox")

    async def stop(self):
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass

    async def run(self):
        await self.bot.wait_until_ready()
        while not self.bot.is_closed():
            try:
                await self.poll()
            except Exception as error:
                # Do not log answers, access codes, sheet data or service-account details.
                log.warning("application_inbox_poll_failed error=%s", type(error).__name__)
            await asyncio.sleep(30)

    async def poll(self):
        def read():
            if self.config.inbox == self.bot.sheets.applications.spreadsheet_id:
                raise ValueError("Inbox must be a separate workbook")
            sheet = self.bot.sheets.client.open_by_key(self.config.inbox).worksheet("Inbox")
            rows = sheet.get_all_values()
            if not rows or rows[0] != HEADERS:
                raise ValueError("Invalid inbox headers")
            return sheet, rows
        sheet, rows = await self.bot.sheets._run(read)
        if not self.inbox_ready:
            log.info("application_web_portal_inbox_ready")
            self.inbox_ready = True
        for position, row in enumerate(rows[1:], 2):
            if len(row) >= 6 and row[1] == "queued":
                await self.process(sheet, position, row)

    async def process(self, sheet, position, row):
        # Only B/G/H are written by Captain; Apps Script only appends immutable rows.
        # Never sort/delete inbox rows while the bridge is running.
        def claim():
            current = sheet.row_values(position)
            if current[:6] != row[:6] or current[1] != "queued":
                raise ValueError("Inbox row moved or already claimed")
            sheet.update_cell(position, 2, "processing")
        await self.bot.sheets._run(claim)
        state, detail, entry = "needs_attention", "validation_or_delivery_failed", ""
        try:
            data = verify_ticket(row[3], self.config.secret, submitted_at=row[2])
            if data["nonce"] != row[0]:
                raise ValueError("Mismatched request ID")
            answers = validate_answers(json.loads(row[4]))
            def content():
                app = self.bot.sheets.applications
                raw = [(app.row_values(n)+[""]*21)[:21] for n in (1, 2)]
                h = raw[1]
                if (h[0], h[3], h[19], h[20]) != ("entryID", "Discord Long ID", "Timestamp", "Approved?"):
                    raise ValueError("Application schema changed")
                version = b64(hashlib.sha256(json.dumps(raw, ensure_ascii=False, separators=(",", ":")).encode()).digest())
                if version != row[5]:
                    raise ValueError("Question version changed")
                return logic.load_content(app)
            current_content = await self.bot.sheets._run(content)
            # Identity is captured by Discord's authenticated slash command, not the browser.
            author = SignedApplicant(int(data["uid"]), data["name"], data["nick"])
            delivered = False
            async def followup_send(*args, **kwargs):
                nonlocal delivered
                # finish_application sends its success embed only after both review messages.
                delivered = kwargs.get("embed") is not None
            proxy = SimpleNamespace(settings=self.bot.settings, get_guild=self.bot.get_guild,
                                    sheets=RawApplications(self.bot.sheets), application_content=current_content)
            submission = SimpleNamespace(bot=proxy, application_data=answers)
            interaction = SimpleNamespace(user=author, response=SimpleNamespace(defer=noop),
                                          followup=SimpleNamespace(send=followup_send))
            await logic.finish_application(submission, interaction)
            entry = str(getattr(submission, "saved_entry_id", ""))
            if entry:
                state = "complete" if delivered else "saved_notification_failed"
                detail = "" if delivered else "saved_do_not_resubmit"
            elif getattr(submission, "submission_attempted", False):
                detail = "write_uncertain_check_live_sheet_before_retry"
        except Exception as error:
            log.warning("application_inbox_item_failed error=%s", type(error).__name__)
        # If acknowledgement fails, leave processing; never make a second insert.
        def acknowledge():
            if sheet.row_values(position)[0] != row[0]:
                raise ValueError("Inbox row moved")
            sheet.update(range_name=f"G{position}:H{position}", values=[[entry, detail]], value_input_option="RAW")
            sheet.update_cell(position, 2, state)
        await self.bot.sheets._run(acknowledge)
