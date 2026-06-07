import asyncio
import socket
from zeroconf import ServiceBrowser, Zeroconf
from zeroconf.asyncio import AsyncZeroconf

from config import log, MDNS_SCAN_DURATION, KNOWN_DEVICES
from actions import (
    _load_registry,
    _save_registry,
    _merge_devices
)

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


class _MDNSListener:
    """Collect cast, TV, and speaker devices discovered during scan window."""

    def __init__(self):
        self.found: list[dict] = []

    def add_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        info = zc.get_service_info(type_, name)
        if not info or not info.addresses:
            return
        ip = socket.inet_ntoa(info.addresses[0])
        raw_name = info.properties.get(b"fn", b"")
        label = raw_name.decode(errors="replace") if raw_name else name.split(".")[0]
        
        # Clean up common prefixes (12-char hex MAC addresses, or "ID@" prefix)
        import re
        label = re.sub(r'^[0-9a-fA-F]{12}_?', '', label)
        label = re.sub(r'^.*?@', '', label)
        label = label.strip()
        
        # Determine vendor and device type based on friendly name or model properties
        model = info.properties.get(b"md", b"").decode(errors="replace") if info.properties.get(b"md") else ""
        friendly = label.lower()
        model_lower = model.lower()
        
        vendor = "Generic"
        device_type = "unknown"
        if "_googlecast._tcp.local." in type_:
            vendor = "Google Home"
            device_type = "google_home"
        
        if "sony" in friendly or "bravia" in friendly or "sony" in model_lower or "bravia" in model_lower:
            vendor = "sony_bravia_tv"
            device_type = "tv"
        elif "bbox" in friendly or "bbox" in model_lower:
            vendor = "bbox"
            device_type = "tv"
        elif "denon" in friendly or "denon" in model_lower:
            vendor = "denon_amplifier"
            device_type = "amplifier"
        elif "marantz" in friendly or "marantz" in model_lower:
            vendor = "marantz_amplifier"
            device_type = "amplifier"
        elif "sonos" in friendly or "sonos" in model_lower:
            vendor = "sonos"
            device_type = "speaker"
        elif "yamaha" in friendly or "musiccast" in friendly or "yamaha" in model_lower or "musiccast" in model_lower:
            vendor = "yamaha_musiccast"
            device_type = "amplifier"
        elif "roku" in friendly or "roku" in model_lower:
            vendor = "roku"
            device_type = "tv"
        elif "hue" in friendly or "hue" in model_lower:
            vendor = "philips_hue"
            device_type = "lighting"
        elif "wiz" in friendly or "wiz" in model_lower:
            vendor = "philips_wiz"
            device_type = "lighting"
            
        log.info("mDNS discovered: %s @ %s (Vendor: %s, Type: %s)", label, ip, vendor, device_type)
        
        # Avoid duplicates in the discovered list
        existing = next((d for d in self.found if d["ip"] == ip), None)
        if existing:
            if existing["vendor"] == "Generic" and vendor != "Generic":
                existing["name"] = label
                existing["type"] = device_type
                existing["vendor"] = vendor
        else:
            self.found.append({
                "name": label, 
                "ip": ip, 
                "type": device_type, 
                "vendor": vendor, 
                "source": "mdns"
            })

    def remove_service(self, *_): pass
    def update_service(self, *_): pass


async def _scan_mdns() -> list[dict]:
    """Scan local network for Chromecast, Spotify Connect, and Bravia services."""
    listener = _MDNSListener()
    azc = AsyncZeroconf()
    protocols = ["_googlecast._tcp.local.", "_spotify-connect._tcp.local.", "_bravia._tcp.local."]
    ServiceBrowser(azc.zeroconf, protocols, listener)
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
