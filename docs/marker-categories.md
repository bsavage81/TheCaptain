# Season 10 marker categories

The standard `/addpoi_overworld`, `/addpoi_nether`, and `/addpoi_end` commands take
`x_coord`, `z_coord`, and a required `marker_type` choice. They open a private form
for text line 1 (or an icon character), optional text lines 2/3, and text color.
Optional lines can be left empty; `no` also clears them. A private helper message
links to the free Font Awesome icon browser. The map font remains Font Awesome 6
Free; newer and Pro-only glyphs may not render. This adds no web app or icon picker.
`/addpoi_endcity_claim` opens a two-field modal for gamertag and text color. Its
fixed claim icon, gamertag position, 10px font, and Community category are retained.
It has no radius field. `/addpoi_end_returngateway` still saves immediately from
X/Z because its icon, text, color, font, and category are fixed.

Player base and community marker forms additionally have an optional radius field. Column P (`radius`)
stores a whole number of blocks from the marker's X/Z center to its border, in that
dimension's own coordinates (no Nether coordinate scaling). Blank or 0 means no
border. Negative, fractional, or nonnumeric radii are rejected before saving.
Shop and portal markers leave P blank. A:O retain their existing meanings. No existing
markers are backfilled. Standard modal submissions contain 16 values; legacy special
End markers may still contain 15, leaving P empty.

Prepare/verify the radius headers with `python scripts/prepare_marker_categories.py --radius`
and add `--apply` to make missing-header changes. The web map can implement its future
border toggle by drawing a circle centered on X/Z for `category` equal to `Player Bases` or `Community`
with a finite numeric `radius > 0`; skip missing, zero, or invalid radii. This repository
does not contain the map renderer, so no border toggle is implemented here.

After deployment, register the three updated slash-command schemas before using
the new required marker-type parameter. No Sheet changes are required for this UI.

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
