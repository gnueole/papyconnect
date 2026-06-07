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
import ipaddress
from datetime import datetime
from pathlib import Path

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
    },
    "google_home": {
        "icon": "google_home",
        "tuto": """
            <h3>🔊 Google Home / Nest Speaker Configuration (Google Cast)</h3>
            <p>Control is executed via the Google Cast protocol.</p>
            <ul style="text-align: left; margin-top: 8px;">
                <li>Allows launching audio and video streams directly on Google Cast compatible speakers and displays.</li>
            </ul>
        """,
        "actions": {
            "launch_spotify": {
                "protocol": "GOOGLE_CAST"
            },
            "launch_youtube": {
                "protocol": "GOOGLE_CAST"
            }
        }
    },
    "xbox": {
        "icon": "xbox",
        "tuto": """
            <h3>🎮 Xbox Series X Configuration (SmartGlass)</h3>
            <p>Control is executed via UDP SmartGlass protocol or resolved via n8n.</p>
        """,
        "actions": {
            "launch_netflix": {
                "protocol": "STATIC"
            },
            "launch_youtube": {
                "protocol": "STATIC"
            }
        }
    },
    "playstation": {
        "icon": "playstation",
        "tuto": """
            <h3>🎮 PlayStation 5 Configuration</h3>
            <p>Control is resolved via n8n.</p>
        """,
        "actions": {
            "launch_netflix": {
                "protocol": "STATIC"
            },
            "launch_youtube": {
                "protocol": "STATIC"
            },
            "launch_spotify": {
                "protocol": "STATIC"
            }
        }
    }
}

# Add "tv" as an alias to the "sony_bravia_tv" catalog to support generic discovered devices
DEVICE_CATALOGS["tv"] = DEVICE_CATALOGS["sony_bravia_tv"]
DEVICE_CATALOGS["bbox"] = {
    "icon": "bbox",
    "tuto": """
        <h3>📺 Bouygues Bbox TV Configuration (DIAL)</h3>
        <p>Control is executed via the DIAL HTTP protocol on port 8008.</p>
    """,
    "actions": {}
}
DEVICE_CATALOGS["denon_amplifier"] = DEVICE_CATALOGS["amplifier"]
DEVICE_CATALOGS["marantz_amplifier"] = {
    "icon": "marantz_amplifier",
    "tuto": """
        <h3>🔊 Marantz Receiver Configuration (Telnet)</h3>
        <p>Control is executed via raw TCP commands on port 23.</p>
        <ul style="text-align: left; margin-top: 8px;">
            <li><b>Required:</b> Set the <i>Network Control</i> option to <b>Always On</b> in the receiver settings (Setup ➔ Network) to allow remote power on.</li>
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
}
DEVICE_CATALOGS["lg_tv"] = {
    "icon": "lg_tv",
    "tuto": """
        <h3>📺 LG TV Configuration (WebOS REST)</h3>
        <p>Control is executed via REST HTTP requests on port 8010.</p>
    """,
    "actions": {
        "power_off": {
            "protocol": "HTTP",
            "method": "POST",
            "port": 8010,
            "path": "/roap/api/command",
            "headers": {
                "Content-Type": "application/xml"
            },
            "payload": "<?xml version=\"1.0\" encoding=\"utf-8\"?><command><name>HandleKeyInput</name><value>1</value></command>"
        }
    }
}
DEVICE_CATALOGS["sharp_tv"] = {
    "icon": "sharp_tv",
    "tuto": """
        <h3>📺 Sharp AQUOS TV Configuration (IP Control)</h3>
        <p>Control is executed via raw TCP commands on port 10002.</p>
    """,
    "actions": {
        "power_on": {
            "protocol": "TCP",
            "port": 10002,
            "payload": "POWR1   \r"
        },
        "power_off": {
            "protocol": "TCP",
            "port": 10002,
            "payload": "POWR0   \r"
        }
    }
}
DEVICE_CATALOGS["samsung_tv"] = {
    "icon": "samsung_tv",
    "tuto": """
        <h3>📺 Samsung TV Configuration (Tizen REST)</h3>
        <p>Control is executed via REST HTTP requests on port 8001.</p>
    """,
    "actions": {
        "power_off": {
            "protocol": "HTTP",
            "method": "POST",
            "port": 8001,
            "path": "/api/v2/channels/samsung.remote.control",
            "headers": {
                "Content-Type": "application/json"
            },
            "payload": "{\"method\":\"ms.remote.control\",\"params\":{\"Cmd\":\"Click\",\"DataOfCmd\":\"KEY_POWER\",\"Option\":\"false\",\"TypeOfRemote\":\"SendRemoteKey\"}}"
        }
    }
}
DEVICE_CATALOGS["philips_hue"] = {
    "icon": "philips_hue",
    "tuto": """
        <h3>💡 Philips Hue Bridge Configuration (REST)</h3>
        <p>Control lights via the local Philips Hue Bridge API on port 80.</p>
    """,
    "actions": {
        "power_on": {
            "protocol": "HTTP",
            "method": "PUT",
            "port": 80,
            "path": "/api/{username}/lights/{id}/state",
            "payload": "{\"on\":true}"
        },
        "power_off": {
            "protocol": "HTTP",
            "method": "PUT",
            "port": 80,
            "path": "/api/{username}/lights/{id}/state",
            "payload": "{\"on\":false}"
        }
    }
}
DEVICE_CATALOGS["sonos"] = {
    "icon": "sonos",
    "tuto": """
        <h3>🎵 Sonos Speaker Configuration (UPnP/SOAP)</h3>
        <p>Control local audio playback via UPnP port 1400.</p>
    """,
    "actions": {
        "play": {
            "protocol": "HTTP",
            "method": "POST",
            "port": 1400,
            "path": "/MediaRenderer/AVTransport/Control",
            "headers": {
                "SOAPACTION": "\"urn:schemas-upnp-org:service:AVTransport:1#Play\"",
                "Content-Type": "text/xml; charset=\"utf-8\""
            },
            "payload": "<s:Envelope xmlns:s=\"http://schemas.xmlsoap.org/soap/envelope/\" s:encodingStyle=\"http://schemas.xmlsoap.org/soap/encoding/\"><s:Body><u:Play xmlns:u=\"urn:schemas-upnp-org:service:AVTransport:1\"><InstanceID>0</InstanceID><Speed>1</Speed></u:Play></s:Body></s:Envelope>"
        },
        "pause": {
            "protocol": "HTTP",
            "method": "POST",
            "port": 1400,
            "path": "/MediaRenderer/AVTransport/Control",
            "headers": {
                "SOAPACTION": "\"urn:schemas-upnp-org:service:AVTransport:1#Pause\"",
                "Content-Type": "text/xml; charset=\"utf-8\""
            },
            "payload": "<s:Envelope xmlns:s=\"http://schemas.xmlsoap.org/soap/envelope/\" s:encodingStyle=\"http://schemas.xmlsoap.org/soap/encoding/\"><s:Body><u:Pause xmlns:u=\"urn:schemas-upnp-org:service:AVTransport:1\"><InstanceID>0</InstanceID></u:Pause></s:Body></s:Envelope>"
        }
    }
}
DEVICE_CATALOGS["yamaha_musiccast"] = {
    "icon": "yamaha_musiccast",
    "tuto": """
        <h3>🔊 Yamaha MusicCast Configuration (REST)</h3>
        <p>Control is executed via REST HTTP requests on port 80.</p>
    """,
    "actions": {
        "power_on": {
            "protocol": "HTTP",
            "method": "GET",
            "port": 80,
            "path": "/api/v1/main/setPower?power=on"
        },
        "power_off": {
            "protocol": "HTTP",
            "method": "GET",
            "port": 80,
            "path": "/api/v1/main/setPower?power=standby"
        }
    }
}
DEVICE_CATALOGS["roku"] = {
    "icon": "roku",
    "tuto": """
        <h3>📺 Roku External Control Configuration (ECP)</h3>
        <p>Control Roku stick or TV via HTTP REST commands on port 8060.</p>
    """,
    "actions": {
        "power_off": {
            "protocol": "HTTP",
            "method": "POST",
            "port": 8060,
            "path": "/keypress/PowerOff"
        },
        "home": {
            "protocol": "HTTP",
            "method": "POST",
            "port": 8060,
            "path": "/keypress/Home"
        }
    }
}
DEVICE_CATALOGS["philips_wiz"] = {
    "icon": "philips_wiz",
    "tuto": """
        <h3>💡 Philips WiZ Light Configuration (UDP)</h3>
        <p>Control smart bulbs using raw UDP JSON packets on port 38899.</p>
    """,
    "actions": {
        "power_on": {
            "protocol": "UDP",
            "port": 38899,
            "payload": "{\"method\":\"setPilot\",\"params\":{\"state\":true}}"
        },
        "power_off": {
            "protocol": "UDP",
            "port": 38899,
            "payload": "{\"method\":\"setPilot\",\"params\":{\"state\":false}}"
        }
    }
}

# Known devices defined with specific environment/location variables
KNOWN_DEVICES: dict[str, dict] = {}

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


class Vendor:
    name: str = "Generic"
    version: str = "1.0"
    description: str = "Generic fallback vendor"
    type: str = "unknown"

    @classmethod
    def get_api_calls(cls) -> dict:
        return {}

    @classmethod
    def get_app_list_request(cls, ip: str) -> dict | None:
        """Return a request configuration to get the application list from this device.
        Should return a dictionary with keys: 'url', 'method', 'headers', 'json'.
        """
        return None

    @classmethod
    def parse_app_list_response(cls, data: dict) -> list[dict]:
        """Parse the raw response from get_app_list_request and return a list of apps.
        Each app in the list should be a dict with keys 'title' and 'uri'.
        """
        return []

    @classmethod
    def get_launch_action_payload(cls, app_uri: str) -> dict | None:
        """Return the action payload config to execute launching this application."""
        return None


class SonyVendor(Vendor):
    name: str = "Sony"
    version: str = "v1.0 (Bravia Simple IP)"
    description: str = "Sony Bravia TVs using Pre-Shared Key (PSK) authentication."
    type: str = "tv"

    @classmethod
    def get_api_calls(cls) -> dict:
        return {
            "Get Application List": {
                "protocol": "HTTP",
                "method": "POST",
                "port": 80,
                "path": "/sony/appControl",
                "headers": {
                    "X-Auth-PSK": "0000",
                    "Content-Type": "application/json"
                },
                "payload": {
                    "method": "getApplicationList",
                    "version": "1.0",
                    "id": 1,
                    "params": []
                }
            },
            "Launch Application": {
                "protocol": "HTTP",
                "method": "POST",
                "port": 80,
                "path": "/sony/appControl",
                "headers": {
                    "X-Auth-PSK": "0000",
                    "Content-Type": "application/json"
                },
                "payload": {
                    "method": "setActiveApp",
                    "version": "1.0",
                    "id": 1,
                    "params": [{"uri": "App URI (e.g. com.sony.dtv.com.netflix.ninja...)"}]
                }
            }
        }

    @classmethod
    def get_app_list_request(cls, ip: str) -> dict | None:
        return {
            "url": f"http://{ip}/sony/appControl",
            "method": "POST",
            "headers": {
                "X-Auth-PSK": "0000",
                "Content-Type": "application/json"
            },
            "json": {
                "method": "getApplicationList",
                "version": "1.0",
                "id": 1,
                "params": []
            }
        }

    @classmethod
    def parse_app_list_response(cls, data: dict) -> list[dict]:
        if "result" in data and isinstance(data["result"], list) and len(data["result"]) > 0:
            return data["result"][0]
        return []

    @classmethod
    def get_launch_action_payload(cls, app_uri: str) -> dict | None:
        return {
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


class DenonVendor(Vendor):
    name: str = "Denon"
    version: str = "v1.0 (Telnet TCP)"
    description: str = "Denon and Marantz AV Receivers controlled via raw TCP Telnet protocol commands."
    type: str = "amplifier"

    @classmethod
    def get_api_calls(cls) -> dict:
        return {
            "Power On & Select Spotify/NET Input": {
                "protocol": "TCP",
                "port": 23,
                "payload": "SINET\r"
            },
            "Power Off (Standby)": {
                "protocol": "TCP",
                "port": 23,
                "payload": "PWSTANDBY\r"
            }
        }


class GenericVendor(Vendor):
    name: str = "Generic"
    version: str = "N/A"
    description: str = "Generic unsupported hardware vendor."
    type: str = "unknown"


class BboxVendor(Vendor):
    name: str = "Bbox"
    version: str = "v1.0 (DIAL HTTP)"
    description: str = "Bouygues Telecom Bbox Android TV devices using the DIAL protocol."
    type: str = "tv"

    @classmethod
    def get_api_calls(cls) -> dict:
        return {
            "Get Application List": {
                "protocol": "HTTP",
                "method": "GET",
                "port": 8008,
                "path": "/apps",
                "headers": {
                    "Accept": "application/xml"
                }
            },
            "Launch Application (e.g. YouTube)": {
                "protocol": "HTTP",
                "method": "POST",
                "port": 8008,
                "path": "/apps/YouTube"
            }
        }

    @classmethod
    def get_launch_action_payload(cls, app_uri: str) -> dict | None:
        app_name = app_uri
        if app_uri.startswith("launch_"):
            app_name = app_uri[7:].capitalize()
            if app_name.lower() == "youtube":
                app_name = "YouTube"
            elif app_name.lower() == "netflix":
                app_name = "Netflix"
            elif app_name.lower() == "spotify":
                app_name = "Spotify"
        return {
            "protocol": "HTTP",
            "method": "POST",
            "port": 8008,
            "path": f"/apps/{app_name}"
        }


class XboxVendor(Vendor):
    name: str = "Xbox"
    version: str = "v1.0 (UDP SmartGlass)"
    description: str = "Microsoft Xbox Series X/S gaming consoles."
    type: str = "game"

    @classmethod
    def get_api_calls(cls) -> dict:
        return {
            "Static Apps List": {
                "protocol": "STATIC",
                "apps": ["Netflix", "YouTube"]
            }
        }


class PlaystationVendor(Vendor):
    name: str = "Playstation"
    version: str = "v1.0 (PS5 REST)"
    description: str = "Sony PlayStation 5 gaming consoles."
    type: str = "game"

    @classmethod
    def get_api_calls(cls) -> dict:
        return {
            "Static Apps List": {
                "protocol": "STATIC",
                "apps": ["Netflix", "YouTube", "Spotify Connect"]
            }
        }


class MarantzVendor(Vendor):
    name: str = "Marantz"
    version: str = "v1.0 (Telnet TCP)"
    description: str = "Marantz AV Receivers controlled via raw TCP Telnet protocol commands."
    type: str = "amplifier"

    @classmethod
    def get_api_calls(cls) -> dict:
        return {
            "Power On & Select Spotify/NET Input": {
                "protocol": "TCP",
                "port": 23,
                "payload": "SINET\r"
            },
            "Power Off (Standby)": {
                "protocol": "TCP",
                "port": 23,
                "payload": "PWSTANDBY\r"
            },
            "Volume Up": {
                "protocol": "TCP",
                "port": 23,
                "payload": "MVUP\r"
            },
            "Volume Down": {
                "protocol": "TCP",
                "port": 23,
                "payload": "MVDOWN\r"
            }
        }


class LgTvVendor(Vendor):
    name: str = "LG TV"
    version: str = "v1.0 (WebOS REST)"
    description: str = "LG Smart TVs running WebOS, controlled via REST HTTP API commands."
    type: str = "tv"

    @classmethod
    def get_api_calls(cls) -> dict:
        return {
            "Power Off": {
                "protocol": "HTTP",
                "method": "POST",
                "port": 8010,
                "path": "/roap/api/command",
                "headers": {
                    "Content-Type": "application/xml"
                },
                "payload": "<?xml version=\"1.0\" encoding=\"utf-8\"?><command><name>HandleKeyInput</name><value>1</value></command>"
            },
            "Launch YouTube": {
                "protocol": "HTTP",
                "method": "POST",
                "port": 8010,
                "path": "/roap/api/command",
                "headers": {
                    "Content-Type": "application/xml"
                },
                "payload": "<?xml version=\"1.0\" encoding=\"utf-8\"?><command><name>AppLaunch</name><value>youtube</value></command>"
            },
            "Launch Netflix": {
                "protocol": "HTTP",
                "method": "POST",
                "port": 8010,
                "path": "/roap/api/command",
                "headers": {
                    "Content-Type": "application/xml"
                },
                "payload": "<?xml version=\"1.0\" encoding=\"utf-8\"?><command><name>AppLaunch</name><value>netflix</value></command>"
            }
        }


class SharpTvVendor(Vendor):
    name: str = "Sharp TV"
    version: str = "v1.0 (AQUOS IP Control)"
    description: str = "Sharp AQUOS Smart TVs controlled via raw TCP commands on port 10002."
    type: str = "tv"

    @classmethod
    def get_api_calls(cls) -> dict:
        return {
            "Power On": {
                "protocol": "TCP",
                "port": 10002,
                "payload": "POWR1   \r"
            },
            "Power Off": {
                "protocol": "TCP",
                "port": 10002,
                "payload": "POWR0   \r"
            },
            "Input HDMI 1": {
                "protocol": "TCP",
                "port": 10002,
                "payload": "IAVI1   \r"
            }
        }


class SamsungTvVendor(Vendor):
    name: str = "Samsung TV"
    version: str = "v1.0 (Samsung Tizen REST)"
    description: str = "Samsung Smart TVs running Tizen OS, controlled via REST HTTP commands."
    type: str = "tv"

    @classmethod
    def get_api_calls(cls) -> dict:
        return {
            "Get Device Info": {
                "protocol": "HTTP",
                "method": "GET",
                "port": 8001,
                "path": "/api/v2/"
            },
            "Power Off": {
                "protocol": "HTTP",
                "method": "POST",
                "port": 8001,
                "path": "/api/v2/channels/samsung.remote.control",
                "headers": {
                    "Content-Type": "application/json"
                },
                "payload": "{\"method\":\"ms.remote.control\",\"params\":{\"Cmd\":\"Click\",\"DataOfCmd\":\"KEY_POWER\",\"Option\":\"false\",\"TypeOfRemote\":\"SendRemoteKey\"}}"
            }
        }


class PhilipsHueVendor(Vendor):
    name: str = "Philips Hue"
    version: str = "v1.0 (Hue REST)"
    description: str = "Philips Hue Smart Lighting Bridge controlling lights via local REST API."
    type: str = "lighting"

    @classmethod
    def get_api_calls(cls) -> dict:
        return {
            "Power On Light": {
                "protocol": "HTTP",
                "method": "PUT",
                "port": 80,
                "path": "/api/{username}/lights/{id}/state",
                "payload": "{\"on\":true}"
            },
            "Power Off Light": {
                "protocol": "HTTP",
                "method": "PUT",
                "port": 80,
                "path": "/api/{username}/lights/{id}/state",
                "payload": "{\"on\":false}"
            },
            "Set Brightness & Color": {
                "protocol": "HTTP",
                "method": "PUT",
                "port": 80,
                "path": "/api/{username}/lights/{id}/state",
                "payload": "{\"on\":true,\"bri\":254,\"hue\":10000,\"sat\":254}"
            }
        }


class SonosVendor(Vendor):
    name: str = "Sonos"
    version: str = "v1.0 (Sonos SOAP)"
    description: str = "Sonos smart speakers and players controlled locally via UPnP/SOAP HTTP requests."
    type: str = "speaker"

    @classmethod
    def get_api_calls(cls) -> dict:
        return {
            "Play": {
                "protocol": "HTTP",
                "method": "POST",
                "port": 1400,
                "path": "/MediaRenderer/AVTransport/Control",
                "headers": {
                    "SOAPACTION": "\"urn:schemas-upnp-org:service:AVTransport:1#Play\"",
                    "Content-Type": "text/xml; charset=\"utf-8\""
                },
                "payload": "<s:Envelope xmlns:s=\"http://schemas.xmlsoap.org/soap/envelope/\" s:encodingStyle=\"http://schemas.xmlsoap.org/soap/encoding/\"><s:Body><u:Play xmlns:u=\"urn:schemas-upnp-org:service:AVTransport:1\"><InstanceID>0</InstanceID><Speed>1</Speed></u:Play></s:Body></s:Envelope>"
            },
            "Pause": {
                "protocol": "HTTP",
                "method": "POST",
                "port": 1400,
                "path": "/MediaRenderer/AVTransport/Control",
                "headers": {
                    "SOAPACTION": "\"urn:schemas-upnp-org:service:AVTransport:1#Pause\"",
                    "Content-Type": "text/xml; charset=\"utf-8\""
                },
                "payload": "<s:Envelope xmlns:s=\"http://schemas.xmlsoap.org/soap/envelope/\" s:encodingStyle=\"http://schemas.xmlsoap.org/soap/encoding/\"><s:Body><u:Pause xmlns:u=\"urn:schemas-upnp-org:service:AVTransport:1\"><InstanceID>0</InstanceID></u:Pause></s:Body></s:Envelope>"
            },
            "Set Volume": {
                "protocol": "HTTP",
                "method": "POST",
                "port": 1400,
                "path": "/MediaRenderer/RenderingControl/Control",
                "headers": {
                    "SOAPACTION": "\"urn:schemas-upnp-org:service:RenderingControl:1#SetVolume\"",
                    "Content-Type": "text/xml; charset=\"utf-8\""
                },
                "payload": "<s:Envelope xmlns:s=\"http://schemas.xmlsoap.org/soap/envelope/\" s:encodingStyle=\"http://schemas.xmlsoap.org/soap/encoding/\"><s:Body><u:SetVolume xmlns:u=\"urn:schemas-upnp-org:service:RenderingControl:1\"><InstanceID>0</InstanceID><Channel>Master</Channel><DesiredVolume>30</DesiredVolume></u:SetVolume></s:Body></s:Envelope>"
            }
        }


class YamahaMusicCastVendor(Vendor):
    name: str = "Yamaha MusicCast"
    version: str = "v1.0 (MusicCast REST)"
    description: str = "Yamaha AV Receivers and speakers using local MusicCast REST HTTP JSON API."
    type: str = "amplifier"

    @classmethod
    def get_api_calls(cls) -> dict:
        return {
            "Power On": {
                "protocol": "HTTP",
                "method": "GET",
                "port": 80,
                "path": "/api/v1/main/setPower?power=on"
            },
            "Power Off": {
                "protocol": "HTTP",
                "method": "GET",
                "port": 80,
                "path": "/api/v1/main/setPower?power=standby"
            },
            "Set Volume": {
                "protocol": "HTTP",
                "method": "GET",
                "port": 80,
                "path": "/api/v1/main/setVolume?volume=30"
            }
        }


class RokuVendor(Vendor):
    name: str = "Roku"
    version: str = "v1.0 (Roku ECP)"
    description: str = "Roku Streaming players and Roku TVs controlled via External Control Protocol (ECP)."
    type: str = "tv"

    @classmethod
    def get_api_calls(cls) -> dict:
        return {
            "Press Home Key": {
                "protocol": "HTTP",
                "method": "POST",
                "port": 8060,
                "path": "/keypress/Home"
            },
            "Launch Netflix": {
                "protocol": "HTTP",
                "method": "POST",
                "port": 8060,
                "path": "/launch/12"
            },
            "Launch YouTube": {
                "protocol": "HTTP",
                "method": "POST",
                "port": 8060,
                "path": "/launch/837"
            }
        }


class PhilipsWizVendor(Vendor):
    name: str = "Philips WiZ"
    version: str = "v1.0 (WiZ UDP)"
    description: str = "Philips WiZ WiFi smart lights controlled via local UDP JSON packets."
    type: str = "lighting"

    @classmethod
    def get_api_calls(cls) -> dict:
        return {
            "Power On": {
                "protocol": "UDP",
                "port": 38899,
                "payload": "{\"method\":\"setPilot\",\"params\":{\"state\":true}}"
            },
            "Power Off": {
                "protocol": "UDP",
                "port": 38899,
                "payload": "{\"method\":\"setPilot\",\"params\":{\"state\":false}}"
            },
            "Set Color Temp": {
                "protocol": "UDP",
                "port": 38899,
                "payload": "{\"method\":\"setPilot\",\"params\":{\"state\":true,\"temp\":4000}}"
            }
        }


VENDORS: dict[str, type[Vendor]] = {
    "Sony": SonyVendor,
    "Denon": DenonVendor,
    "Marantz": MarantzVendor,
    "LG TV": LgTvVendor,
    "Sharp TV": SharpTvVendor,
    "Samsung TV": SamsungTvVendor,
    "Philips Hue": PhilipsHueVendor,
    "Sonos": SonosVendor,
    "Yamaha MusicCast": YamahaMusicCastVendor,
    "Roku": RokuVendor,
    "Philips WiZ": PhilipsWizVendor,
    "Bbox": BboxVendor,
    "Xbox": XboxVendor,
    "Playstation": PlaystationVendor,
    "Generic": GenericVendor
}


VENDORS_REGISTRY = {
    "sony_bravia_tv": {
        "vendor": "sony_bravia_tv",
        "get_apps_request": {
            "method": "POST",
            "url": "http://{device_ip}/sony/appControl",
            "headers": {
                "X-Auth-PSK": "0000",
                "Content-Type": "application/json"
            },
            "payload": {
                "method": "getApplicationList",
                "version": "1.0",
                "id": 1,
                "params": []
            }
        }
    },
    "bbox": {
        "vendor": "bbox",
        "get_apps_request": {
            "method": "GET",
            "url": "http://{device_ip}:8008/apps",
            "headers": {
                "Accept": "application/xml"
            },
            "payload": None
        }
    },
    "google_home": {
        "vendor": "google_home",
        "get_apps_request": {
            "method": "GET",
            "url": "http://{device_ip}:8008/setup/eureka_info?options=detail",
            "headers": {
                "Content-Type": "application/json"
            },
            "payload": None
        }
    },
    "xbox": {
        "vendor": "xbox",
        "get_apps_request": {
            "method": "STATIC",
            "apps": ["Netflix", "YouTube"]
        }
    },
    "playstation": {
        "vendor": "playstation",
        "get_apps_request": {
            "method": "STATIC",
            "apps": ["Netflix", "YouTube", "Spotify Connect"]
        }
    },
    "denon_amplifier": {
        "vendor": "denon_amplifier",
        "get_apps_request": {
            "method": "STATIC",
            "apps": ["Spotify"]
        }
    },
    "marantz_amplifier": {
        "vendor": "marantz_amplifier",
        "get_apps_request": {
            "method": "STATIC",
            "apps": ["Spotify", "HEOS"]
        }
    },
    "lg_tv": {
        "vendor": "lg_tv",
        "get_apps_request": {
            "method": "STATIC",
            "apps": ["Netflix", "YouTube", "Spotify", "Amazon Prime"]
        }
    },
    "sharp_tv": {
        "vendor": "sharp_tv",
        "get_apps_request": {
            "method": "STATIC",
            "apps": ["Netflix", "YouTube"]
        }
    },
    "samsung_tv": {
        "vendor": "samsung_tv",
        "get_apps_request": {
            "method": "STATIC",
            "apps": ["Netflix", "YouTube", "Spotify", "Disney Plus", "Amazon Prime"]
        }
    },
    "philips_hue": {
        "vendor": "philips_hue",
        "get_apps_request": {
            "method": "STATIC",
            "apps": ["Light Zone 1", "Light Zone 2", "All Lights"]
        }
    },
    "sonos": {
        "vendor": "sonos",
        "get_apps_request": {
            "method": "STATIC",
            "apps": ["Line-In", "Spotify", "TuneIn Radio"]
        }
    },
    "yamaha_musiccast": {
        "vendor": "yamaha_musiccast",
        "get_apps_request": {
            "method": "STATIC",
            "apps": ["HDMI 1", "HDMI 2", "Spotify", "Bluetooth"]
        }
    },
    "roku": {
        "vendor": "roku",
        "get_apps_request": {
            "method": "STATIC",
            "apps": ["Home", "Netflix", "YouTube", "Hulu"]
        }
    },
    "philips_wiz": {
        "vendor": "philips_wiz",
        "get_apps_request": {
            "method": "STATIC",
            "apps": ["Toggle Light", "Daylight Scene", "Night Light Scene"]
        }
    }
}


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


def _get_device_vendor(device: dict) -> type[Vendor]:
    """Retrieve Vendor class for a device."""
    vendor_name = _get_device_vendor_name(device)
    mapping = {
        "sony_bravia_tv": SonyVendor,
        "denon_amplifier": DenonVendor,
        "marantz_amplifier": MarantzVendor,
        "lg_tv": LgTvVendor,
        "sharp_tv": SharpTvVendor,
        "samsung_tv": SamsungTvVendor,
        "philips_hue": PhilipsHueVendor,
        "sonos": SonosVendor,
        "yamaha_musiccast": YamahaMusicCastVendor,
        "roku": RokuVendor,
        "philips_wiz": PhilipsWizVendor,
        "google_home": GenericVendor,
        "bbox": BboxVendor,
        "xbox": XboxVendor,
        "playstation": PlaystationVendor
    }
    return mapping.get(vendor_name, GenericVendor)


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
            for app in ["Netflix", "YouTube", "Spotify"]:
                apps_list.append({"title": app, "uri": f"launch_{_slugify(app)}"})
        return apps_list
        
    elif vendor_name == "google_home":
        return [
            {"title": "Spotify", "uri": "launch_spotify"},
            {"title": "YouTube", "uri": "launch_youtube"}
        ]
        
    elif vendor_name == "xbox":
        return [
            {"title": "Netflix", "uri": "launch_netflix"},
            {"title": "YouTube", "uri": "launch_youtube"}
        ]
        
    elif vendor_name == "playstation":
        return [
            {"title": "Netflix", "uri": "launch_netflix"},
            {"title": "YouTube", "uri": "launch_youtube"},
            {"title": "Spotify Connect", "uri": "launch_spotify"}
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
            return [{"title": app, "uri": f"launch_{_slugify(app)}"} for app in ["Netflix", "YouTube", "Spotify"]]
        elif vendor_name == "google_home":
            return [{"title": "Spotify", "uri": "launch_spotify"}, {"title": "YouTube", "uri": "launch_youtube"}]
            
    return apps_list


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
    ip = new_device.get("ip")
    if not _is_ip_in_local_subnet(ip):
        log.warning("Skipping device merge: IP %s is not in the local subnet.", ip)
        return devices
        
    for existing in devices:
        if existing.get("ip") == ip:
            existing.setdefault("name", new_device.get("name", "Unknown"))
            existing["type"] = new_device.get("type", existing.get("type", "unknown"))
            existing["vendor"] = new_device.get("vendor", existing.get("vendor", _get_device_vendor_name(existing)))
            existing["variables"] = new_device.get("variables", existing.get("variables", {}))
            existing["last_seen"] = datetime.utcnow().isoformat()
            return devices
    new_device.setdefault("last_seen", datetime.utcnow().isoformat())
    new_device["vendor"] = new_device.get("vendor", _get_device_vendor_name(new_device))
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
        
        # Determine vendor based on friendly name or model properties
        model = info.properties.get(b"md", b"").decode(errors="replace") if info.properties.get(b"md") else ""
        friendly = label.lower()
        model_lower = model.lower()
        
        vendor = "Generic"
        if "sony" in friendly or "bravia" in friendly or "sony" in model_lower or "bravia" in model_lower:
            vendor = "sony_bravia_tv"
        elif "bbox" in friendly or "bbox" in model_lower:
            vendor = "bbox"
            
        device_type = "tv"
        if vendor == "sony_bravia_tv":
            device_type = "tv"
        elif vendor == "bbox":
            device_type = "tv"
        else:
            vendor = "Generic"
            device_type = "google_home"
            
        log.info("mDNS discovered: %s @ %s (Vendor: %s)", label, ip, vendor)
        self.found.append({"name": label, "ip": ip, "type": device_type, "vendor": vendor, "source": "mdns"})

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
        
        # Initialize default empty apps list
        device["available_apps"] = []
        
        # Fetch available apps from vendor_registry discover-schema
        vendor_name = _get_device_vendor_name(device)
        schema = VENDORS_REGISTRY.get(vendor_name, {}).get("get_apps_request", {})
        apps = []
        if schema:
            is_static = schema.get("method") == "STATIC"
            is_online = device.get("status") == "online"
            if is_static or is_online:
                apps = await _fetch_device_apps(device)
                device["available_apps"] = [app["title"] if isinstance(app, dict) else app for app in apps]
        
        catalog_key = _get_device_vendor_name(device)
        if catalog_key not in DEVICE_CATALOGS:
            catalog_key = dtype
            
        if catalog_key in DEVICE_CATALOGS:
            catalog = copy.deepcopy(DEVICE_CATALOGS[catalog_key])
            device["catalog"] = catalog
            
            # Merge dynamic launch actions if the device is online and vendor supports execution
            if apps:
                vendor_cls = _get_device_vendor(device)
                device_dynamic = {}
                for app in apps:
                    if isinstance(app, dict):
                        app_title = app.get("title")
                        app_uri = app.get("uri")
                        if app_title and app_uri:
                            slug = _slugify(app_title)
                            action_key = f"launch_{slug}"
                            action_payload = vendor_cls.get_launch_action_payload(app_uri)
                            if action_payload:
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


@app.post("/api/devices", status_code=201, summary="Manually register an IoT device")
async def add_device(body: DeviceIn):
    """Add or update an IoT device manually in the registry database."""
    if not _is_ip_in_local_subnet(body.ip):
        log.warning("Manual registration failed: IP %s is outside of the local subnet.", body.ip)
        raise HTTPException(
            status_code=400,
            detail=f"Device IP {body.ip} is outside of the local subnet {str(ipaddress.ip_network(_get_local_subnet(), strict=False))}."
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


@app.get("/api/vendors", summary="List all supported hardware vendors and API specs")
async def get_vendors():
    """Retrieve metadata and API contract specifications for all supported hardware vendors."""
    return [
        {
            "name": v.name,
            "version": v.version,
            "description": v.description,
            "type": v.type,
            "api_calls": v.get_api_calls()
        }
        for name, v in VENDORS.items() if name != "Generic"
    ]


@app.get("/api/network-prefix", summary="Retrieve local subnet prefix suggestion")
async def get_network_prefix():
    """Retrieve the prefix of the local subnet for manual adding suggestion (e.g. '192.168.1.')."""
    subnet_str = _get_local_subnet()
    if "/" in subnet_str:
        ip_part = subnet_str.split("/")[0]
        parts = ip_part.split(".")
        if len(parts) == 4:
            return {"prefix": f"{parts[0]}.{parts[1]}.{parts[2]}."}
    return {"prefix": "192.168.1."}


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
