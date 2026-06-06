"""
PapyConnect — Dynamic IoT Service Registry
==========================================
FastAPI backend for PapyConnect network management and action resolution.

Exposed Routes:
  GET    /                       → English Dashboard HTML
  GET    /api/devices            → Active IoT Registry with live status ping
  POST   /api/scan               → Scan local network via mDNS and ping known devices
  POST   /api/devices            → Manually register a device
  DELETE /api/devices/{ip}       → Remove a registered device
  GET    /api/actions            → List all configured virtual actions
  POST   /api/actions            → Configure/register a virtual action
  DELETE /api/actions/{action_id}→ Remove a virtual action
  POST   /api/actions/{action_id}/execute → Resolve action execution contract for n8n
"""

import asyncio
import aiohttp
import json
import logging
import socket
from datetime import datetime
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from zeroconf import ServiceBrowser, Zeroconf
from zeroconf.asyncio import AsyncZeroconf

# ─────────────────────────────────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────────────────────────────────
REGISTRY_PATH = Path("./data/registry.json")
ACTIONS_PATH = Path("./data/actions.json")
MDNS_SCAN_DURATION = 3.0

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("papyconnect")

# ─────────────────────────────────────────────────────────────────────────────
# Device Action Catalogs
# ─────────────────────────────────────────────────────────────────────────────
DEVICE_CATALOGS = {
    "amplifier": {
        "icon": "amplifier",
        "tuto": """
            <h3>🔊 Denon / Marantz Receiver Configuration (Telnet)</h3>
            <p>Control is executed via raw TCP commands on port 23.</p>
            <ul style="text-align: left; margin-top: 8px;">
                <li><b>Required:</b> Set the <i>Network Control</i> option to <b>Always On</b> in the receiver settings (Setup ➔ Network). This prevents standby cold starts.</li>
                <li>The command <code style="color: #ff9800;">SINET</code> powers the receiver on and switches to the Network/Spotify Connect input.</li>
            </ul>
        """,
        "actions": {
            "launch_spotify": {
                "protocol": "TCP",
                "port": 23,
                "payload": "SINET\r"
            },
            "power_off": {
                "protocol": "TCP",
                "port": 23,
                "payload": "PWSTANDBY\r"
            }
        }
    },
    "sony_bravia_tv": {
        "icon": "tv",
        "tuto": """
            <h3>📺 Sony Bravia TV Configuration (Pre-Shared Key)</h3>
            <p>To control the TV without complex OAuth tokens:</p>
            <ul style="text-align: left; margin-top: 8px;">
                <li>Go to <b>Settings ➔ Network ➔ Home Network</b>.</li>
                <li>Enable the <b>Pre-Shared Key (PSK)</b> option.</li>
                <li>Set the secret key to: <code style="color: #ff9800; background: #222; padding: 2px 6px; border-radius: 4px;">0000</code></li>
                <li>Go to <b>IP Control</b> settings and enable <i>Simple IP Control</i>.</li>
            </ul>
        """,
        "actions": {
            "power_on": {
                "protocol": "HTTP",
                "method": "POST",
                "port": 80,
                "path": "/sony/system",
                "headers": {
                    "X-Auth-PSK": "0000",
                    "Content-Type": "application/json"
                },
                "payload": "{\"method\":\"setPowerStatus\",\"version\":\"1.0\",\"id\":1,\"params\":[{\"status\":true}]}"
            },
            "launch_netflix": {
                "protocol": "HTTP",
                "method": "POST",
                "port": 80,
                "path": "/sony/appControl",
                "headers": {
                    "X-Auth-PSK": "0000",
                    "Content-Type": "application/json"
                },
                "payload": "{\"method\":\"setActiveApp\",\"version\":\"1.0\",\"id\":1,\"params\":[{\"uri\":\"com.sony.dtv.com.netflix.ninja.com.netflix.ninja.MainActivity\"}]}"
            },
            "launch_youtube": {
                "protocol": "HTTP",
                "method": "POST",
                "port": 80,
                "path": "/sony/appControl",
                "headers": {
                    "X-Auth-PSK": "0000",
                    "Content-Type": "application/json"
                },
                "payload": "{\"method\":\"setActiveApp\",\"version\":\"1.0\",\"id\":1,\"params\":[{\"uri\":\"com.sony.dtv.com.google.android.youtube.tv.com.google.android.youtube.tv.MainActivity\"}]}"
            },
            "launch_spotify": {
                "protocol": "HTTP",
                "method": "POST",
                "port": 80,
                "path": "/sony/appControl",
                "headers": {
                    "X-Auth-PSK": "0000",
                    "Content-Type": "application/json"
                },
                "payload": "{\"method\":\"setActiveApp\",\"version\":\"1.0\",\"id\":1,\"params\":[{\"uri\":\"com.sony.dtv.com.spotify.tv.android.com.spotify.tv.android.AboutActivity\"}]}"
            },
            "power_off": {
                "protocol": "HTTP",
                "method": "POST",
                "port": 80,
                "path": "/sony/system",
                "headers": {
                    "X-Auth-PSK": "0000",
                    "Content-Type": "application/json"
                },
                "payload": "{\"method\":\"setPowerStatus\",\"version\":\"1.0\",\"id\":1,\"params\":[{\"status\":false}]}"
            }
        }
    }
}

# Add "tv" as an alias to the "sony_bravia_tv" catalog to support generic discovered devices
DEVICE_CATALOGS["tv"] = DEVICE_CATALOGS["sony_bravia_tv"]

# Known devices defined with specific environment/location variables
KNOWN_DEVICES: dict[str, dict] = {
    "192.168.1.193": {
        "name": "Denon AVC-X3800H Salon",
        "type": "amplifier",
        "ip": "192.168.1.193",
        "variables": {
            "zone": "MAIN",
            "max_volume": 80
        }
    },
    "192.168.1.200": {
        "name": "Denon de Louistib (Superior Model)",
        "type": "amplifier",
        "ip": "192.168.1.200",
        "variables": {
            "zone": "MAIN",
            "max_volume": 90
        }
    },
    "192.168.1.100": {
        "name": "Sony Bravia TV Salon",
        "type": "sony_bravia_tv",
        "ip": "192.168.1.100",
        "variables": {}
    }
}

# ─────────────────────────────────────────────────────────────────────────────
# JSON Persistence Helpers
# ─────────────────────────────────────────────────────────────────────────────

# In-memory cache for dynamically discovered actions, keyed by (device_ip, action_name)
DYNAMIC_ACTIONS_CACHE: dict[str, dict[str, dict]] = {}

import re

def _slugify(text: str) -> str:
    """Helper to convert application titles into clean URL/action ID slugs."""
    text = text.lower()
    text = re.sub(r'[^a-z0-9]+', '_', text)
    return text.strip('_')


async def _fetch_sony_apps(ip: str, timeout: float = 1.5) -> list[dict]:
    """Fetch the list of installed applications from a Sony Bravia TV using PSK."""
    url = f"http://{ip}/sony/appControl"
    headers = {
        "X-Auth-PSK": "0000",
        "Content-Type": "application/json"
    }
    payload = {
        "method": "getApplicationList",
        "version": "1.0",
        "id": 1,
        "params": []
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=headers, timeout=timeout) as response:
                if response.status == 200:
                    data = await response.json()
                    if "result" in data and isinstance(data["result"], list) and len(data["result"]) > 0:
                        return data["result"][0]
    except Exception as e:
        log.warning("Failed to fetch Sony apps from %s: %s", ip, e)
    return []


def _get_device_actions(device: dict) -> dict:
    """Get all actions (static catalog + dynamically cached) for a device."""
    dtype = device.get("type")
    ip = device.get("ip")
    actions = {}
    if dtype in DEVICE_CATALOGS:
        actions.update(DEVICE_CATALOGS[dtype].get("actions", {}))
    if ip in DYNAMIC_ACTIONS_CACHE:
        actions.update(DYNAMIC_ACTIONS_CACHE[ip])
    return actions


def _load_registry() -> list[dict]:
    """Load registry devices from disk. Returns empty list on absence/errors."""
    try:
        if REGISTRY_PATH.exists() and REGISTRY_PATH.stat().st_size > 2:
            return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
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
    try:
        if ACTIONS_PATH.exists() and ACTIONS_PATH.stat().st_size > 2:
            data = json.loads(ACTIONS_PATH.read_text(encoding="utf-8"))
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


def _merge_devices(devices: list[dict], new_device: dict) -> list[dict]:
    """Merge newly discovered device into registry without overwriting configured custom fields."""
    for existing in devices:
        if existing.get("ip") == new_device.get("ip"):
            existing.setdefault("name", new_device.get("name", "Unknown"))
            existing["type"] = new_device.get("type", existing.get("type", "unknown"))
            existing["variables"] = new_device.get("variables", existing.get("variables", {}))
            existing["last_seen"] = datetime.utcnow().isoformat()
            return devices
    new_device.setdefault("last_seen", datetime.utcnow().isoformat())
    devices.append(new_device)
    return devices

# ─────────────────────────────────────────────────────────────────────────────
# Async Network Ping
# ─────────────────────────────────────────────────────────────────────────────

async def _ping_device(ip: str, timeout: float = 1.5) -> bool:
    """Return True if device answers an ICMP ping within timeout seconds."""
    try:
        proc = await asyncio.create_subprocess_exec(
            "ping", "-c", "1", "-W", str(max(1, int(timeout))), ip,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await asyncio.wait_for(proc.wait(), timeout=timeout + 1.5)
        return proc.returncode == 0
    except Exception:
        return False


async def _enrich_status(devices: list[dict]) -> list[dict]:
    """Ping all registry devices in parallel and inject connection status."""
    if not devices:
        return devices
    statuses = await asyncio.gather(*[_ping_device(d["ip"]) for d in devices])
    for device, online in zip(devices, statuses):
        device["status"] = "online" if online else "offline"
    return devices


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

# ─────────────────────────────────────────────────────────────────────────────
# mDNS Device Discovery
# ─────────────────────────────────────────────────────────────────────────────

class _MDNSListener:
    """Collect cast devices discovered during scan window."""

    def __init__(self):
        self.found: list[dict] = []

    def add_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        info = zc.get_service_info(type_, name)
        if not info or not info.addresses:
            return
        ip = socket.inet_ntoa(info.addresses[0])
        raw_name = info.properties.get(b"fn", b"")
        label = raw_name.decode(errors="replace") if raw_name else name.split(".")[0]
        log.info("mDNS discovered: %s @ %s", label, ip)
        self.found.append({"name": label, "ip": ip, "type": "tv", "source": "mdns"})

    def remove_service(self, *_): pass
    def update_service(self, *_): pass


async def _scan_mdns() -> list[dict]:
    """Scan local network for Chromecast/Android TVs."""
    listener = _MDNSListener()
    azc = AsyncZeroconf()
    ServiceBrowser(azc.zeroconf, "_googlecast._tcp.local.", listener)
    await asyncio.sleep(MDNS_SCAN_DURATION)
    await azc.async_close()
    return listener.found


async def _scan_known_devices() -> list[dict]:
    """Check status of statically known devices."""
    online = []
    for ip, meta in KNOWN_DEVICES.items():
        if await _ping_device(ip):
            online.append(dict(meta))
    return online


async def _full_scan() -> None:
    """Perform full mDNS + Ping discovery and update the local registry."""
    log.info("Starting network scan (mDNS %ss + ping known)...", int(MDNS_SCAN_DURATION))
    mdns_hits, known_hits = await asyncio.gather(
        _scan_mdns(), _scan_known_devices()
    )
    devices = _load_registry()
    for d in mdns_hits + known_hits:
        devices = _merge_devices(devices, d)
    _save_registry(devices)
    log.info("Network scan completed — %d device(s) registered.", len(devices))

# ─────────────────────────────────────────────────────────────────────────────
# FastAPI Application setup
# ─────────────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="PapyConnect",
    description="Dynamic IoT Service Registry for n8n workflows",
    version="1.3.0",
)

_TEMPLATES_DIR = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    log.warning("HTTP %s error on %s %s: %s", exc.status_code, request.method, request.url.path, exc.detail)
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    log.error("Validation error on %s %s: %s", request.method, request.url.path, exc.errors())
    return JSONResponse(
        status_code=422,
        content={"detail": exc.errors()},
    )


@app.on_event("startup")
async def _startup() -> None:
    """Ensure persistence paths are created and populate default actions if empty."""
    REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not REGISTRY_PATH.exists():
        _save_registry([])
        log.info("Registry file initialized: %s", REGISTRY_PATH.resolve())
    if not ACTIONS_PATH.exists():
        default_actions = [
            {
                "id": "netflix_salon",
                "title": "Netflix (Salon)",
                "icon": "netflix",
                "device_ip": "192.168.1.100",
                "target_app": "launch_netflix"
            },
            {
                "id": "spotify_salon",
                "title": "Spotify (Salon)",
                "icon": "spotify",
                "device_ip": "192.168.1.193",
                "target_app": "launch_spotify"
            }
        ]
        _save_actions(default_actions)
        log.info("Default actions initialized: %s", ACTIONS_PATH.resolve())
    log.info("PapyConnect service started successfully on http://0.0.0.0:8000")


# ── Web UI Dashboard ─────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse, summary="English Web Dashboard UI")
async def dashboard(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


# ── Devices API ──────────────────────────────────────────────────────────────

@app.get("/api/devices", summary="List registered devices with live status")
async def get_devices():
    """Retrieve all devices from local registry, checking status in real time."""
    devices = await _enrich_status(_load_registry())
    
    import copy
    
    async def process_device(device):
        dtype = device.get("type")
        if dtype in DEVICE_CATALOGS:
            catalog = copy.deepcopy(DEVICE_CATALOGS[dtype])
            device["catalog"] = catalog
            
            # If it's a TV and online, fetch apps dynamically and merge
            if dtype in ["sony_bravia_tv", "tv"] and device.get("status") == "online":
                apps = await _fetch_sony_apps(device["ip"])
                device_dynamic = {}
                for app in apps:
                    app_title = app.get("title")
                    app_uri = app.get("uri")
                    if app_title and app_uri:
                        slug = _slugify(app_title)
                        action_key = f"launch_{slug}"
                        action_payload = {
                            "protocol": "HTTP",
                            "method": "POST",
                            "port": 80,
                            "path": "/sony/appControl",
                            "headers": {
                                "X-Auth-PSK": "0000",
                                "Content-Type": "application/json"
                            },
                            "payload": json.dumps({
                                "method": "setActiveApp",
                                "version": "1.0",
                                "id": 1,
                                "params": [{"uri": app_uri}]
                            })
                        }
                        catalog["actions"][action_key] = action_payload
                        device_dynamic[action_key] = action_payload
                
                # Cache the dynamic actions for lookup during execution/config fetch
                if device_dynamic:
                    DYNAMIC_ACTIONS_CACHE[device["ip"]] = device_dynamic
                    
    await asyncio.gather(*[process_device(d) for d in devices])
    return devices


class DeviceIn(BaseModel):
    name: str
    ip: str
    type: str = "unknown"
    variables: dict = {}


@app.post("/api/devices", status_code=201, summary="Manually register an IoT device")
async def add_device(body: DeviceIn):
    """Add or update an IoT device manually in the registry database."""
    devices = _merge_devices(_load_registry(), body.model_dump())
    _save_registry(devices)
    log.info("Device manually configured: %s (@ %s)", body.name, body.ip)
    return {"ok": True, "total": len(devices)}


@app.delete("/api/devices/{ip}", summary="Remove a device from registry")
async def delete_device(ip: str):
    """Delete a device configuration by its IP address."""
    devices = _load_registry()
    filtered = [d for d in devices if d.get("ip") != ip]
    if len(filtered) == len(devices):
        log.warning("Deletion failed: IP %s not found in registry", ip)
        raise HTTPException(status_code=404, detail=f"Device with IP {ip} not found.")
    _save_registry(filtered)
    log.info("Device removed from registry: %s", ip)
    return {"ok": True, "removed": ip}


@app.post("/api/scan", summary="Trigger mDNS and ping network scan")
async def trigger_scan(bg: BackgroundTasks):
    """Scan local network asynchronously and update registered devices registry."""
    bg.add_task(_full_scan)
    return {
        "ok": True,
        "message": f"Network scan triggered (mDNS {int(MDNS_SCAN_DURATION)}s + ping known)",
    }


# ── Direct Device Commands ───────────────────────────────────────────────────

@app.post("/api/devices/{ip}/action/{action_name}", summary="Directly execute an action on a device")
async def run_device_action(ip: str, action_name: str):
    """Execute a catalog action directly on a target IP (interpolating target variables)."""
    devices = _load_registry()
    device = next((d for d in devices if d.get("ip") == ip), None)
    
    if not device and ip in KNOWN_DEVICES:
        device = KNOWN_DEVICES[ip]
        
    if not device:
        log.warning("Execution failed: Device IP %s not found in database", ip)
        raise HTTPException(status_code=404, detail=f"Device with IP {ip} not found.")
        
    dtype = device.get("type")
    if dtype not in DEVICE_CATALOGS:
        log.warning("Execution failed: No catalog action defined for device type %s", dtype)
        raise HTTPException(status_code=400, detail=f"No action available for device type '{dtype}'.")
        
    actions = _get_device_actions(device)
    if action_name not in actions:
        log.warning("Execution failed: Action '%s' not defined for type '%s'", action_name, dtype)
        raise HTTPException(status_code=404, detail=f"Action '{action_name}' not defined for type '{dtype}'.")
        
    action_meta = actions[action_name]
    protocol = action_meta.get("protocol")
    port = action_meta.get("port")
    payload = action_meta.get("payload", "")
    
    variables = device.get("variables", {})
    if isinstance(payload, str) and variables:
        try:
            payload = payload.format(**variables)
        except Exception as e:
            log.warning("Failed formatting command payload for %s: %s", ip, e)
            
    if protocol == "TCP":
        log.info("Sending TCP command to %s:%s (payload: %r)", ip, port, payload)
        success = await _send_tcp_command(ip, port, payload)
        if not success:
            log.warning("TCP command to %s:%s failed", ip, port)
            raise HTTPException(status_code=502, detail=f"Could not reach device on TCP port {port}.")
        log.info("TCP command sent successfully to %s:%s", ip, port)
        return {"ok": True, "message": f"Action '{action_name}' sent successfully via TCP to {ip}."}
        
    elif protocol == "HTTP":
        path = action_meta.get("path", "")
        url = f"http://{ip}:{port}{path}"
        headers = action_meta.get("headers", {})
        method = action_meta.get("method", "POST")
        log.info("Sending HTTP %s request to %s (headers: %r, payload: %r)", method, url, headers, payload)
        success = await _send_http_command(url, method, headers, payload)
        if not success:
            log.warning("HTTP %s command to %s failed", method, url)
            raise HTTPException(status_code=502, detail=f"Could not reach device on HTTP url {url}.")
        log.info("HTTP request completed successfully on %s", url)
        return {"ok": True, "message": f"Action '{action_name}' sent successfully via HTTP to {ip}."}
        
    else:
        log.warning("Execution failed: protocol %s not supported", protocol)
        raise HTTPException(status_code=400, detail=f"Protocol '{protocol}' not supported.")


@app.get("/api/devices/{ip}/action/{action_name}/config", summary="Retrieve raw action configuration for n8n")
async def get_device_action_config(ip: str, action_name: str):
    """Return resolved action configuration contract without executing (consumed by n8n)."""
    devices = _load_registry()
    device = next((d for d in devices if d.get("ip") == ip), None)
    if not device and ip in KNOWN_DEVICES:
        device = KNOWN_DEVICES[ip]
        
    if not device:
        raise HTTPException(status_code=404, detail=f"Device with IP {ip} not found.")
        
    dtype = device.get("type")
    if dtype not in DEVICE_CATALOGS:
        raise HTTPException(status_code=400, detail=f"No action catalog available for type '{dtype}'.")
        
    actions = _get_device_actions(device)
    if action_name not in actions:
        raise HTTPException(status_code=404, detail=f"Action '{action_name}' not defined for type '{dtype}'.")
        
    action_meta = actions[action_name]
    payload = action_meta.get("payload", "")
    variables = device.get("variables", {})
    if isinstance(payload, str) and variables:
        try:
            payload = payload.format(**variables)
        except Exception as e:
            log.warning("Failed formatting payload config for %s: %s", ip, e)
            
    config = {
        "ip": ip,
        "name": device.get("name"),
        "type": dtype,
        "action": action_name,
        "protocol": action_meta.get("protocol"),
        "port": action_meta.get("port"),
        "payload": payload
    }
    
    if action_meta.get("protocol") == "HTTP":
        config["method"] = action_meta.get("method", "POST")
        config["path"] = action_meta.get("path", "")
        config["url"] = f"http://{ip}:{action_meta.get('port', 80)}{action_meta.get('path', '')}"
        config["headers"] = action_meta.get("headers", {})
        
    return config


# ── Virtual Actions API ──────────────────────────────────────────────────────

@app.get("/api/icons/{filename}", summary="Serve console active/inactive icons")
def get_icon(filename: str):
    import os
    from fastapi import Response
    safe_filename = "".join(c for c in filename if c.isalnum() or c in "._-")
    path = os.path.join("app", "static", "icons", safe_filename)
    if not os.path.exists(path):
        if "_active" in safe_filename:
            path = os.path.join("app", "static", "icons", "default_active.png")
        else:
            path = os.path.join("app", "static", "icons", "default.png")
    if os.path.exists(path):
        with open(path, "rb") as f:
            return Response(content=f.read(), media_type="image/png")
    return Response(content=b"", media_type="image/png")


class ActionIn(BaseModel):
    id: str
    title: str
    icon: str
    device_ip: str
    target_app: str


@app.get("/api/actions", summary="List all configured virtual actions")
async def get_actions():
    """Retrieve list of all registered virtual actions."""
    return _load_actions()


@app.post("/api/actions", status_code=201, summary="Register or update a virtual action")
async def create_action(body: ActionIn):
    """Save or update a virtual action profile in actions.json database."""
    log.info("Received configuration request for action '%s' (IP: %s, App: %s, Title: %s)", body.id, body.device_ip, body.target_app, body.title)
    actions = _load_actions()
    
    # Remove existing action if updating, then append new config
    actions = [a for a in actions if a["id"] != body.id]
    actions.append({
        "id": body.id,
        "title": body.title,
        "icon": body.icon,
        "device_ip": body.device_ip,
        "target_app": body.target_app,
        "state": "inactive"
    })
    
    _save_actions(actions)
    log.info("Action '%s' registered successfully (Title: %s, Icon: %s)", body.id, body.title, body.icon)
    return {"ok": True, "total": len(actions)}


@app.delete("/api/actions/{action_id}", summary="Remove a virtual action")
async def delete_action(action_id: str):
    """Delete a virtual action mapping profile by its ID."""
    log.info("Received request to delete action '%s'", action_id)
    actions = _load_actions()
    filtered = [a for a in actions if a["id"] != action_id]
    if len(filtered) == len(actions):
        log.warning("Deletion failed: Action '%s' not found in database", action_id)
        raise HTTPException(status_code=404, detail=f"Action '{action_id}' not found.")
    _save_actions(filtered)
    log.info("Action '%s' deleted successfully", action_id)
    return {"ok": True, "removed": action_id}


@app.post("/api/actions/execute/{action_id}", summary="Resolve contract and execute action toggle")
@app.post("/api/actions/{action_id}/execute", summary="Resolve contract and execute action toggle (compatibility)")
async def execute_action(action_id: str):
    """Resolve action, perform state toggle (power_off if active, otherwise target_app), and return n8n contract."""
    actions = _load_actions()
    action = next((a for a in actions if a["id"] == action_id), None)
    if not action:
        log.warning("Execution failed: Action '%s' not found", action_id)
        raise HTTPException(status_code=404, detail=f"Action '{action_id}' not found.")
        
    ip = action["device_ip"]
    
    # Toggle state logic
    current_state = action.get("state", "inactive")
    if current_state == "active":
        action_name = "power_off"
        action["state"] = "inactive"
    else:
        action_name = action["target_app"]
        action["state"] = "active"
        # Turn off other actions mapped to the same physical device IP
        for act in actions:
            if act["id"] != action_id and act.get("device_ip") == ip:
                act["state"] = "inactive"
                
    _save_actions(actions)
    log.info("Toggled action state for '%s' (New State: %s, Resolved Action: %s)", action_id, action["state"], action_name)
    
    # Retrieve target device information
    devices = _load_registry()
    device = next((d for d in devices if d.get("ip") == ip), None)
    if not device and ip in KNOWN_DEVICES:
        device = KNOWN_DEVICES[ip]
        
    if not device:
        log.warning("Execution failed: Target device IP %s not found in registry", ip)
        raise HTTPException(status_code=404, detail=f"Target device with IP {ip} not found.")
        
    dtype = device.get("type")
    if dtype not in DEVICE_CATALOGS:
        raise HTTPException(status_code=400, detail=f"No action catalog available for type '{dtype}'.")
        
    actions_cat = _get_device_actions(device)
    if action_name not in actions_cat:
        raise HTTPException(status_code=404, detail=f"Action '{action_name}' not defined for type '{dtype}'.")
        
    action_meta = actions_cat[action_name]
    payload = action_meta.get("payload", "")
    variables = device.get("variables", {})
    if isinstance(payload, str) and variables:
        try:
            payload = payload.format(**variables)
        except Exception as e:
            log.warning("Failed formatting execution payload config for %s: %s", ip, e)
            
    config = {
        "action_id": action_id,
        "ip": ip,
        "name": device.get("name"),
        "type": dtype,
        "action": action_name,
        "protocol": action_meta.get("protocol"),
        "port": action_meta.get("port"),
        "payload": payload
    }
    
    if action_meta.get("protocol") == "HTTP":
        config["method"] = action_meta.get("method", "POST")
        config["path"] = action_meta.get("path", "")
        config["url"] = f"http://{ip}:{action_meta.get('port', 80)}{action_meta.get('path', '')}"
        config["headers"] = action_meta.get("headers", {})
        
    return config
