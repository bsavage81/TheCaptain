"""Inspect the authorized Captain server through TLS-verified panel API calls.

Never log API keys, panel URLs, startup commands, response bodies or private files.
"""
import argparse
import asyncio
import hashlib
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import sys
import time
from urllib.error import HTTPError
from urllib.parse import quote, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

ROOT = Path(__file__).resolve().parents[1]
EXPECTED_SERVER = "5ff9cb52"
GUIDE = "utils/coastal_guide/__cg_logic.py"
WEB_PORTAL = "utils/coastal_applications/web_portal.py"
LEGACY_REVISION = "1f9f85c95821830d2a95f4ccf2bafee2a443eed2"


class PanelError(RuntimeError):
    def __init__(self, status=None):
        self.status = status
        super().__init__("Panel request failed")


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class Panel:
    def __init__(self, url, key):
        parsed = urlsplit(url)
        if parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError("Panel URL must be a plain HTTPS origin/path")
        self.url = url.rstrip("/") + "/api/client"
        self.key = key
        self.opener = build_opener(NoRedirect())

    def get(self, path, *, raw=False):
        request = Request(self.url + path, headers={"Authorization": "Bearer " + self.key,
                          "Accept": "application/json"})
        try:
            with self.opener.open(request, timeout=30) as response:
                value = response.read(2_000_000)
                return value.decode("utf-8") if raw else json.loads(value)
        except HTTPError as error:
            raise PanelError(error.code) from None

    def restart(self):
        self.post(f"/servers/{EXPECTED_SERVER}/power", json.dumps({"signal": "restart"}))

    def post(self, path, body, *, content_type="application/json"):
        request = Request(self.url + path, method="POST",
            data=body.encode(), headers={
                "Authorization": "Bearer " + self.key, "Accept": "application/json",
                "Content-Type": content_type})
        try:
            with self.opener.open(request, timeout=30) as response:
                if response.status != 204:
                    raise PanelError(response.status)
        except HTTPError as error:
            raise PanelError(error.code) from None


def file_text(panel, name):
    try:
        return panel.get(f"/servers/{EXPECTED_SERVER}/files/contents?file=" + quote("/" + name, safe=""), raw=True)
    except PanelError as error:
        if error.status in (403, 404):
            return None
        raise


def normalized_hash(text):
    return hashlib.sha256(text.replace("\r\n", "\n").encode()).hexdigest()


def legacy_example():
    url = f"https://raw.githubusercontent.com/bsavage81/TheCaptain/{LEGACY_REVISION}/botconfig.example.json"
    with build_opener(NoRedirect()).open(Request(url), timeout=30) as response:
        content = response.read(100_000).decode("utf-8")
    if not isinstance(json.loads(content), dict):
        raise ValueError("Invalid committed example")
    return content


def repair_tracked_example(panel):
    """Preserve the exact user-edited example before restoring just that tracked file."""
    revision = file_text(panel, ".git/refs/heads/main")
    if not revision or revision.strip() != LEGACY_REVISION:
        raise ValueError("Legacy checkout changed; review before repairing the example")
    original = file_text(panel, "botconfig.example.json")
    if original is None:
        raise ValueError("Server example unavailable; no file was changed")
    committed = legacy_example()
    if original == committed:
        return {"tracked_example_already_clean": True}
    folders = panel.get(f"/servers/{EXPECTED_SERVER}/files/list?directory=%2F")
    if not any(x["attributes"]["name"] == ".database-backups" and not x["attributes"]["is_file"]
               for x in folders.get("data", [])):
        panel.post(f"/servers/{EXPECTED_SERVER}/files/create-folder", json.dumps({"root": "/", "name": ".database-backups"}))
    name = ".database-backups/botconfig.example.before-git-update-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + ".json"
    def write_file(path, content):
        panel.post(f"/servers/{EXPECTED_SERVER}/files/write?file=" + quote("/" + path, safe=""),
                   content, content_type="text/plain; charset=utf-8")
    write_file(name, original)
    if file_text(panel, name) != original:
        raise ValueError("Server example backup did not verify; original was not changed")
    if file_text(panel, "botconfig.example.json") != original or (file_text(panel, ".git/refs/heads/main") or "").strip() != LEGACY_REVISION:
        raise ValueError("Server files changed concurrently; original was not changed")
    write_file("botconfig.example.json", committed)
    if file_text(panel, "botconfig.example.json") != committed:
        raise ValueError("Tracked example restoration did not verify; preserved backup remains available")
    return {"server_example_backup_verified": True, "backup_path": "/" + name, "tracked_example_restored": True}


async def console_signals(panel):
    import aiohttp
    credentials = panel.get(f"/servers/{EXPECTED_SERVER}/websocket")["data"]
    socket = credentials["socket"]
    parsed = urlsplit(socket)
    if parsed.scheme != "wss" or parsed.hostname != "v-dtx-12.apollopanel.com":
        raise ValueError("Unexpected console socket origin")
    output = []
    panel_origin = urlsplit(panel.url)
    async with aiohttp.ClientSession() as session:
        async with session.ws_connect(socket, origin=panel_origin.scheme + "://" + panel_origin.netloc,
                                      timeout=aiohttp.ClientWSTimeout(ws_close=5)) as ws:
            await ws.send_json({"event": "auth", "args": [credentials["token"]]})
            for _ in range(180):
                try:
                    message = await ws.receive(timeout=2)
                except asyncio.TimeoutError:
                    break
                if message.type != aiohttp.WSMsgType.TEXT:
                    break
                payload = json.loads(message.data)
                if payload.get("event") == "auth success":
                    await ws.send_json({"event": "send logs", "args": [None]})
                if payload.get("event") == "console output":
                    output.extend(str(value) for value in payload.get("args", []))
    text = re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]", "", "\n".join(output))
    return {"logs_received": bool(output),
            "git_local_changes_block_pull": "would be overwritten by merge" in text,
            "git_divergent_branches": "divergent branches" in text,
            "git_authentication_failed": "Authentication failed" in text or "could not read Username" in text,
            "git_ownership_failed": "dubious ownership" in text,
            "git_not_repository": "not a git repository" in text,
            "git_up_to_date_reported": "Already up to date" in text,
            "configuration_error": "Settings migration" in text or "migrations.botdata_settings" in text,
            "bot_ready_logged": "TheCaptain ready" in text,
            "application_web_portal_enabled": "application_web_portal_enabled" in text,
            "application_web_portal_inbox_ready": "application_web_portal_inbox_ready" in text,
            "application_web_portal_disabled": "application_web_portal_disabled" in text,
            "application_inbox_poll_failed": "application_inbox_poll_failed" in text,
            "ready_revisions": re.findall(r"The Captain Version:\s*([0-9a-f]{7,40})", text)[-5:],
            "guide_file_named_in_error": GUIDE in text and ("error:" in text or "fatal:" in text)}


def inspect(panel, configured_server):
    payload = panel.get(f"/servers/{EXPECTED_SERVER}")
    attributes = payload["attributes"]
    if attributes.get("identifier") != EXPECTED_SERVER:
        raise ValueError("Server identifier mismatch")
    invocation = attributes.get("invocation", "")
    report = {"configured_server_matches_expected": configured_server.startswith(EXPECTED_SERVER),
              "expected_server_accessible": True,
              "startup_contains_git_pull": "git pull" in invocation,
              "startup_installs_requirements": "requirements" in invocation and "pip" in invocation}
    try:
        resources = panel.get(f"/servers/{EXPECTED_SERVER}/resources")
        report["server_state"] = resources["attributes"].get("current_state")
    except PanelError as error:
        report["resources_status"] = error.status
    try:
        variables = panel.get(f"/servers/{EXPECTED_SERVER}/startup")
        safe = {}
        report["startup_variable_names"] = [entry["attributes"]["env_variable"] for entry in variables.get("data", [])]
        for entry in variables.get("data", []):
            var = entry["attributes"]
            key, value = var["env_variable"], str(var.get("server_value", ""))
            if key in ("AUTO_UPDATE", "USER_UPLOAD", "BRANCH", "GIT_BRANCH", "PY_FILE", "BOT_PY_FILE", "STARTUP_FILE", "REQUIREMENTS_FILE"):
                safe[key] = value if re.fullmatch(r"[\w./ -]{0,120}", value) else "[nonstandard value]"
            if key in ("GIT_ADDRESS", "GIT_REPO", "GIT_URL"):
                safe[key + "_is_captain_repo"] = "github.com/bsavage81/thecaptain" in value.casefold()
                safe[key + "_empty"] = not value.strip()
            if not any(secret in key.upper() for secret in ("TOKEN", "PASSWORD", "PASS", "KEY", "SECRET", "AUTH")) and value.casefold() in ("0", "1", "true", "false", "yes", "no"):
                safe[key] = value
        report["startup_variables"] = safe
        report["startup_has_disabled_update_gate"] = bool(re.search(r'(?:"?0"?\s*==\s*"?1"?|"?false"?\s*==\s*"?true"?)', invocation))
    except PanelError as error:
        report["startup_variables_status"] = error.status
    guide = file_text(panel, GUIDE)
    if guide is not None:
        line = next((line.strip() for line in guide.splitlines() if line.strip().startswith("command_channel =")), "")
        report["guide_destination_source"] = next((name for name in (
            "bot_spam_channel_coastal", "botspamChannel", "CoastalMRP") if name in line), "unrecognized")
        report["guide_matches_checkout"] = normalized_hash(guide) == normalized_hash((ROOT / GUIDE).read_text(encoding="utf-8"))
    else:
        report["guide_file_readable"] = False
    if (ROOT / WEB_PORTAL).is_file():
        portal = file_text(panel, WEB_PORTAL)
        report["portal_source_matches_checkout"] = portal is not None and normalized_hash(portal) == normalized_hash(
            (ROOT / WEB_PORTAL).read_text(encoding="utf-8"))
    head = file_text(panel, ".git/HEAD")
    if head:
        if re.fullmatch(r"[0-9a-f]{40}\s*", head):
            report["server_commit"] = head.strip()
        elif re.fullmatch(r"ref: refs/heads/[\w./-]+\s*", head):
            ref = head.strip()[5:]
            report["server_branch"] = ref.removeprefix("refs/heads/")
            revision = file_text(panel, ".git/" + ref)
            if revision and re.fullmatch(r"[0-9a-f]{40}\s*", revision):
                report["server_commit"] = revision.strip()
    try:
        report["console_signals"] = asyncio.run(console_signals(panel))
    except Exception as error:
        report["console_inspection_error_type"] = type(error).__name__
        report["console_inspection_http_status"] = getattr(error, "status", None)
    return report


def main():
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--inspect-only", action="store_true")
    mode.add_argument("--restart-and-verify", action="store_true")
    parser.add_argument("--expected-revision")
    parser.add_argument("--repair-tracked-example", action="store_true")
    args = parser.parse_args()
    panel = Panel(os.environ["PANEL_URL"], os.environ["PANEL_API_KEY"])
    configured = os.environ.get("PANEL_SERVER_ID", "").strip()
    if args.restart_and_verify:
        if not configured.startswith(EXPECTED_SERVER) or not re.fullmatch(r"[0-9a-f]{40}", args.expected_revision or ""):
            raise ValueError("Explicit expected Captain server and revision required")
        # Verify ownership/identifier before performing the pre-authorized restart.
        if panel.get(f"/servers/{EXPECTED_SERVER}")["attributes"].get("identifier") != EXPECTED_SERVER:
            raise ValueError("Server identifier mismatch")
        if args.repair_tracked_example:
            print(json.dumps(repair_tracked_example(panel)), flush=True)
        panel.restart()
        print(json.dumps({"restart_accepted": True}), flush=True)
        deadline = time.monotonic() + 180
        report = {}
        while time.monotonic() < deadline:
            time.sleep(5)
            report = inspect(panel, configured)
            revisions = report.get("console_signals", {}).get("ready_revisions", [])
            if report.get("guide_matches_checkout") and report.get("portal_source_matches_checkout", True) and report.get("server_commit") == args.expected_revision and any(
                    args.expected_revision.startswith(revision) for revision in revisions):
                print(json.dumps(dict(report, deployment_verified=True), indent=2))
                return
        print(json.dumps(dict(report, deployment_verified=False), indent=2))
        raise ValueError("Server did not load the expected source and ready revision")
    print(json.dumps(inspect(panel, configured), indent=2))


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(json.dumps({"status": "failed", "error_type": type(error).__name__,
                          "http_status": getattr(error, "status", None)}))
        sys.exit(1)
