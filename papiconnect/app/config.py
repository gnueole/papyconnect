import logging
import socket
import ipaddress
import re
from pathlib import Path

# Config files
REGISTRY_PATH = Path("./data/registry.json")
ACTIONS_PATH = Path("./data/actions.json")
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

def _get_local_subnet() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        ip_net = ipaddress.ip_network(f"{local_ip}/255.255.255.0", strict=False)
        return str(ip_net)
    except Exception:
        return "192.168.1.0/24"

def _is_ip_in_local_subnet(ip_str: str) -> bool:
    try:
        ip_obj = ipaddress.ip_address(ip_str)
        subnet = ipaddress.ip_network(_get_local_subnet(), strict=False)
        return ip_obj in subnet
    except Exception:
        return False

def _slugify(text: str) -> str:
    """Helper to convert application titles into clean URL/action ID slugs."""
    text = text.lower()
    text = re.sub(r'[^a-z0-9]+', '_', text)
    return text.strip('_')
