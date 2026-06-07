#!/usr/bin/env python3
import sys
import urllib.request
import json

def main():
    # Retrieve host and port from arguments or fallback
    args = sys.argv[1:]
    host = "gronas"
    port = "8000"
    
    if len(args) >= 2:
        host = args[0]
        port = args[1]
        remaining_args = args[2:]
    else:
        remaining_args = args

    # Check for add or --add argument
    if "add" in remaining_args or "--add" in remaining_args:
        add_idx = remaining_args.index("add") if "add" in remaining_args else remaining_args.index("--add")
        if add_idx + 1 < len(remaining_args):
            pair = remaining_args[add_idx + 1]
            if "=" in pair:
                dev_name, dev_ip = pair.split("=", 1)
                
                # Retrieve local IP subnet prefix from endpoint if needed
                if dev_ip.startswith("."):
                    prefix = "192.168.1."
                    try:
                        prefix_url = f"http://{host}:{port}/api/network-prefix"
                        req = urllib.request.Request(prefix_url)
                        with urllib.request.urlopen(req, timeout=3.0) as resp:
                            prefix_data = json.loads(resp.read().decode('utf-8'))
                            prefix = prefix_data.get("prefix", "192.168.1.")
                    except Exception:
                        pass
                    dev_ip = prefix + dev_ip[1:]

                # Match vendor and type from device name
                name_lower = dev_name.lower()
                vendor = "Generic"
                dev_type = "unknown"
                
                if "sony" in name_lower or "bravia" in name_lower:
                    vendor = "Sony"
                    dev_type = "tv"
                elif "denon" in name_lower:
                    vendor = "Denon"
                    dev_type = "amplifier"
                elif "marantz" in name_lower:
                    vendor = "Marantz"
                    dev_type = "amplifier"
                elif "lg" in name_lower:
                    vendor = "LG TV"
                    dev_type = "tv"
                elif "sharp" in name_lower:
                    vendor = "Sharp TV"
                    dev_type = "tv"
                elif "samsung" in name_lower:
                    vendor = "Samsung TV"
                    dev_type = "tv"
                elif "hue" in name_lower:
                    vendor = "Philips Hue"
                    dev_type = "lighting"
                elif "sonos" in name_lower:
                    vendor = "Sonos"
                    dev_type = "speaker"
                elif "musiccast" in name_lower or "yamaha" in name_lower:
                    vendor = "Yamaha MusicCast"
                    dev_type = "amplifier"
                elif "roku" in name_lower:
                    vendor = "Roku"
                    dev_type = "tv"
                elif "wiz" in name_lower:
                    vendor = "Philips WiZ"
                    dev_type = "lighting"
                elif "bbox" in name_lower:
                    vendor = "Bbox"
                    dev_type = "tv"
                elif "google" in name_lower or "nest" in name_lower or "chromecast" in name_lower:
                    vendor = "Google Home"
                    dev_type = "speaker"
                elif "xbox" in name_lower:
                    vendor = "Xbox"
                    dev_type = "game"
                elif "playstation" in name_lower or "ps5" in name_lower or "ps4" in name_lower:
                    vendor = "Playstation"
                    dev_type = "game"

                # Send POST to add device
                add_url = f"http://{host}:{port}/api/devices"
                payload = {
                    "name": dev_name,
                    "ip": dev_ip,
                    "type": dev_type,
                    "vendor": vendor,
                    "variables": {}
                }
                
                try:
                    data_bytes = json.dumps(payload).encode('utf-8')
                    req = urllib.request.Request(
                        add_url,
                        data=data_bytes,
                        headers={"Content-Type": "application/json"},
                        method="POST"
                    )
                    with urllib.request.urlopen(req, timeout=5.0) as resp:
                        res = json.loads(resp.read().decode('utf-8'))
                        if res.get("ok"):
                            print(f"\033[92mSuccessfully registered device: {dev_name} ({dev_ip}) as {vendor} ({dev_type})\033[0m")
                        else:
                            print(f"\033[91mFailed to register device: {res}\033[0m")
                except Exception as e:
                    print(f"\033[91mError registering device via API: {e}\033[0m")
                    sys.exit(1)
            else:
                print("\033[91mError: add parameter must be in format 'name=ip' (e.g. xbox=.53 or tv=192.168.1.55)\033[0m")
                sys.exit(1)
        else:
            print("\033[91mError: add parameter must specify 'name=ip'\033[0m")
            sys.exit(1)

    # Proceed to list all devices
    url = f"http://{host}:{port}/api/devices"

    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=5.0) as response:
            devices = json.loads(response.read().decode('utf-8'))
    except Exception as e:
        print(f"\n\033[1;33m🌐 PapyConnect Scan Status ({host}:{port})\033[0m")
        print("\033[90m==================================================\033[0m")
        print(f"\033[1;31mError connecting to PapyConnect API at {url}: {e}\033[0m")
        print("\033[90m==================================================\033[0m")
        sys.exit(1)

    if not devices:
        print(f"\n\033[1;33m🌐 PapyConnect Scan Status ({host}:{port})\033[0m")
        print("\033[90m==================================================\033[0m")
        print("No scanned devices found.")
        print("\033[90m==================================================\033[0m")
        return

    # Check for --byapp or byapp grouping argument
    if "byapp" in remaining_args or "--byapp" in remaining_args:
        # Group devices by available applications
        app_to_devices = {}
        for dev in devices:
            for app in dev.get("available_apps", []):
                # Clean up any HTML entities (like &amp;) in names
                clean_app = app.replace("&amp;", "&")
                if clean_app not in app_to_devices:
                    app_to_devices[clean_app] = []
                app_to_devices[clean_app].append(dev)
                
        # Sort apps alphabetically
        sorted_apps = sorted(app_to_devices.keys())
        
        print(f"\n\033[1;33m🌐 PapyConnect Scan Status - Grouped by Application ({host}:{port})\033[0m")
        print("\033[90m==================================================\033[0m")
        
        for i, app in enumerate(sorted_apps):
            is_last_app = (i == len(sorted_apps) - 1)
            prefix_app = "└── " if is_last_app else "├── "
            
            print(f"{prefix_app}\033[1;32m{app}\033[0m")
            
            devs = app_to_devices[app]
            # Sort devices by status (online first) then by name
            devs = sorted(devs, key=lambda d: (d.get("status") != "online", d.get("name", "").lower()))
            
            for j, dev in enumerate(devs):
                is_last_dev = (j == len(devs) - 1)
                prefix_indent = "    " if is_last_app else "│   "
                prefix_dev = "└── " if is_last_dev else "├── "
                
                name = dev.get("name", "Unknown Device")
                ip = dev.get("ip", "unknown IP")
                status = dev.get("status", "unknown")
                vendor = dev.get("vendor", "Generic")
                
                if status == "online":
                    status_str = "\033[92monline\033[0m"
                else:
                    status_str = f"\033[91m{status}\033[0m"
                    
                print(f"{prefix_indent}{prefix_dev}\033[1;36m{name}\033[0m (\033[35m{ip}\033[0m) [{status_str}] [\033[33m{vendor}\033[0m]")
                
        print("\033[90m==================================================\033[0m")
        return

    # Standard print: Grouped by Device (default)
    print(f"\n\033[1;33m🌐 PapyConnect Scan Status ({host}:{port})\033[0m")
    print("\033[90m==================================================\033[0m")

    # Sort devices by status (online first) then by name
    devices = sorted(devices, key=lambda d: (d.get("status") != "online", d.get("name", "").lower()))

    for i, dev in enumerate(devices):
        is_last_dev = (i == len(devices) - 1)
        prefix_dev = "└── " if is_last_dev else "├── "
        
        name = dev.get("name", "Unknown Device")
        ip = dev.get("ip", "unknown IP")
        status = dev.get("status", "unknown")
        vendor = dev.get("vendor", "Generic")
        
        # Color coding status
        if status == "online":
            status_str = "\033[92monline\033[0m"
        else:
            status_str = f"\033[91m{status}\033[0m"
            
        print(f"{prefix_dev}\033[1;36m{name}\033[0m (\033[35m{ip}\033[0m) [{status_str}] [\033[33m{vendor}\033[0m]")
        
        apps = dev.get("available_apps", [])
        for j, app in enumerate(apps):
            is_last_app = (j == len(apps) - 1)
            # Tree indentation prefix
            prefix_indent = "    " if is_last_dev else "│   "
            prefix_app = "└── " if is_last_app else "├── "
            
            # Clean up any HTML entities (like &amp;) in names
            clean_app = app.replace("&amp;", "&")
            print(f"{prefix_indent}{prefix_app}\033[32m{clean_app}\033[0m")
            
    print("\033[90m==================================================\033[0m")

if __name__ == "__main__":
    main()
