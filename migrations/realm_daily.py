"""Explicit additive daily timeline migration; defaults to read-only preflight."""
import argparse
import json
import os
from migrations.player_registry import migrate as registry_migrate
from utils.realms.daily_models import DailyReport, DailyCollection


def migrate(backend, *, apply=False, backup_verified=False):
    return registry_migrate(backend, apply=apply, backup_verified=backup_verified,
                            models=[DailyReport, DailyCollection])


def main():
    from dotenv import load_dotenv
    from utils.core_features.__constants import ROOT
    from utils.database.__database import make_database
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--backup-verified', action='store_true')
    args = parser.parse_args()
    load_dotenv(ROOT / '.env')
    print(json.dumps(migrate(make_database(os.environ), apply=args.apply,
                             backup_verified=args.backup_verified), indent=2))


if __name__ == '__main__':
    main()
