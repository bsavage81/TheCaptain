# Baseline and preserved contracts

Remote heads rechecked before implementation on October 27, 2026 (America/Chicago):
TheCaptain main `24535b991e83732b26ce98a7be80adb76ff748cb`;
PortalBot dev `34ec7f696c4c253ca19846e4a40a84976d343ea8`.
Both matched the requested snapshots. Captain's local origin is still
`https://github.com/bsavage81/TheOldKing.git`; it was deliberately not rewritten or pushed.
Captain and PortalBot started with no working-tree changes. No applicable AGENTS.md was found
in either repository or the ancestor directories. PortalBot was used read-only.

## Commands and access

`baseline-commands.json` captures source decorators, Python names and options before behavior edits.
The original two End overwrites meant only the last of three End definitions survived class creation.
Intended current command inventory:

| Command | Options | Scope | Access |
| --- | --- | --- | --- |
| `/repeat` | `message: str` | global | existing avatar tree check |
| `/applycoastal` | none | MRP; CoastalMRP channel only | existing avatar tree check |
| `/approveapp`, `/denyapp` | `appnumber: str` | PBtest and Coastal | OP Team role plus avatar |
| `/guide` | none | PBtest and Coastal | OP Team role plus avatar (prefix-only decorator repaired) |
| `/addpoi_overworld`, `/addpoi_nether`, `/addpoi_end`, `/addpoi_endcity_claim`, `/addpoi_end_returngateway` | `x_coord: int`, `z_coord: int` | PBtest and Coastal | existing avatar check; no new role restriction |
| prefix `sync` | guild / global / all | existing guild/global sync targets | Administrators tier >= 3; author-owned confirmation for global/all |
| jishaku prefix group | upstream options | upstream scope | upstream bot owner check |

Bot owner check retains database tier >= 3, falling back to Discord's owner logic.
The avatar policy is preserved, even though its original explanation may be outdated.
Guide's OP Team restriction was clearly expressed with an incompatible prefix decorator; enforcing
that intended restriction is a deliberate defect repair, not a new Moderator-role policy.
No member-facing expansion of guide access was invented. Confirm the OP Team intent in staging.

## Database

Peewee tables remain `botdata` and `administrators`. `BotData` retains `id`, `persistent_views`,
`prefix`, `bot_spam_channel_coastal`, `bot_spam_channel_aurafall`, `bot_type`, `bot_id`,
`server_id_aurafall`, `server_id_coastal`, with original field types/defaults. Administrators retains
`id`, unique BigInteger `discordID`, and Integer `TierLevel`. STABLE selects ID 1; BETA selects ID 2.
Existing rows are untouched. New rows use explicit selected IDs and existing defaults. No schema
migration or replacement with PortalBot models is required. Table creation occurs only at startup.
SQLite tests validate model behavior; MySQL driver/server behavior is a staging check.

## Application Sheet

Spreadsheet title: **CCS9 Realm Application**, first worksheet (`sheet1`). Row 1 A:I contains
application title/description, reference title/description, thank-you title/description, then the
three page titles. Row 2 E:S contains the 15 question labels in page order. Each page has exactly
five required long text inputs (2..200 chars, labels capped at 45 chars). Titles and prompts come
from the Sheet; no replacement season content is supplied.

Insert at row **3**, `USER_ENTERED`. Column order A:T is ID; Discord username; display name;
Discord ID as string; gamertag; country; age; gender; platform; questions 1..5; rules 1..2;
references 1..3; local timestamp `%m/%d/%Y %H:%M:%S`. Column U (21) is subsequently updated to
exactly **Yes** or **No**. Application response embeds, reactions and user ownership are retained.
The timestamp follows host local time as before; operators must set the deployment timezone.

## POI Sheet

Spreadsheet title: **Coastal Markers**. Worksheets: **Overworld**, **Nether**, **End**, **Questions**.
Questions B1:B6 hold description, text 1..3, color, marker-type prompts.
Insert at row **2**, `USER_ENTERED`. A:N stays ID, X, Z (legacy column named y), min zoom `-1`,
image, anchor, text 1, text 2, text 3, color, stroke `#ffffff`, offset X `0`, offset Y `0`, font.
Fonts remain `900 8px 'Font Awesome 6 Free'` for base/default, `900 10px ...` for shop and
special End markers, `900 12px ...` for portals. End claim uses U+F06A and the gamertag; return
gateway uses U+F52B, `Return Portal`, red. Blank text 2/3 interpretation retains original `no`/`No`.

## Verified original defects and intended repair

- Import-time config creation, Google credential reads/requests and database table creation:
  explicit injectable startup and worker boundaries.
- BotData read before bootstrap, invalid create fields, unspecified BETA ID, unavailable owner_ids:
  initialize tables and selected row before bot prefix/commands; seed configured legacy owners only
  for an empty administrator table.
- Three Python methods named addpoi_end: unique methods preserve all intended slash names.
- Stale normalized retry answer, unhandled retry timeout and unowned guide messages: refresh each
  answer, bind author/channel, handle all waits, and avoid overlapping sessions.
- Inherited question-suggestion persistent view referenced absent models and a database flag:
  remove unrelated question wiring. Temporary application views remain temporary.
- Blocking Sheets calls before acknowledgement, ID read long before insert, mutable row indexes:
  serialize read/write operations off-loop and resolve IDs/rows at write time.
- Public error gists, inherited branding and unused Flask/Sentry imports: remove from active code.

## Guarantees and limitations

Exactly one writer bot process may use a given set of spreadsheets. An asyncio lock serializes
operations inside that process and stays held until a cancelled worker finishes. It is **not a
distributed lock**: another bot, human/script writer or independent service can still race with ID
allocation or row lookup/update. Running BETA and STABLE against the same Sheets is unsafe.
Allocate each staging bot its own Sheets. Multiple active writers require a separately designed
shared allocator/transactional outbox and exclusive Sheet writer, not merely another Python lock.

ID allocation scans numeric IDs from the data rows and inserts max+1; it no longer assumes row 2/3
contains the max or reserves an ID at the start of a conversation. A transport timeout can occur
after Google committed a write. Inserts are never automatically retried. Repeated submission of
the same final modal is blocked in memory; restart, another modal, or user retry is not durable
idempotency. Operators must reconcile uncertain writes before retrying. USER_ENTERED and its
existing spreadsheet interpretation are intentionally preserved.

A saved Sheet row and Discord messages/DM/invite delivery are not atomic. Applications report a
saved entry ID if later notifications fail. POI failures explicitly report possible completed writes.
Decision status remains saved even if a DM fails, with failure surfaced to the operator. A created
invite can remain unused after a status write fails; revoke/reconcile it manually. Concurrent
conflicting approval/denial actions are serialized at the Sheet write, but last completed write wins;
notification ordering is not transactional. No automatic compensation deletes applicant data.
Application views and duplicate-attempt protection are in-memory and expire on restart. Guide role
updates can partially succeed if the second assignment or notification fails; operators reconcile.
