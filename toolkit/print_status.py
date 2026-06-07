#!/usr/bin/env python3
import sys
import urllib.request
import urllib.parse
import json

def main():
    import os
    from pathlib import Path
    
    # Try to load .env relative to script or in CWD
    env_vars = {}
    for p in [Path(__file__).parent.parent / ".env", Path(".env")]:
        if p.exists():
            try:
                for line in p.read_text(encoding="utf-8").splitlines():
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        env_vars[k.strip()] = v.strip()
            except Exception:
                pass
            break

    default_host = env_vars.get("GRONAS_IP") or os.environ.get("GRONAS_IP") or "gronas"
    default_port = env_vars.get("PAPYCONNECT_PORT") or os.environ.get("PAPYCONNECT_PORT") or "8000"

    args = sys.argv[1:]
    
    if len(args) >= 2 and not any(x in args[0] for x in ["=", "add", "byapp"]):
        host = args[0]
        port = args[1]
        remaining_args = args[2:]
    else:
        host = default_host
        port = default_port
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
                
                # Fetch vendors from API to match name dynamically
                vendors = []
                try:
                    vendors_url = f"http://{host}:{port}/api/vendors"
                    req = urllib.request.Request(vendors_url)
                    with urllib.request.urlopen(req, timeout=3.0) as resp:
                        vendors = json.loads(resp.read().decode('utf-8'))
                except Exception:
                    pass
                
                # Match vendor and type from device name
                name_lower = dev_name.lower()
                vendor = "Generic"
                dev_type = "unknown"
                
                for v in vendors:
                    keywords = v.get("keywords", [])
                    if any(kw.lower() in name_lower for kw in keywords):
                        vendor = v.get("name")
                        dev_type = v.get("type", "unknown")
                        break

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

    # Check for vendor or --vendor argument to toggle activation globally
    if "vendor" in remaining_args or "--vendor" in remaining_args:
        vendor_idx = remaining_args.index("vendor") if "vendor" in remaining_args else remaining_args.index("--vendor")
        if vendor_idx + 1 < len(remaining_args):
            pair = remaining_args[vendor_idx + 1]
            if "=" in pair:
                vendor_key, status_val = pair.split("=", 1)
                deactivated = status_val.lower() not in ["active", "activated", "true", "1"]
                
                toggle_url = f"http://{host}:{port}/api/vendors/{vendor_key}/toggle"
                try:
                    query = urllib.parse.urlencode({"deactivated": str(deactivated).lower()})
                    req = urllib.request.Request(
                        f"{toggle_url}?{query}",
                        method="POST"
                    )
                    with urllib.request.urlopen(req, timeout=5.0) as resp:
                        res = json.loads(resp.read().decode('utf-8'))
                        if res.get("ok"):
                            status_label = "deactivated" if deactivated else "activated"
                            print(f"\033[92mSuccessfully set vendor integration {vendor_key} to {status_label}\033[0m")
                        else:
                            print(f"\033[91mFailed to toggle vendor: {res}\033[0m")
                except Exception as e:
                    print(f"\033[91mError toggling vendor via API: {e}\033[0m")
                    sys.exit(1)
            else:
                print("\033[91mError: vendor parameter must be in format 'key=active/inactive' (e.g. google_home=active)\033[0m")
                sys.exit(1)
        else:
            print("\033[91mError: vendor parameter must specify 'key=active/inactive'\033[0m")
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
                
                if dev.get("vendor_deactivated") or vendor == "Generic":
                    status_str = "\033[90mdeactivated\033[0m"
                elif status == "online":
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
        if dev.get("vendor_deactivated") or vendor == "Generic":
            status_str = "\033[90mdeactivated\033[0m"
        elif status == "online":
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
