from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
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

SHEET_DEFAULTS = {
    "application_sheet": "CCS10 Realm Application",
    "markers_sheet": "Coastal Markers S10",
}
CAPTAIN_SERVICE_ACCOUNT = "thecaptain@thecaptain-513018.iam.gserviceaccount.com"
REALM_NAME = "Coastal Craft Season 10: The Mighty Mesa Reborn"

GUIDE_DEFAULTS = {
    "web_url": "https://docs.google.com/document/d/1FGK84rUyrC6LX0UrnW7IxzjupYPEbOCo7ccpQlSmvu8/edit?usp=drive_link",
    "pdf_url": "https://drive.google.com/file/d/1zMmjQTzZeEHUHgjxNZsNnGe9ubw-3QCW/view?usp=drive_link",
    "question": "Who knows?",
    "answer": "armadillo",
    "answer_match": "contains",
}
# Direct image form of the owner-supplied Drive file; public Discord fetching needs verification.
LOGO_URL = "https://drive.google.com/uc?export=view&id=19swOQMBDP42z9b15DdBONkPDTgQcRRbo"
