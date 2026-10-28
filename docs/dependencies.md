# Dependency review

Current target: Python 3.15.2 and Peewee 4.5.3, validated as documented in runtime-upgrade.md.
The earlier dependency baseline below is historical.

Checked October 27, 2026. No reliable deployment lock existed in the repository. The old main
could not provide a working runtime baseline because importing it required live credentials and
queried tables before bootstrap. After those repairs, 17 focused offline tests passed with
conservative packages (discord.py 2.3.2, Peewee 3.17.1, gspread 5.12.4, jishaku 2.5.2,
python-dotenv 1.0.1, oauth2client 4.1.3, PyMySQL 1.1.2). The complete installed baseline is in
`baseline-requirements.txt`; it is historical evidence, not an installation recommendation.

The same tests passed after upgrading, before expanding coverage. Direct runtime dependencies
are now inventoried in `requirements.in` with full pinned transitive closure in `requirements.txt`:
discord.py 2.7.1; jishaku 2.7.5; Peewee 3.19.0; gspread 6.2.1; oauth2client 4.1.3;
python-dotenv 1.2.4; PyMySQL 1.2.3. Exact versions came from official PyPI metadata. Peewee 4.5.3
was initially deferred; it is now selected and regression-tested while preserving Captain's schema.
The explicit MySQL driver is required by Peewee, rather than assumed to exist on the host.

Test dependencies are pinned separately. The first pip-audit run found PYSEC-2026-1845
(CVE-2025-71176, duplicated by the service) in pytest 8.4.2. pytest was upgraded to 9.2.0 and
pytest-asyncio to 1.4.1; the final audit result is saved in `dependency-audit.json`.
Advisory checks are a point-in-time check, not a guarantee against unknown vulnerabilities.

## Authentication migration decision

The existing oauth2client service account loader and four scopes are retained for deployment
compatibility. gspread still converts these credentials to google-auth internally. Migration is
recommended separately: use `google.oauth2.service_account.Credentials.from_service_account_file`
with the same credentials path/scopes, compare auth failures against copied staging Sheets, then
remove oauth2client/httplib2/rsa when no longer direct requirements. Do not change credential
format, permissions and feature architecture in the same step. No live authentication was tested.

## Removed runtime requirements

Flask supplied request hooks even though no web server ran. FlaskIntegration and discord-sentry
reporting were inherited optional telemetry with unsanitized exception exposure; removed from
active startup. pygit2 existed only for an unused version property; no native Git dependency is
needed by features. alive-progress was only startup decoration. requests/psutil were unused after
removing inherited public traceback gists and stale utility imports. requests remains transitive
through Google libraries. Archive-only imports do not imply runtime dependencies. Jishaku is
explicitly retained and its native upstream owner authorization is unchanged.

## Official sources consulted

- [discord.py releases/changelog](https://discordpy.readthedocs.io/en/stable/whats_new.html)
- [discord.py package metadata](https://pypi.org/project/discord.py/)
- [jishaku package metadata](https://pypi.org/project/jishaku/)
- [Peewee MySQL driver documentation](https://docs.peewee-orm.com/en/latest/peewee/database.html)
- [gspread authentication and oauth2client transition](https://docs.gspread.org/en/master/oauth2.html)
- [gspread package metadata](https://pypi.org/project/gspread/)
- [PyMySQL published security advisories](https://github.com/PyMySQL/PyMySQL/security/advisories)
- [Python version support](https://devguide.python.org/versions/)
- [CodeQL supported action versions](https://github.com/github/codeql-action/blob/main/README.md)
- [checkout action documentation](https://github.com/actions/checkout)
- [setup-python action documentation](https://github.com/actions/setup-python)

Only `.github/workflows/` runs in GitHub Actions. CodeQL was updated to v4; obsolete active
OSSAR/.NET tooling was replaced with pip-audit. The inactive root `workflows/` duplicates were removed in the Season 10 cleanup. CI installs pins, checks syntax/imports and runs the offline suite on Windows
and Linux without bot secrets. Security audit alone queries public advisory data. No panel or
production deployment workflow was copied. Hosted CI execution remains unverified until pushed.

## Season 10 maintenance

Runtime dependency pins and oauth2client credential compatibility are unchanged. Dedicated-account
validation does not require a new authentication library or credential format. Ruff 0.17.3 is a
pinned development-only addition for unused imports, undefined names and related F checks. The
current security audit is recorded in validation.md; baseline-requirements.txt remains historical.
No new deployment dependencies or panel integration were introduced.
