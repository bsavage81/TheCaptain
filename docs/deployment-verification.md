# Verified Captain deployment and blocked Git updates

## Resolved October 29, 2026

The corrected guide announcement was on GitHub, but Apollo was still running commit
`1f9f85c`. Its actual guide file used `CoastalMRP`, producing the wrong channel link even
though the live database correctly stored Coastal's bot-command channel.

The owner identified an uncommitted change to the server's tracked `botconfig.example.json`.
The new release deletes that obsolete example, so the local edit prevented Git from pulling
the release. The old restart action sent a request without checking the HTTP response or
the deployed revision; its success did not demonstrate an updated bot.

The repair preserved the exact edited example in the server's private Git-ignored
`/.database-backups/botconfig.example.before-git-update-20261029T124106Z.json`, verified
the backup contents, and restored only that tracked example to its original committed
version. The actual `botconfig.json`, `.env`, database and Google credentials were not changed.
The Apollo Startup command was not changed.

A checked API restart then allowed the normal startup Git pull to reach `d2eab2a`.
Verification read the actual server files, confirmed the guide uses
`bot_spam_channel_coastal`, and read the ready banner for that deployed revision.
Coastal's actual destination was independently verified through Discord as
`415213466522091542` (#bot-commands-spamming). The particular announcement supplied
by the owner was edited in place with mention notifications disabled.

## Deployment checks

The main workflow now uses `scripts/panel_deploy.py` with the existing panel secrets:

- Requires HTTPS, valid TLS and the explicitly authorized server identifier `5ff9cb52`.
- Does not follow redirects with credentials or log API keys, private file contents,
  panel URLs, complete startup commands or raw console logs.
- Requires HTTP 204 acknowledgement of the restart; rejected requests fail the job.
- Checks the actual server commit against the triggering GitHub commit.
- Compares the actual guide source with the checked-out release.
- Reads the authenticated console and requires the ready-banner revision to match.
- Fails if source/readiness verification does not complete within three minutes.

The read-only diagnostic workflow can also inspect startup flags, the current revision,
the guide destination field and sanitized error signals. It does not restart the server.
Authenticated console access uses the panel's legitimate origin and the expected Apollo
node over WSS. Temporary console tokens remain in memory and are never logged.

## Future local-change conflicts

Preserve and inspect server edits before restoring any tracked file. Do not run a blanket
`git reset --hard`, delete private configuration, or stash unrelated production data.
Private `.env`, `creds.json`, runtime configuration and backups belong outside version control.
Operational settings now live in `botdata`, so editing a tracked example is unnecessary.

The `--repair-tracked-example` maintenance option is narrowly restricted to the observed
old revision and `botconfig.example.json`. It verifies a server-side backup before restoring
that one file and refuses an unexpected revision or concurrent change. It is not used by
normal deployment or read-only diagnostics.
