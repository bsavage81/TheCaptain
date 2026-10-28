# File mapping

| Previous file | Current file(s) |
| --- | --- |
| `main.py` | Thin `main.py`; config/constants in `utils/core_features/__common.py`, `__constants.py` |
| `core/database.py` | `utils/database/__database.py` |
| `core/checks.py` | `utils/helpers/__checks.py` |
| `core/logging_module.py` | `utils/helpers/__logging_module.py` |
| `core/special_methods.py` | `utils/core_features/__special_methods.py` (safe errors; inherited wiring removed) |
| `core/common.py` | `utils/core_features/__common.py` (config and active sync button only) |
| `utils/Global_cogs/sync_slash.py` | `utils/admin/bot_management/bm_main.py`, `__bm_commands.py` |
| `utils/Global_cogs/repeat.py` | `utils/core_features/cf_main.py`, `__utility_commands.py` |
| `utils/Coastal_cogs/CoastalAppCMD.py` | `utils/coastal_applications/ca_main.py`, `__ca_commands.py`, `__ca_logic.py`, `__ca_views.py` |
| `utils/Coastal_cogs/CoastalGuide.py` | `utils/coastal_guide/cg_main.py`, `__cg_commands.py`, `__cg_logic.py` |
| `utils/Coastal_cogs/CoastalPOICMD.py` | `utils/coastal_poi/poi_main.py`, `__poi_commands.py`, `__poi_logic.py` |
| Inline Google setup in features | `utils/integrations/__google_sheets.py` |
| `utils/!COGTEMP.py`, empty `core/__init__.py` | Preserved under `!archive/` |

The fixed extension manifest excludes all component, integration, archive and package files.
Each entry point adds its cog once. Utilities load once through `cf_main`. No empty view or logic
files were introduced for symmetry. No active feature reads a local image/text asset, so no
unused files were moved into an artificial `data/` directory; legacy assets remain in place.
Archived source keeps historical imports and is intentionally not runnable as an extension.
