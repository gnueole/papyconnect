#!/usr/bin/env python3
import sys
import urllib.request
import json

def main():
    # Retrieve host and port from arguments or fallback
    host = sys.argv[1] if len(sys.argv) > 1 else "gronas"
    port = sys.argv[2] if len(sys.argv) > 2 else "8000"
    url = f"http://{host}:{port}/api/devices"

    print(f"\n\033[1;33m🌐 PapyConnect Scan Status ({host}:{port})\033[0m")
    print("\033[90m==================================================\033[0m")

    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=5.0) as response:
            devices = json.loads(response.read().decode('utf-8'))
    except Exception as e:
        print(f"\033[1;31mError connecting to PapyConnect API at {url}: {e}\033[0m")
        sys.exit(1)

    if not devices:
        print("No scanned devices found.")
        print("\033[90m==================================================\033[0m")
        return

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
            
            print(f"{prefix_indent}{prefix_app}\033[32m{app}\033[0m")
            
    print("\033[90m==================================================\033[0m")

if __name__ == "__main__":
    main()
