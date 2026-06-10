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

import sys
import copy
import asyncio
import ipaddress
import socket
from pathlib import Path

# Add app directory to sys.path to ensure import compatibility across all deployment environments
sys.path.append(str(Path(__file__).parent))

from fastapi import BackgroundTasks, FastAPI, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel

# Import modular components
from config import (
    REGISTRY_PATH,
    ACTIONS_PATH,
    DISABLED_VENDORS_PATH,
    MDNS_SCAN_DURATION,
    log,
    KNOWN_DEVICES,
    _is_ip_in_local_subnet,
    _get_local_subnet,
    _slugify
)
from catalogs import DEVICE_CATALOGS
from vendors import VENDORS, VENDORS_REGISTRY
from discovery import _full_scan, _enrich_status
from actions import (
    _load_registry,
    _save_registry,
    _load_actions,
    _save_actions,
    _load_disabled_vendors,
    _save_disabled_vendors,
    _merge_devices,
    _get_device_vendor,
    _get_device_vendor_name,
    _get_device_actions,
    _fetch_device_apps,
    _send_tcp_command,
    _send_http_command,
    _send_websocket_command,
    DYNAMIC_ACTIONS_CACHE
)

# ─────────────────────────────────────────────────────────────────────────────
# FastAPI Application setup
# ─────────────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="PapyConnect",
    description="Dynamic IoT Service Registry for n8n workflows",
    version="1.4.0",
)

_TEMPLATES_DIR = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))

_STATIC_DIR = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")


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
        _save_actions([])
        log.info("Actions file initialized empty: %s", ACTIONS_PATH.resolve())
        
    if not DISABLED_VENDORS_PATH.exists():
        _save_disabled_vendors(["google_home"])
        log.info("Disabled vendors file initialized: %s", DISABLED_VENDORS_PATH.resolve())
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
    disabled_vendors = _load_disabled_vendors()
    
    async def process_device(device):
        dtype = device.get("type")
        device.setdefault("disabled_apps", [])
        
        vendor_name = _get_device_vendor_name(device)
        vendor_deactivated = vendor_name in disabled_vendors
        device["vendor_deactivated"] = vendor_deactivated
        
        # Initialize default empty apps list and status flag
        device["available_apps"] = []
        device["apps_failed"] = False
        
        # Fetch available apps from vendor_registry discover-schema
        schema = VENDORS_REGISTRY.get(vendor_name, {}).get("get_apps_request", {})
        all_apps = []
        if schema and device.get("vendor") != "Generic" and not vendor_deactivated:
            is_static = schema.get("method") == "STATIC"
            is_online = device.get("status") == "online"
            if is_static or is_online:
                all_apps = await _fetch_device_apps(device)
                if not is_static and not all_apps:
                    device["apps_failed"] = True
        
        # Filter active apps for available_apps
        disabled = device.get("disabled_apps", [])
        disabled_slugs = {_slugify(d) for d in disabled}
        active_apps = []
        for app in all_apps:
            title = app["title"] if isinstance(app, dict) else app
            if _slugify(title) not in disabled_slugs:
                active_apps.append(app)
        device["available_apps"] = [app["title"] if isinstance(app, dict) else app for app in active_apps]
        
        catalog_key = _get_device_vendor_name(device)
        if catalog_key not in DEVICE_CATALOGS:
            catalog_key = dtype
            
        if catalog_key in DEVICE_CATALOGS:
            catalog = copy.deepcopy(DEVICE_CATALOGS[catalog_key])
            device["catalog"] = catalog
            
            # Deactivate all catalog actions if the vendor integration is deactivated
            if vendor_deactivated:
                for act in catalog.get("actions", {}).values():
                    act["deactivated"] = True
            
            # Merge dynamic launch actions if the device is online and vendor supports execution
            if all_apps:
                vendor_cls = _get_device_vendor(device)
                device_dynamic = {}
                for app in all_apps:
                    if isinstance(app, dict):
                        app_title = app.get("title")
                        app_uri = app.get("uri")
                        if app_title and app_uri:
                            slug = _slugify(app_title)
                            action_key = f"launch_{slug}"
                            action_payload = vendor_cls.get_launch_action_payload(app_uri)
                            if action_payload:
                                if _slugify(app_title) in disabled_slugs:
                                    action_payload["deactivated"] = True
                                catalog["actions"][action_key] = action_payload
                                device_dynamic[action_key] = action_payload
                
                if device_dynamic:
                    DYNAMIC_ACTIONS_CACHE[device["ip"]] = device_dynamic
                    
    await asyncio.gather(*[process_device(d) for d in devices])
    return devices


class DeviceIn(BaseModel):
    name: str
    ip: str
    type: str = "unknown"
    vendor: str = "Generic"
    variables: dict = {}
    disabled_apps: list[str] = []


@app.post("/api/devices", status_code=201, summary="Manually register an IoT device")
async def add_device(body: DeviceIn):
    """Add or update an IoT device manually in the registry database."""
    if not _is_ip_in_local_subnet(body.ip):
        log.warning("Manual registration failed: IP %s is outside of the allowed local subnet or private IP ranges.", body.ip)
        raise HTTPException(
            status_code=400,
            detail=f"Device IP {body.ip} is outside of the allowed local subnet {str(ipaddress.ip_network(_get_local_subnet(), strict=False))} or private IP ranges."
        )
        
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


@app.post("/api/devices/{ip}/toggle-app", summary="Toggle application deactivation status")
async def toggle_app_deactivation(ip: str, app_title: str, deactivated: bool):
    """Disable or enable an application for a specific device, saving persistent settings."""
    devices = _load_registry()
    found = False
    disabled = []
    for device in devices:
        if device.get("ip") == ip:
            disabled = device.setdefault("disabled_apps", [])
            slug = _slugify(app_title)
            existing_match = next((d for d in disabled if _slugify(d) == slug), None)
            
            if deactivated:
                if not existing_match:
                    disabled.append(app_title)
            else:
                if existing_match:
                    disabled.remove(existing_match)
            found = True
            break
            
    if not found:
        raise HTTPException(status_code=404, detail="Device not found")
        
    _save_registry(devices)
    log.info("Application '%s' toggled (deactivated=%s) on device %s", app_title, deactivated, ip)
    return {"ok": True, "disabled_apps": disabled}


@app.get("/api/vendors", summary="List all supported hardware vendors and API specs")
async def get_vendors():
    """Retrieve metadata and API contract specifications for all supported hardware vendors."""
    disabled_vendors = _load_disabled_vendors()
    return [
        {
            "key": v.key,
            "name": v.name,
            "version": v.version,
            "description": v.description,
            "type": v.type,
            "keywords": v.keywords,
            "deactivated": v.key in disabled_vendors,
            "api_calls": v.get_api_calls()
        }
        for name, v in VENDORS.items() if name != "Generic"
    ]


@app.post("/api/vendors/{key}/toggle", summary="Toggle vendor activation status")
async def toggle_vendor(key: str, deactivated: bool):
    """Enable or disable a vendor integration globally."""
    disabled_vendors = _load_disabled_vendors()
    if deactivated:
        if key not in disabled_vendors:
            disabled_vendors.append(key)
    else:
        if key in disabled_vendors:
            disabled_vendors.remove(key)
    _save_disabled_vendors(disabled_vendors)
    log.info("Vendor '%s' toggled (deactivated=%s)", key, deactivated)
    return {"ok": True, "disabled_vendors": disabled_vendors}


@app.get("/api/network-prefix", summary="Retrieve local subnet prefix suggestion")
async def get_network_prefix():
    """Retrieve the prefix of the local subnet for manual adding suggestion (e.g. '192.168.1.')."""
    subnet_str = _get_local_subnet()
    if "/" in subnet_str:
        ip_part = subnet_str.split("/")[0]
        parts = ip_part.split(".")
        if len(parts) == 4:
            return {"prefix": f"{parts[0]}.{parts[1]}.{parts[2]}."}
            
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        parts = local_ip.split(".")
        if len(parts) == 4:
            return {"prefix": f"{parts[0]}.{parts[1]}.{parts[2]}."}
    except Exception:
        pass

    return {"prefix": "192.168.1."}


@app.get("/api/subnet", summary="Retrieve currently configured subnet")
async def get_subnet():
    """Retrieve the subnet range (e.g. '192.168.1.0/24')."""
    return {"subnet": _get_local_subnet()}


@app.get("/api/vendors/{vendor_name}/discover-schema", summary="Retrieve discovery spec details for n8n")
async def get_vendor_discover_schema(vendor_name: str):
    """Retrieve the JSON configuration schema of the get_apps_request query sheet for a vendor."""
    normalized = vendor_name.lower()
    if normalized == "sony":
        normalized = "sony_bravia_tv"
    elif normalized == "denon":
        normalized = "denon_amplifier"
        
    if normalized not in VENDORS_REGISTRY:
        log.warning("Discover-schema request failed: Vendor '%s' not found", vendor_name)
        raise HTTPException(status_code=404, detail=f"Vendor '{vendor_name}' not found in registry.")
    return VENDORS_REGISTRY[normalized]["get_apps_request"]


@app.post("/api/factory-reset", summary="Factory reset all database and configurations")
async def factory_reset():
    """Delete all local files and reset registry/actions back to clean initial states."""
    try:
        if REGISTRY_PATH.exists():
            REGISTRY_PATH.unlink()
        if ACTIONS_PATH.exists():
            ACTIONS_PATH.unlink()
        REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)
        DYNAMIC_ACTIONS_CACHE.clear()
        log.warning("Factory Reset executed: deleted registry.json and actions.json")
        return {"ok": True, "message": "Factory reset complete. System is back to a clean install state."}
    except Exception as e:
        log.error("Failed to execute factory reset: %s", e)
        raise HTTPException(status_code=500, detail=f"Factory reset failed: {str(e)}")


@app.post("/api/scan", summary="Trigger mDNS and ping network scan")
async def trigger_scan(bg: BackgroundTasks, subnet: str = None):
    """Scan local network asynchronously and update registered devices registry."""
    if subnet:
        try:
            ipaddress.ip_network(subnet, strict=False)
            import os
            os.environ["PAPYCONNECT_SUBNET"] = subnet
            try:
                subnet_file = Path("./data/subnet.txt")
                subnet_file.parent.mkdir(parents=True, exist_ok=True)
                subnet_file.write_text(subnet, encoding="utf-8")
                log.info("Persisted custom subnet from scan configuration: %s", subnet)
            except Exception as e:
                log.error("Failed to write custom subnet to file: %s", e)
        except ValueError:
            log.warning("Invalid subnet format supplied: %s", subnet)
            raise HTTPException(status_code=400, detail=f"Invalid subnet format: {subnet}")

    bg.add_task(_full_scan)
    return {
        "ok": True,
        "message": f"Network scan triggered (mDNS {int(MDNS_SCAN_DURATION)}s + ping known)" + (f" on subnet {subnet}" if subnet else ""),
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
        
    vendor_name = _get_device_vendor_name(device)
    disabled_vendors = _load_disabled_vendors()
    if vendor_name in disabled_vendors:
        log.warning("Execution failed: Vendor '%s' is deactivated for device IP %s", vendor_name, ip)
        raise HTTPException(status_code=400, detail="Vendor integration is deactivated.")
        
    dtype = device.get("type")
    catalog_key = _get_device_vendor_name(device)
    if catalog_key not in DEVICE_CATALOGS:
        catalog_key = dtype
        
    if catalog_key not in DEVICE_CATALOGS:
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
        if any(f"{{{k}}}" in payload for k in variables):
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
        
    elif protocol == "WS" or protocol == "WEBSOCKET":
        path = action_meta.get("path", "")
        
        # Retrieve token from variables if present and append to WebSocket path
        variables = device.get("variables", {})
        token = variables.get("token")
        if token:
            if "token=" not in path:
                separator = "&" if "?" in path else "?"
                path = f"{path}{separator}token={token}"
                
        # Construct ws or wss URL based on the port
        proto_prefix = "wss" if port == 8002 else "ws"
        url = f"{proto_prefix}://{ip}:{port}{path}"
        log.info("Sending WebSocket command to %s (payload: %r)", url, payload)
        
        success, new_token = await _send_websocket_command(url, payload)
        if not success:
            log.warning("WebSocket command to %s failed", url)
            raise HTTPException(status_code=502, detail=f"Could not reach device on WebSocket url {url}.")
            
        if new_token and new_token != token:
            # Persistent storage of the pairing token in registry.json variables
            devices = _load_registry()
            for d in devices:
                if d.get("ip") == ip:
                    d.setdefault("variables", {})["token"] = new_token
                    break
            _save_registry(devices)
            log.info("Persisted new WebSocket authorization token for device IP %s", ip)
            
        log.info("WebSocket command completed successfully on %s", url)
        return {"ok": True, "message": f"Action '{action_name}' sent successfully via WebSocket to {ip}."}
        
    elif protocol == "STATIC":
        log.info("Static/n8n action '%s' triggered for device %s", action_name, ip)
        return {"ok": True, "message": f"Action '{action_name}' triggered (handled via n8n/static integration)."}
        
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
    catalog_key = _get_device_vendor_name(device)
    if catalog_key not in DEVICE_CATALOGS:
        catalog_key = dtype
        
    if catalog_key not in DEVICE_CATALOGS:
        raise HTTPException(status_code=400, detail=f"No action catalog available for type '{dtype}'.")
        
    actions = _get_device_actions(device)
    if action_name not in actions:
        raise HTTPException(status_code=404, detail=f"Action '{action_name}' not defined for type '{dtype}'.")
        
    action_meta = actions[action_name]
    payload = action_meta.get("payload", "")
    variables = device.get("variables", {})
    if isinstance(payload, str) and variables:
        if any(f"{{{k}}}" in payload for k in variables):
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
        
    vendor_name = _get_device_vendor_name(device)
    disabled_vendors = _load_disabled_vendors()
    if vendor_name in disabled_vendors:
        log.warning("Execution failed: Vendor '%s' is deactivated globally for action execution", vendor_name)
        raise HTTPException(status_code=400, detail="Vendor integration is deactivated.")
        
    dtype = device.get("type")
    catalog_key = _get_device_vendor_name(device)
    if catalog_key not in DEVICE_CATALOGS:
        catalog_key = dtype
        
    if catalog_key not in DEVICE_CATALOGS:
        raise HTTPException(status_code=400, detail=f"No action catalog available for type '{dtype}'.")
        
    actions_cat = _get_device_actions(device)
    if action_name not in actions_cat:
        raise HTTPException(status_code=404, detail=f"Action '{action_name}' not defined for type '{dtype}'.")
        
    action_meta = actions_cat[action_name]
    payload = action_meta.get("payload", "")
    variables = device.get("variables", {})
    if isinstance(payload, str) and variables:
        if any(f"{{{k}}}" in payload for k in variables):
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
