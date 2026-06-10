import logging
import socket
import ipaddress
import re
import subprocess
from pathlib import Path

# Config files
REGISTRY_PATH = Path("./data/registry.json")
ACTIONS_PATH = Path("./data/actions.json")
DISABLED_VENDORS_PATH = Path("./data/disabled_vendors.json")
MDNS_SCAN_DURATION = 3.0

# Logging config
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("papyconnect")

# Known devices defined with specific environment/location variables
KNOWN_DEVICES: dict[str, dict] = {}

def _is_virtual_adapter(name: str) -> bool:
    name_lower = name.lower()
    virtual_keywords = ["vethernet", "wsl", "virtualbox", "vmware", "docker", "loopback", "host-only", "br-", "veth", "lo"]
    return any(kw in name_lower for kw in virtual_keywords)

def _get_local_subnet() -> str:
    # 0. Check for persisted subnet file
    try:
        subnet_file = Path("./data/subnet.txt")
        if subnet_file.exists():
            val = subnet_file.read_text(encoding="utf-8").strip()
            if val:
                return val
    except Exception:
        pass

    # 1. Check for environment variable override
    import os
    env_subnet = os.getenv("PAPYCONNECT_SUBNET")
    if env_subnet:
        return env_subnet

    # 1. Try Windows ipconfig parsing (filtering out virtual adapters and prioritizing physical ones)
    try:
        out = subprocess.check_output("ipconfig", stderr=subprocess.DEVNULL).decode("oem")
        current_adapter = None
        current_ip = None
        current_mask = None
        candidates = []
        
        for raw_line in out.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            
            # Detect adapter header: must end with ":" and NOT start with leading spaces/tabs in the raw line
            if raw_line.endswith(":") and not raw_line.startswith(" ") and not raw_line.startswith("\t"):
                if current_adapter and current_ip and current_mask:
                    if not _is_virtual_adapter(current_adapter):
                        candidates.append((current_adapter, current_ip, current_mask))
                current_adapter = line[:-1]
                current_ip = None
                current_mask = None
            elif current_adapter:
                ipv4_match = re.search(r"IPv4 Address[\s\.:]+(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})", line)
                if not ipv4_match:
                    # French Windows fallback
                    ipv4_match = re.search(r"Adresse IPv4[\s\.:]+(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})", line)
                if ipv4_match:
                    current_ip = ipv4_match.group(1)
                    
                mask_match = re.search(r"Subnet Mask[\s\.:]+(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})", line)
                if not mask_match:
                    # French Windows fallback
                    mask_match = re.search(r"Masque de sous-réseau[\s\.:]+(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})", line)
                if mask_match:
                    current_mask = mask_match.group(1)
                    
        if current_adapter and current_ip and current_mask:
            if not _is_virtual_adapter(current_adapter):
                candidates.append((current_adapter, current_ip, current_mask))
                
        # Prioritize physical WiFi or Ethernet adapters
        for name, ip, mask in candidates:
            name_lower = name.lower()
            if any(p in name_lower for p in ["wi-fi", "wifi", "ethernet", "connexion", "sans fil"]):
                return str(ipaddress.ip_network(f"{ip}/{mask}", strict=False))
                
        if candidates:
            name, ip, mask = candidates[0]
            return str(ipaddress.ip_network(f"{ip}/{mask}", strict=False))
    except Exception:
        pass

    # 2. Try Linux/Unix parsing (filtering out virtual adapters and prioritizing physical ones)
    try:
        import fcntl
        import struct
        interfaces = [name for _, name in socket.if_nameindex()]
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        candidates = []
        for ifname in interfaces:
            if _is_virtual_adapter(ifname):
                continue
            try:
                if_addr = socket.inet_ntoa(fcntl.ioctl(
                    s.fileno(),
                    0x8915,  # SIOCGIFADDR
                    struct.pack('256s', ifname[:15].encode('utf-8'))
                )[20:24])
                netmask = socket.inet_ntoa(fcntl.ioctl(
                    s.fileno(),
                    0x891b,  # SIOCGIFNETMASK
                    struct.pack('256s', ifname[:15].encode('utf-8'))
                )[20:24])
                candidates.append((ifname, if_addr, netmask))
            except Exception:
                continue
                
        # Prioritize eth, en, wlan, bond interfaces
        for name, ip, mask in candidates:
            if any(name.startswith(p) for p in ["eth", "en", "wlan", "bond"]):
                return str(ipaddress.ip_network(f"{ip}/{mask}", strict=False))
                
        if candidates:
            name, ip, mask = candidates[0]
            return str(ipaddress.ip_network(f"{ip}/{mask}", strict=False))
    except Exception:
        pass

    # 3. Connection-based socket fallback (e.g. if running inside a locked-down container without CLI tools)
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        return f"{local_ip}/24"
    except Exception:
        return "192.168.1.0/24"

def _is_ip_in_local_subnet(ip_str: str) -> bool:
    try:
        ip_obj = ipaddress.ip_address(ip_str)
        # Check if the IP is in the local subnet
        subnet = ipaddress.ip_network(_get_local_subnet(), strict=False)
        if ip_obj in subnet:
            return True
        # Also allow loopback, link-local, and private network IPs (RFC 1918)
        return ip_obj.is_private or ip_obj.is_loopback or ip_obj.is_link_local
    except Exception:
        return False

def _slugify(text: str) -> str:
    """Helper to convert application titles into clean URL/action ID slugs."""
    text = text.lower()
    text = re.sub(r'[^a-z0-9]+', '_', text)
    return text.strip('_')
