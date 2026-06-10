import json
from pathlib import Path

VENDORS_JSON_PATH = Path(__file__).parent / "vendors.json"

class Vendor:
    def __init__(self, key: str, data: dict):
        self.key = key
        self.name = data.get("name", "Generic")
        self.version = data.get("version", "1.0")
        self.description = data.get("description", "")
        self.type = data.get("type", "unknown")
        self.api_calls = data.get("api_calls", {})
        self.get_apps_request = data.get("get_apps_request")
        self.launch_action_template = data.get("launch_action_template")
        self.keywords = data.get("keywords", [])

    def get_api_calls(self) -> dict:
        return self.api_calls

    def get_launch_action_payload(self, app_uri: str) -> dict | None:
        if not self.launch_action_template:
            return None
        
        # Serialize to json string, format placeholders, and deserialize back
        raw = json.dumps(self.launch_action_template)
        formatted = raw.replace("{app_uri}", app_uri)
        
        # For Bbox, it also needs slugified app names like f"/apps/{app_name}"
        # We can format {app_name} by extracting from app_uri:
        app_name = app_uri
        if app_uri.startswith("launch_"):
            app_name = app_uri[7:].capitalize()
            if app_name.lower() == "youtube":
                app_name = "YouTube"
            elif app_name.lower() == "netflix":
                app_name = "Netflix"
            elif app_name.lower() == "spotify":
                app_name = "Spotify"
        formatted = formatted.replace("{app_name}", app_name)
        
        # For Samsung TV, we need to map app slug / URI to its appId:
        if self.key == "samsung_tv":
            samsung_app_ids = {
                "netflix": "11101200001",
                "youtube": "111299001912",
                "spotify": "3201606009684",
                "prime_video": "3201512006785",
                "disney_plus": "3201901017640",
                "apple_tv": "3201807016597",
                "plex": "3201512006963",
                "canal": "3201511006428",
                "canal_": "3201511006428",
                "twitch": "3201710015037",
                "vlc": "3201706012437",
                "hbo_max": "3202301029760",
                "youtube_music": "3201908019041"
            }
            slug = app_uri.replace("launch_", "").lower().strip()
            # If the slug is already an ID (numeric), use it directly
            if slug.isdigit():
                app_id = slug
            else:
                app_id = samsung_app_ids.get(slug, "11101200001") # Netflix default fallback
            formatted = formatted.replace("{app_id}", app_id)
            
        return json.loads(formatted)


VENDORS: dict[str, Vendor] = {}
VENDORS_BY_KEY: dict[str, Vendor] = {}
VENDORS_REGISTRY: dict[str, dict] = {}
GenericVendor = Vendor("Generic", {
    "name": "Generic",
    "version": "N/A",
    "description": "Generic unsupported hardware vendor.",
    "type": "unknown",
    "api_calls": {}
})

def load_vendors():
    try:
        if VENDORS_JSON_PATH.exists():
            with open(VENDORS_JSON_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                for key, val in data.items():
                    vendor_inst = Vendor(key, val)
                    VENDORS[val.get("name", key)] = vendor_inst
                    VENDORS_BY_KEY[key] = vendor_inst
                    if val.get("get_apps_request"):
                        VENDORS_REGISTRY[key] = {
                            "vendor": key,
                            "get_apps_request": val["get_apps_request"]
                        }
    except Exception as e:
        pass

# Load vendors on startup
load_vendors()

# Ensure Generic is in VENDORS
VENDORS["Generic"] = GenericVendor
VENDORS_BY_KEY["Generic"] = GenericVendor
