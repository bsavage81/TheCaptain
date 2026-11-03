"""Private operator diagnostic. Defaults to offline config validation.

Never run login/probe until a live test has been separately authorized. No bot
startup, Discord commands, database reads, background jobs or automatic logins.
"""
import argparse
import asyncio
import json
import logging
import os
from pathlib import Path
import sys

from utils.integrations.realms.configuration import Principal, RealmsConfig
from utils.integrations.realms.errors import ConfigurationError, RealmsError
from utils.integrations.realms.models import Secret
from utils.integrations.realms.service import RealmsService
from utils.integrations.realms.token_store import EncryptedTokenStore
from utils.integrations.realms.transport import AiohttpTransport


def load_config(path):
    failed = False
    config = None
    try:
        if path.stat().st_size > 16384:
            raise ValueError()
        config = RealmsConfig.from_document(json.loads(path.read_text(encoding="utf-8")))
    except (OSError, ValueError, UnicodeError):
        failed = True
    if failed:
        raise ConfigurationError()
    return config


def load_keys():
    invalid = False
    keys = None
    try:
        data = json.loads(os.environ.get("CAPTAIN_REALMS_KEYS", ""))
        if not isinstance(data, dict) or not data or not all(isinstance(k, str) and isinstance(v, str) for k, v in data.items()):
            raise ValueError()
        keys = {k: Secret(v) for k, v in data.items()}
    except (ValueError, TypeError):
        invalid = True
    if invalid:
        raise ConfigurationError()
    return keys


async def live(args, config, *, transport_factory=AiohttpTransport):
    principal = Principal(args.user_id, args.guild_id)
    config.authorize(principal)
    store = EncryptedTokenStore(args.store_dir, config.binding, load_keys(), args.key_id)
    # Acquire private storage and single-writer lock before constructing a network session.
    with store:
        async with transport_factory(selected_realm_id=config.selected_realm_id) as transport:
            service = RealmsService(config, transport, store)
            try:
                if args.action == "login":
                    pending = await service.begin_device_login(principal)
                    print("Open this Microsoft verification page in your browser:")
                    print(pending.challenge.verification_uri)
                    print("Private one-time user code:", pending.challenge.user_code.value)
                    identity = await service.complete_device_login(principal, pending)
                    print("Verified configured Xbox account:", identity.gamertag)
                    print("Encrypted refresh credentials saved. No Realm was accessed.")
                else:
                    client = service.client(principal)
                    # This first request verifies identity through the service before Realms I/O.
                    realms = await client.list_realms()
                    print("Accessible Realm count:", len(realms.data))
                    if config.selected_realm_id:
                        realm = await client.realm()
                        print("Selected Realm state:", realm.data.state)
                        activity = await client.activities()
                        selected = next((a for a in activity.data if a.realm_id == config.selected_realm_id), None)
                        print("Selected Realm activity:", "unknown" if selected is None else len(selected.players))
                    print("Private diagnostic complete; no writes, invitation acceptance or world connection.")
            finally:
                await service.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("check", "login", "probe"), nargs="?", default="check")
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--user-id", type=int)
    parser.add_argument("--guild-id", type=int)
    parser.add_argument("--store-dir", type=Path)
    parser.add_argument("--key-id")
    parser.add_argument("--allow-live", action="store_true")
    args = parser.parse_args(argv)
    # CLI is a private terminal workflow, not a logger: suppress third-party wire logs.
    previous_logging = logging.root.manager.disable
    logging.disable(logging.CRITICAL)
    try:
        config = load_config(args.config)
        if args.action == "check":
            print("Configuration valid; integration", "enabled for manual use" if config.enabled else "disabled", "(offline).")
            return 0
        config.authorize(Principal(args.user_id, args.guild_id))
        if not args.allow_live or not sys.stdin.isatty() or not sys.stdout.isatty() or args.store_dir is None or not args.key_id:
            print("Live diagnostic requires explicit opt-in, a private interactive terminal and storage configuration.", file=sys.stderr)
            return 2
        phrase = "AUTHORIZE " + args.action.upper()
        if input("After separate owner approval, type " + phrase + " to contact Microsoft" + (" and Realms" if args.action == "probe" else "") + ": ") != phrase:
            return 2
        asyncio.run(live(args, config))
        return 0
    except RealmsError as error:
        print("Diagnostic stopped:", error.category, file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("Diagnostic cancelled.", file=sys.stderr)
        return 130
    except Exception:
        # Do not expose raw requests, parser errors or local key material in a traceback.
        print("Diagnostic stopped: unexpected_local_failure", file=sys.stderr)
        return 1
    finally:
        logging.disable(previous_logging)


if __name__ == "__main__":
    raise SystemExit(main())
