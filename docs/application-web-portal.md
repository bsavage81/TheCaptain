# Coastal Craft web applications

The Apps Script portal replaces the applicant's Discord modal pages while keeping
Captain as the only writer to the existing application database. The existing
`/approveapp`, `/denyapp`, profile capture, OP review embeds and reactions remain.

## Source and deployment

- Source: `apps_script/coastal_application/Code.gs` and `Index.html`.
- Script project: https://script.google.com/d/1D0WZ8Bw2oaasmeLV1f1ZFSmbgF4iGugu8q5QFEIPPXu1EH-3RH3V6VF7/edit
- Public form: https://script.google.com/macros/s/AKfycbwFPFDHdCN_wf811Gur7fV876RqdUTn13wOTJTiqRC1f5ty4kgk6cKMUmfaA2fv0AtLug/exec
- Private inbox: https://docs.google.com/spreadsheets/d/13jaecVN1wtBUXPMMnUUgbcxYD4joYMoz1WfxvAK8HBk/edit
- Existing database: https://docs.google.com/spreadsheets/d/1ltMnItNgDBk5FhgsC-afi0l17OBnfOTcKPIkcSw9zvE/edit

Document IDs and the deployment URL are not credentials. Workbooks and the script
editor must remain restricted. Applicants use the public web deployment. Share
the inbox as Editor with Captain's existing service account:
`thecaptain@thecaptain-513018.iam.gserviceaccount.com`.

## Bot configuration

Set `APPLICATION_WEB_SECRET` in Captain's private environment or `.env` to the
same 32+ character random secret stored in Apps Script. Never commit its value.
With only that secret configured, the URL and inbox above are used as defaults.
Optional `APPLICATION_WEB_URL` and `APPLICATION_INBOX_ID` environment variables
override those defaults. Blank all three to retain the original Discord modals.
Restart after changing the bot environment. Keep the existing operational
`application_sheet_id` pointing to the database workbook above.

The environment is separate from the botdata table. Invalid partial configuration
fails the application cog load instead of issuing unusable codes.

## Apps Script configuration

| Script Property | Value |
| --- | --- |
| APPLICATION_SHEET_ID | `1ltMnItNgDBk5FhgsC-afi0l17OBnfOTcKPIkcSw9zvE` |
| APPLICATION_TAB | `Form Responses 1` |
| APPLICATION_INBOX_ID | `13jaecVN1wtBUXPMMnUUgbcxYD4joYMoz1WfxvAK8HBk` |
| APPLICATION_WEB_SECRET | Same private random value as Captain |
| APPLICATIONS_OPEN | `true` to accept applications; `false` to close |

For a new inbox only, run the visible `setupInbox` function from Code.gs as the
deployment owner. Its identity guard blocks anonymous web callers and invokes
the hidden `setupInbox_` helper. It refuses to overwrite an existing inbox.
The current inbox has already been created; do not repeat setup.

Deploy to execute as the owner, accessible to Anyone. Source edits require a new
version of the existing deployment; Script Property edits do not. Google Sites
can embed the `/exec` URL; add a direct-link fallback. Google multi-account sign-in
can rewrite the URL with `/u/3/` and produce a Drive error; a signed-out/private
window is a useful access check.

## Application and database contract

`/applycoastal` retains its server/channel restrictions. With the portal enabled
it sends an ephemeral 24-hour access code and form button. The HMAC-signed code
contains the identity captured by the Discord command; the browser cannot choose
a different Discord ID. Keep codes private.

The form reads A1:I1 for introductions/section titles and E2:S2 for the existing
15 question labels. It keeps the 2–200 character required-answer limits and adds
Back/Next, browser drafts, review and explicit confirmation. It never reads live
applicant rows. Snapshot checks prevent interpreting answers under changed prompts.
Text is displayed using textContent, not HTML injection.

Apps Script appends A:H to the separate Inbox worksheet. Captain polls every
30 seconds, validates signatures/answers/snapshot/column sentinels, claims a row,
and runs its existing serialized save and review flow. IDs are allocated under
the same lock as modal submissions. Records still occupy A:T at row 3; decisions
are Yes/No in U. Web submissions use RAW input to preserve exact Discord IDs and
prevent formula execution. Existing modal/POI modes are unchanged. No schema
migration, second writer, inbound bot port or Discord token in Apps Script.

## Recovery and verification

Run exactly one Captain process. Do not sort/delete/rearrange Inbox rows while
active; use filter views. Apps Script appends immutable inputs; Captain changes
state B and receipt fields G:H. Reusing a code returns the same receipt.

| State | Meaning |
| --- | --- |
| queued | Waiting; inspect bot availability and service-account access if persistent |
| processing | Claimed; a crash/uncertain acknowledgement needs manual reconciliation |
| complete | Saved with ID in G and review messages/reactions delivered |
| saved_notification_failed | Saved with ID in G; restore the review message, do not reinsert |
| needs_attention | Validation/configuration/uncertain save; check live sheet before retry |

Claimed rows are never retried automatically because the legacy schema has no
durable request-ID column. Inspect the live sheet and review channel before an
operator retries an interrupted write. Archive completed rows only while the
bridge is stopped, preserving unresolved records.

Readiness logs contain no secrets or answers: `application_web_portal_enabled`
and `application_web_portal_inbox_ready`. `application_inbox_poll_failed` signals
an access/processing issue. Deployment diagnostics compare the actual portal
source and report readiness alongside the deployed commit/banner.

Run `python -m pytest` with pinned development requirements and
`node --test apps_script/coastal_application/test-backend.cjs`. Offline tests use
synthetic identities/responses and block outside network access. A live operator
test is still needed to prove Discord → form → inbox → review; no real applicant
data should be used merely to test delivery.

Rollback: close the form, reconcile inbox work, stop Captain, unset the three
bridge environment values, and restart. The old modal flow resumes without
changing application records or decisions. Retain the inbox for recovery.
