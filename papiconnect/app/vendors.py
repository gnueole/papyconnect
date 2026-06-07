import json

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
            "Power On": {
                "protocol": "HTTP",
                "method": "POST",
                "port": 8008,
                "path": "/apps/HomeScreen"
            },
            "Power Off": {
                "protocol": "HTTP",
                "method": "GET",
                "port": 8080,
                "path": "/remote-control?key=116"
            },
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
        from config import _slugify
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
            },
            "Power On": {
                "protocol": "STATIC"
            },
            "Power Off": {
                "protocol": "STATIC"
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
