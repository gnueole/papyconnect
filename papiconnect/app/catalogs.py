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
            "power_on": {
                "protocol": "STATIC"
            },
            "power_off": {
                "protocol": "STATIC"
            },
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
    "actions": {
        "power_on": {
            "protocol": "HTTP",
            "method": "POST",
            "port": 8008,
            "path": "/apps/HomeScreen"
        },
        "power_off": {
            "protocol": "HTTP",
            "method": "GET",
            "port": 8080,
            "path": "/remote-control?key=116"
        }
    }
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
