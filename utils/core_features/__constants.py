from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
EXTENSIONS = (
    "jishaku", "utils.core_features.cf_main", "utils.admin.bot_management.bm_main",
    "utils.coastal_applications.ca_main", "utils.coastal_guide.cg_main", "utils.coastal_poi.poi_main",
)
LEGACY_IDS = {
    "CoastalInviteChannel": 443614533815369728,
    "CoastalGuideRole": 1159549536579096676,
    "CoastalActiveRole": 565587168035340298,
    "CoastalGuideResponses": 517060711202160640,
}
