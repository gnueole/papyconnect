import json
import aiohttp
import asyncio
from datetime import datetime

from config import (
    REGISTRY_PATH,
    ACTIONS_PATH,
    DISABLED_VENDORS_PATH,
    log,
    _is_ip_in_local_subnet,
    _slugify,
    KNOWN_DEVICES
)
from catalogs import DEVICE_CATALOGS
from vendors import (
    VENDORS,
    VENDORS_REGISTRY,
    GenericVendor,
    VENDORS_BY_KEY,
    Vendor
)

# In-memory cache for dynamically discovered actions, keyed by (device_ip, action_name)
DYNAMIC_ACTIONS_CACHE: dict[str, dict[str, dict]] = {}

def _get_device_vendor_name(device: dict) -> str:
    """Determine vendor name from device dict, with fallback logic based on type/name."""
    v = device.get("vendor")
    if v and v != "Generic":
        v_lower = v.lower()
        if "sony" in v_lower:
            return "sony_bravia_tv"
        if "denon" in v_lower:
            return "denon_amplifier"
        if "marantz" in v_lower:
            return "marantz_amplifier"
        if "lg" in v_lower:
            return "lg_tv"
        if "sharp" in v_lower:
            return "sharp_tv"
        if "samsung" in v_lower:
            return "samsung_tv"
        if "hue" in v_lower:
            return "philips_hue"
        if "sonos" in v_lower:
            return "sonos"
        if "musiccast" in v_lower or "yamaha" in v_lower:
            return "yamaha_musiccast"
        if "roku" in v_lower:
            return "roku"
        if "wiz" in v_lower:
            return "philips_wiz"
        if "bbox" in v_lower:
            return "bbox"
        if "google" in v_lower or "cast" in v_lower:
            return "google_home"
        if "xbox" in v_lower:
            return "xbox"
        if "playstation" in v_lower or "ps5" in v_lower or "ps4" in v_lower:
            return "playstation"
        return v
        
    dtype = device.get("type", "").lower()
    if dtype == "google_home":
        return "google_home"
    if dtype in ["sony_bravia_tv", "tv"]:
        return "sony_bravia_tv"
    if dtype in ["amplifier", "denon_amplifier"]:
        return "denon_amplifier"
    if dtype == "marantz_amplifier":
        return "marantz_amplifier"
    if dtype == "lg_tv":
        return "lg_tv"
    if dtype == "sharp_tv":
        return "sharp_tv"
    if dtype == "samsung_tv":
        return "samsung_tv"
    if dtype == "philips_hue":
        return "philips_hue"
    if dtype == "sonos":
        return "sonos"
    if dtype == "yamaha_musiccast":
        return "yamaha_musiccast"
    if dtype == "roku":
        return "roku"
    if dtype == "philips_wiz":
        return "philips_wiz"
    if dtype == "xbox":
        return "xbox"
    if dtype in ["playstation", "ps5", "ps4"]:
        return "playstation"
    if dtype == "bbox":
        return "bbox"
        
    name = device.get("name", "").lower()
    if "sony" in name or "bravia" in name:
        return "sony_bravia_tv"
    if "denon" in name:
        return "denon_amplifier"
    if "marantz" in name:
        return "marantz_amplifier"
    if "lg" in name:
        return "lg_tv"
    if "sharp" in name:
        return "sharp_tv"
    if "samsung" in name:
        return "samsung_tv"
    if "hue" in name:
        return "philips_hue"
    if "sonos" in name:
        return "sonos"
    if "musiccast" in name or "yamaha" in name:
        return "yamaha_musiccast"
    if "roku" in name:
        return "roku"
    if "wiz" in name:
        return "philips_wiz"
    if "bbox" in name:
        return "bbox"
    if "google" in name or "chromecast" in name or "nest" in name:
        return "google_home"
    if "xbox" in name:
        return "xbox"
    if "playstation" in name or "ps5" in name or "ps4" in name:
        return "playstation"
    return "Generic"


def _get_device_vendor(device: dict) -> Vendor:
    """Retrieve Vendor instance for a device."""
    vendor_name = _get_device_vendor_name(device)
    return VENDORS_BY_KEY.get(vendor_name, GenericVendor)


def _get_device_actions(device: dict) -> dict:
    """Get all actions (static catalog + dynamically cached) for a device."""
    dtype = device.get("type")
    ip = device.get("ip")
    actions = {}
    
    catalog_key = _get_device_vendor_name(device)
    if catalog_key not in DEVICE_CATALOGS:
        catalog_key = dtype
        
    if catalog_key in DEVICE_CATALOGS:
        actions.update(DEVICE_CATALOGS[catalog_key].get("actions", {}))
    if ip in DYNAMIC_ACTIONS_CACHE:
        actions.update(DYNAMIC_ACTIONS_CACHE[ip])
    return actions


def _load_registry() -> list[dict]:
    """Load registry devices from disk. Returns empty list on absence/errors."""
    if not REGISTRY_PATH.exists():
        return []
    try:
        content = REGISTRY_PATH.read_text(encoding="utf-8").strip()
        if content:
            return json.loads(content)
    except (json.JSONDecodeError, OSError) as exc:
        log.warning("Registry file unreadable - resetting: %s", exc)
    return []


def _save_registry(devices: list[dict]) -> None:
    """Atomic write of registry devices to registry.json."""
    REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = REGISTRY_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(devices, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(REGISTRY_PATH)


def _load_actions() -> list[dict]:
    """Load configured virtual actions from disk, migrating from previous schemas if needed."""
    if not ACTIONS_PATH.exists():
        return []
    try:
        content = ACTIONS_PATH.read_text(encoding="utf-8").strip()
        if content:
            data = json.loads(content)
            if isinstance(data, list):
                return data
            elif isinstance(data, dict):
                # Migration: Convert dictionary keys (papyconnect_btn_x) back to a flat list
                migrated = []
                for btn_id, val in data.items():
                    if val.get("device_ip") and val.get("target_app"):
                        migrated.append({
                            "id": val.get("id") or btn_id,
                            "title": val.get("title", f"Action {btn_id}"),
                            "icon": val.get("icon", "default"),
                            "device_ip": val.get("device_ip"),
                            "target_app": val.get("target_app"),
                            "state": val.get("state", "inactive")
                        })
                return migrated
    except Exception as exc:
        log.warning("Actions file unreadable - resetting: %s", exc)
    return []


def _save_actions(actions: list[dict]) -> None:
    """Atomic write of virtual actions configuration list."""
    ACTIONS_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = ACTIONS_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(actions, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(ACTIONS_PATH)


def _load_disabled_vendors() -> list[str]:
    """Load globally disabled/deactivated hardware vendors from disk."""
    if not DISABLED_VENDORS_PATH.exists():
        return ["google_home"]  # google_home is deactivated by default
    try:
        content = DISABLED_VENDORS_PATH.read_text(encoding="utf-8").strip()
        if content:
            return json.loads(content)
    except Exception as exc:
        log.warning("Disabled vendors file unreadable - resetting: %s", exc)
    return ["google_home"]  # google_home is deactivated by default


def _save_disabled_vendors(disabled_vendors: list[str]) -> None:
    """Atomic write of disabled vendors list to disabled_vendors.json."""
    DISABLED_VENDORS_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = DISABLED_VENDORS_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(disabled_vendors, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(DISABLED_VENDORS_PATH)


def _merge_devices(devices: list[dict], new_device: dict) -> list[dict]:
    """Merge newly discovered device into registry without overwriting configured custom fields."""
    ip = new_device.get("ip")
    if not _is_ip_in_local_subnet(ip):
        log.warning("Skipping device merge: IP %s is not in the local subnet.", ip)
        return devices
        
    for existing in devices:
        if existing.get("ip") == ip:
            if existing.get("vendor") == "Generic" and new_device.get("vendor") != "Generic":
                existing["name"] = new_device.get("name", existing.get("name"))
                existing["vendor"] = new_device.get("vendor")
                existing["type"] = new_device.get("type", existing.get("type"))
            else:
                existing.setdefault("name", new_device.get("name", "Unknown"))
                existing["type"] = new_device.get("type", existing.get("type", "unknown"))
                existing["vendor"] = new_device.get("vendor", existing.get("vendor", _get_device_vendor_name(existing)))
            existing["variables"] = new_device.get("variables", existing.get("variables", {}))
            existing.setdefault("disabled_apps", [])
            existing["last_seen"] = datetime.utcnow().isoformat()
            return devices
    new_device.setdefault("last_seen", datetime.utcnow().isoformat())
    new_device.setdefault("disabled_apps", [])
    new_device["vendor"] = new_device.get("vendor", _get_device_vendor_name(new_device))
    devices.append(new_device)
    return devices


def _parse_vendor_apps(vendor_name: str, data) -> list[dict]:
    """Parse raw response from discover-schema HTTP request into a list of app dicts."""
    if vendor_name == "sony_bravia_tv":
        if isinstance(data, dict) and "result" in data and isinstance(data["result"], list) and len(data["result"]) > 0:
            return data["result"][0]
            
    elif vendor_name == "bbox":
        apps_list = []
        if isinstance(data, str):
            try:
                import xml.etree.ElementTree as ET
                root = ET.fromstring(data)
                names = list(set(elem.text for elem in root.iter() if elem.tag.endswith('name') and elem.text))
                for app in names:
                    apps_list.append({"title": app, "uri": f"launch_{_slugify(app)}"})
            except Exception:
                pass
        if not apps_list:
            for app in ["Netflix", "YouTube", "Spotify", "Prime Video", "Canal+", "Apple TV", "Arte", "Disney+", "Twitch", "Salto", "VLC", "YouTube Music", "France.tv", "HBO Max", "Mubi"]:
                apps_list.append({"title": app, "uri": f"launch_{_slugify(app)}"})
        return apps_list
        
    elif vendor_name == "google_home":
        return [
            {"title": "Spotify", "uri": "launch_spotify"},
            {"title": "YouTube", "uri": "launch_youtube"},
            {"title": "YouTube Music", "uri": "launch_youtube_music"}
        ]
        
    elif vendor_name == "xbox":
        return [
            {"title": "Netflix", "uri": "launch_netflix"},
            {"title": "YouTube", "uri": "launch_youtube"},
            {"title": "Spotify", "uri": "launch_spotify"},
            {"title": "Prime Video", "uri": "launch_prime_video"},
            {"title": "Canal+", "uri": "launch_canal"},
            {"title": "Apple TV", "uri": "launch_apple_tv"},
            {"title": "Arte", "uri": "launch_arte"},
            {"title": "Disney+", "uri": "launch_disney_plus"},
            {"title": "Twitch", "uri": "launch_twitch"},
            {"title": "Salto", "uri": "launch_salto"},
            {"title": "VLC", "uri": "launch_vlc"},
            {"title": "YouTube Music", "uri": "launch_youtube_music"},
            {"title": "France.tv", "uri": "launch_france_tv"},
            {"title": "HBO Max", "uri": "launch_hbo_max"},
            {"title": "Mubi", "uri": "launch_mubi"},
            {"title": "Plex", "uri": "launch_plex"},
            {"title": "Minecraft", "uri": "launch_minecraft"},
            {"title": "FIFA", "uri": "launch_fifa"},
            {"title": "Halo Infinite", "uri": "launch_halo_infinite"},
            {"title": "Forza Horizon 5", "uri": "launch_forza_horizon_5"}
        ]
        
    elif vendor_name == "playstation":
        return [
            {"title": "Netflix", "uri": "launch_netflix"},
            {"title": "YouTube", "uri": "launch_youtube"},
            {"title": "Spotify Connect", "uri": "launch_spotify"},
            {"title": "Prime Video", "uri": "launch_prime_video"},
            {"title": "Canal+", "uri": "launch_canal"},
            {"title": "Apple TV", "uri": "launch_apple_tv"},
            {"title": "Arte", "uri": "launch_arte"},
            {"title": "Disney+", "uri": "launch_disney_plus"},
            {"title": "Twitch", "uri": "launch_twitch"},
            {"title": "Salto", "uri": "launch_salto"},
            {"title": "VLC", "uri": "launch_vlc"},
            {"title": "YouTube Music", "uri": "launch_youtube_music"},
            {"title": "France.tv", "uri": "launch_france_tv"},
            {"title": "HBO Max", "uri": "launch_hbo_max"},
            {"title": "Mubi", "uri": "launch_mubi"},
            {"title": "Spider-Man 2", "uri": "launch_spider-man_2"},
            {"title": "God of War Ragnarok", "uri": "launch_god_of_war_ragnarok"},
            {"title": "Gran Turismo 7", "uri": "launch_gran_turismo_7"},
            {"title": "Elden Ring", "uri": "launch_elden_ring"}
        ]
        
    return []


async def _fetch_device_apps(device: dict, timeout: float = 1.5) -> list[dict]:
    """Fetch list of installed applications from a device using the VENDORS_REGISTRY configuration."""
    ip = device.get("ip")
    vendor_name = _get_device_vendor_name(device)
    
    if vendor_name not in VENDORS_REGISTRY:
        return []
        
    schema = VENDORS_REGISTRY[vendor_name]["get_apps_request"]
    method = schema.get("method")
    
    if method == "STATIC":
        static_apps = schema.get("apps", [])
        return [{"title": app, "uri": f"launch_{_slugify(app)}"} for app in static_apps]
        
    url = schema.get("url", "").format(device_ip=ip)
    headers = schema.get("headers", {})
    payload = schema.get("payload")
    
    apps_list = []
    try:
        async with aiohttp.ClientSession() as session:
            if method == "POST":
                async with session.post(url, json=payload, headers=headers, timeout=timeout) as resp:
                    if resp.status == 200:
                        text = await resp.text()
                        try:
                            data = json.loads(text)
                            apps_list = _parse_vendor_apps(vendor_name, data)
                        except json.JSONDecodeError:
                            apps_list = _parse_vendor_apps(vendor_name, text)
            elif method == "GET":
                async with session.get(url, headers=headers, timeout=timeout) as resp:
                    if resp.status == 200:
                        text = await resp.text()
                        try:
                            data = json.loads(text)
                            apps_list = _parse_vendor_apps(vendor_name, data)
                        except json.JSONDecodeError:
                            apps_list = _parse_vendor_apps(vendor_name, text)
    except Exception as e:
        log.warning("Failed to fetch applications for %s (%s) @ %s: %s", device.get("name"), vendor_name, ip, e)
        
    if not apps_list:
        if vendor_name == "bbox":
            apps_list = [{"title": app, "uri": f"launch_{_slugify(app)}"} for app in ["Netflix", "YouTube", "Spotify", "Prime Video", "Canal+", "Apple TV", "Arte", "Disney+", "Twitch", "Salto", "VLC", "YouTube Music", "France.tv", "HBO Max", "Mubi"]]
        elif vendor_name == "google_home":
            apps_list = [{"title": "Spotify", "uri": "launch_spotify"}, {"title": "YouTube", "uri": "launch_youtube"}, {"title": "YouTube Music", "uri": "launch_youtube_music"}]
            
    # Normalize Amazon Prime / Prime Video titles to "Prime Video"
    for app in apps_list:
        if isinstance(app, dict) and app.get("title") in ["Amazon Prime", "Prime Video"]:
            app["title"] = "Prime Video"
            if app.get("uri", "").startswith("launch_"):
                app["uri"] = "launch_prime_video"
            
    return apps_list


async def _send_tcp_command(ip: str, port: int, payload: str, timeout: float = 3.0) -> bool:
    """Send a raw TCP command to a target IP and port."""
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(ip, port),
            timeout=timeout
        )
        writer.write(payload.encode("utf-8") if isinstance(payload, str) else payload)
        await writer.drain()
        writer.close()
        await writer.wait_closed()
        return True
    except Exception as e:
        log.error("Failed to send TCP command to %s:%s - %s", ip, port, e)
        return False


async def _send_http_command(url: str, method: str, headers: dict, payload: str, timeout: float = 5.0) -> bool:
    """Send an HTTP request to a target API endpoint."""
    try:
        async with aiohttp.ClientSession() as session:
            data = None
            json_data = None
            if payload:
                try:
                    json_data = json.loads(payload)
                except json.JSONDecodeError:
                    data = payload
            
            async with session.request(
                method=method,
                url=url,
                headers=headers,
                json=json_data,
                data=data,
                timeout=timeout
            ) as response:
                return response.status in [200, 201, 202, 204]
    except Exception as e:
        log.error("Failed to send HTTP request to %s - %s", url, e)
        return False
