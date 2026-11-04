"""Private activity extension; read-only preflight unless explicitly applied."""
import argparse
import json
import os
from migrations.player_registry import migrate as registry_migrate
from utils.players.models import MODELS
from utils.players.activity_models import RealmActivity


def migrate(backend, *, apply=False, backup_verified=False):
    return registry_migrate(backend, apply=apply, backup_verified=backup_verified,
                            models=[*MODELS, RealmActivity])


def main():
    from dotenv import load_dotenv
    from utils.core_features.__constants import ROOT
    from utils.database.__database import make_database
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--backup-verified", action="store_true")
    args = parser.parse_args()
    load_dotenv(ROOT / ".env")
    try:
        print(json.dumps(migrate(make_database(os.environ), apply=args.apply,
                                 backup_verified=args.backup_verified), indent=2))
    except Exception as error:
        parser.exit(1, f"Activity migration stopped ({type(error).__name__}); review schema/backup.\n")


if __name__ == "__main__":
    main()
