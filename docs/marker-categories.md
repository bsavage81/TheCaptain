# Season 10 marker categories

All three standard `/addpoi_*` conversations accept `base`, `shop`,
`portal`, or `community`, trimming whitespace and ignoring case. Invalid answers reprompt
without saving a marker. Categories in O are respectively `Player Bases`, `Shops`,
`Portals`, and `Community`; font sizes in N are 8, 10, 12, and 10px. Other A:N fields
and the configured Season 10 spreadsheet ID are preserved. Both success replies and
staff embeds show the category.

Special End city claims keep their existing icon and 10px font and use `Community`.
Return gateways keep their existing icon and 10px font and use `Portals`.

Live schema verified on November 1, 2026: Overworld, Nether, and End all have
`category` in O1. The owner added the Nether and End headers; existing markers
are already categorized and must not be backfilled. Questions!B6 is updated to
the same four-choice prompt used by the code during rollout.

For future setup verification, preview the narrowly scoped preparation:

```shell
python scripts/prepare_marker_categories.py
python scripts/prepare_marker_categories.py --apply
```

The explicit apply adds `category` only to missing O1 headers and updates Questions!B6
with the four-choice prompt. It verifies the Season 10 spreadsheet ID, all A:N headers,
and that O is blank or already `category` before any writes; each changed cell is read
back. No rows are inserted and no existing marker values are backfilled or changed.
The conversational prompt uses the same wording from code so stale sheet text cannot
advertise unsupported choices. New 15-column writes fail if the category header is missing.

This setup does not change the spreadsheet ID or any existing marker rows.
