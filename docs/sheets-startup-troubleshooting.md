# Sheets startup failures

The configuration loader reads botconfig.json beside main.py. application_sheet_id and
markers_sheet_id take precedence over titles. After editing the private file, restart the bot;
it does not reload Sheets configuration while running. Example files are not deployment settings.

An applications lookup failure happens before application question/applicant processing. Credentials
may have loaded successfully, but authorization is lazy, so this stage can still fail during token
refresh or its first Google request. The safe startup error now separates spreadsheet lookup from
first-worksheet metadata and includes exception type, available HTTP status and allowlisted Google
reason codes. Raw exception text, Google response bodies, key contents and applicant data are never
printed. The same diagnostics apply to later marker/worksheet stages.

- SERVICE_DISABLED/accessNotConfigured: enable Google Sheets API in the service account's project
  (Captain's documented project is thecaptain-513018). Google Drive API is also needed for title
  discovery; explicit spreadsheet keys bypass that discovery operation.
- HTTP 403/PermissionError: check service-account file access and API availability. File sharing and
  enabling project APIs are separate actions. Use the documented Captain account with the existing
  permissions needed for inserts/status changes. Do not make applicant files public as a workaround.
- SpreadsheetNotFound/HTTP 404: verify the key/title and that the service account can access that
  file. This error can conceal lack of access; it does not prove the file does not exist.
- HTTP 400: verify that the supplied ID identifies a native Google Sheet rather than a Doc or an
  uploaded workbook. Worksheet structure is checked only after the spreadsheet is opened.
- RefreshError/HTTP 401: check whether the existing private key is active and the server clock is
  correct. Never paste, print or commit creds.json. Do not regenerate credentials speculatively.
- Network/SSL/timeout: check outbound HTTPS and trusted Google certificates. The database's explicit
  self-signed setting is scoped to MySQL; do not disable Google HTTPS verification.
- HTTP 429/5xx: retry startup later; initialization performs reads, not application insert retries.

Official [gspread authentication setup](https://docs.gspread.org/en/latest/oauth2.html) explains
project API enablement and service-account sharing. The Google Drive connector may use a different
account and cannot establish whether Captain's service account has access. No live Sheets records
or private credentials were read during diagnosis; exact root cause needs a classified error or a
confirmed project/API configuration check.
