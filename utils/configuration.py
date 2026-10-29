"""Strict database runtime configuration and explicit legacy-file conversion.

Secrets are bootstrap environment values. Non-secret operational values live only in
botdata.settings_json (row 1); prefix stays in its existing canonical SQL column.
"""
import json
import os
import re
from pathlib import Path
from utils.core_features.__constants import ROOT

VERSION = 1
COLUMN = "settings_json"
SEED = ROOT / "config" / "botdata-settings.seed.json"
BOOTSTRAP_KEYS = ("token", "database_ip", "database_port", "database_username",
                  "database_password", "database_schema", "database_ssl_mode", "database_ssl_ca")
REQUIRED_IDS = ("MRP", "Coastal", "CoastalMRP", "CoastalApplications", "CoastalOPTeam",
                "CoastalMapUpdates", "CoastalInviteChannel", "CoastalGuideRole",
                "CoastalActiveRole", "CoastalGuideResponses", "botspamChannel")
LEGACY_KEYS = {"bannedlistChannel", "questionSuggestChannel", "realmChannelResponse", "BotType",
               "OtherBotID", "BotID", "ServerID", "ServerID2", "MRPWelcome", "AurafallApplications",
               "PBtestApplications", "AurafallOPTeam", "PBtestOPTeam", "Innkeeper", "ModReport",
               "GeneralChannel", "Aurafall", "77th", "CoastalMRPpbtest"}
SETTING_KEYS = set("""MRP Coastal PBtest CoastalMRP CoastalApplications CoastalOPTeam
CoastalMapUpdates botspamChannel CoastalInviteChannel CoastalGuideRole CoastalActiveRole
CoastalGuideResponses OPTeamRole owner_ids credentials_path application_sheet markers_sheet
application_sheet_id markers_sheet_id realm_name guide_web_url guide_pdf_url guide_question
guide_answer guide_answer_match guide_cells logo_url profiles_enabled checkin_enabled
checkin_announcements_enabled checkin_reminders_enabled checkin_timezone checkin_season
checkin_season_name checkin_channel_id checkin_staff_channel_id checkin_eligible_role_id
checkin_inactive_role_id checkin_reminder_days profile_sources""".split())


def load_bootstrap(environ=None):
    """Never reads botconfig.json or fills guild/channel/role defaults."""
    environ = os.environ if environ is None else environ
    if str(environ.get("bot_type", "STABLE")).upper() != "STABLE":
        raise ValueError("Retired bot_type cannot initialize production")
    config = {key: environ[key] for key in BOOTSTRAP_KEYS if key in environ}
    config["configuration_source"] = "database"
    required = ("token", "database_ip", "database_username", "database_password", "database_schema")
    if any(not config.get(key) for key in required):
        raise ValueError("Configure token and database bootstrap environment variables before startup")
    return config


def validate_document(document):
    if not isinstance(document, dict) or type(document.get("version")) is not int or document.get("version") != VERSION:
        raise ValueError("Unsupported botdata settings version")
    if set(document) != {"version", "settings", "legacy_settings"}:
        raise ValueError("Unexpected botdata settings envelope")
    config = document["settings"]
    if not isinstance(config, dict) or not isinstance(document["legacy_settings"], dict):
        raise ValueError("Settings and legacy_settings must be objects")
    if set(config) != SETTING_KEYS or set(document["legacy_settings"]) - LEGACY_KEYS:
        raise ValueError("Settings keys differ from the supported configuration schema")
    for key, value in document["legacy_settings"].items():
        if key == "BotType":
            if str(value).upper() != "STABLE":
                raise ValueError("Retired deployment configuration cannot be activated")
        elif type(value) is not int or not 0 < value < 2**63:
            raise ValueError("Legacy identifiers must be positive integers")
    for key in REQUIRED_IDS:
        if type(config[key]) is not int or not 0 < config[key] < 2**63:
            raise ValueError(f"Configure a positive Discord ID for {key}")
    if config["PBtest"] is not None and (type(config["PBtest"]) is not int or not 0 < config["PBtest"] < 2**63):
        raise ValueError("PBtest must be a positive guild ID or null")
    if not isinstance(config["owner_ids"], list) or not config["owner_ids"] or any(
            type(uid) is not int or not 0 < uid < 2**63 for uid in config["owner_ids"]):
        raise ValueError("owner_ids must contain positive Discord IDs")
    if not (type(config["OPTeamRole"]) is int and config["OPTeamRole"] > 0 or
            isinstance(config["OPTeamRole"], str) and config["OPTeamRole"].strip()):
        raise ValueError("OPTeamRole must be a role ID or name")
    for key in ("application_sheet", "markers_sheet", "credentials_path", "realm_name", "checkin_season_name"):
        if not isinstance(config[key], str) or not config[key].strip():
            raise ValueError(f"Configure nonempty {key}")
    for key in ("application_sheet_id", "markers_sheet_id"):
        if config[key] is not None and (not isinstance(config[key], str) or not config[key].strip()):
            raise ValueError(f"{key} must be a nonempty key or null")
    for key in ("guide_web_url", "guide_pdf_url", "guide_question", "guide_answer", "logo_url"):
        if not isinstance(config[key], str):
            raise ValueError(f"{key} must be a string")
    if not isinstance(config["guide_cells"], dict) or not isinstance(config["profile_sources"], dict):
        raise ValueError("guide_cells and profile_sources must be objects")
    if set(config["guide_cells"]) - {"web_url", "pdf_url", "question", "answer"} or any(
            not isinstance(cell, str) or not re.fullmatch(r"[A-Z]+[1-9][0-9]*", cell) for cell in config["guide_cells"].values()):
        raise ValueError("Invalid guide cell mapping")
    for options in config["profile_sources"].values():
        if not isinstance(options, dict) or set(options) - {"season", "header_row", "worksheet", "trusted_discord_ids"}:
            raise ValueError("Invalid archive source options")
        for key in ("season", "header_row"):
            if key in options and (type(options[key]) is not int or options[key] <= 0):
                raise ValueError("Archive season and header row must be positive integers")
        if "trusted_discord_ids" in options and type(options["trusted_discord_ids"]) is not bool:
            raise ValueError("Archive ID trust option must be boolean")
        if "worksheet" in options and (not isinstance(options["worksheet"], str) or not options["worksheet"].strip()):
            raise ValueError("Archive worksheet must be nonempty")
    if config["checkin_enabled"] and not config["profiles_enabled"]:
        raise ValueError("Enable profiles before check-ins")
    from utils.players.checkins import validate
    validate(config)
    # Validate all guide parameters without reading Sheets; cell values are checked at startup.
    from utils.coastal_guide.__cg_logic import load_guide_content
    guide = dict(config, guide_cells={})
    load_guide_content(guide)
    return document


def import_document(source):
    """Explicit import fills omitted keys from the reviewed seed, never at runtime."""
    if not isinstance(source, dict):
        raise ValueError("Configuration source must be an object")
    if "version" in source:
        return validate_document(source), None
    if str(source.get("BotType", source.get("bot_type", "STABLE"))).upper() != "STABLE":
        raise ValueError("Retired deployment config cannot be imported")
    document = json.loads(SEED.read_text(encoding="utf-8"))
    allowed = set(document["settings"])
    unknown = set(source) - allowed - LEGACY_KEYS - set(BOOTSTRAP_KEYS) - {"prefix", "bot_type", "sentry_dsn"}
    if unknown:
        raise ValueError("Unknown configuration keys require explicit schema review")
    document["settings"].update({key: source[key] for key in allowed if key in source})
    document["legacy_settings"].update({key: source[key] for key in LEGACY_KEYS if key in source})
    prefix = source.get("prefix")
    if prefix is not None and (not isinstance(prefix, str) or not prefix.strip()):
        raise ValueError("prefix must be nonempty")
    return validate_document(document), prefix


def read_database_settings(backend):
    """Read-only, fail closed; stale local JSON and constants have no precedence."""
    if COLUMN not in {c.name for c in backend.get_columns("botdata")}:
        raise ValueError("Run migrations.botdata_settings before starting the database-configured runtime")
    row = backend.execute_sql("SELECT settings_json, prefix FROM botdata WHERE id=1").fetchone()
    if row is None or row[0] is None:
        raise ValueError("Production database settings are missing; import them explicitly")
    if not isinstance(row[1], str) or not row[1].strip():
        raise ValueError("Production prefix is missing")
    document = validate_document(json.loads(row[0]))
    config = dict(document["settings"])
    config["prefix"] = row[1]
    config["configuration_source"] = "database"
    config["credentials_path"] = str((ROOT / Path(config["credentials_path"])).resolve())
    return config
