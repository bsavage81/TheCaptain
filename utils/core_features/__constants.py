from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EXTENSIONS = (
    "jishaku",
    "utils.core_features.cf_main",
    "utils.admin.bot_management.bm_main",
    "utils.coastal_applications.ca_main",
    "utils.coastal_guide.cg_main",
    "utils.coastal_poi.poi_main",
)
LEGACY_IDS = {
    "CoastalInviteChannel": 443614533815369728,
    "CoastalGuideRole": 1565125349044527184,
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
# Owner-supplied Season 10 Discord CDN image; configurable for future image changes.
LOGO_URL = "https://cdn.discordapp.com/attachments/488792053002534920/1561597489516384357/IMG_8282.png?ex=6ae374be&is=6ae2233e&hm=b3b70039d6d9875d55c2f53827ceaed69ba1b19b5b635a5de7257f2692fa34f0&"
