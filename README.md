# PapyConnect Home Lab Integration Stack

This workspace organizes the PapyConnect dynamic IoT service registry (FastAPI) and the dynamic Logitech Options+ triggers. It contains both a dynamic C# plugin (**PapyConnect C# Plugin**) and a JavaScript/JSON Extension blueprint for Options+.

---

## 🚀 System Architecture

```mermaid
graph TD
    A[Logitech MX Creative Keypad] -->|1. Presses LCD Key| B[PapyConnect Plugin / extension]
    B -->|2. Dynamic HTTP POST Webhook| C[n8n Gateway / gronas:5678]
    C -->|3. Query Execution Contract| D[PapyConnect / gronas:8000]
    D -->|4. Returns HTTP/TCP details| C
    C -->|5a. Execute HTTP POST| E[Sony Bravia TV API]
    C -->|5b. Execute raw TCP Telnet| F[Denon/Marantz Telnet]
    C -->|5c. Set Scene parallelly| G[LIFX Cloud API]
```

---

## 🔌 PapyConnect C# Plugin (Loupedeck/Logi)

The compiled C# plugin is located in [PapyConnectPlugin/](file:///home/eole/projects/papyconnect/PapyConnectPlugin).

### 1. How it works
The plugin reads the n8n Gateway URL from a configuration file under a dedicated `PapyConnect` folder in your Windows Documents folder:
👉 `C:\Users\YOUR_USERNAME\Documents\PapyConnect\config.json`

Example:
```json
{
  "N8nGatewayUrl": "http://gronas:5678"
}
```

The dynamic action parameters are fetched automatically from the gateway and cached in:
👉 `C:\Users\YOUR_USERNAME\Documents\PapyConnect\n8n_triggers.json`

Example of cached triggers file:
```json
[
  {
    "id": "netflix_salon",
    "name": "Netflix Salon",
    "url": "http://gronas:5678/webhook/papyconnect-action?id=netflix_salon",
    "color": "#E50914"
  },
  {
    "id": "spotify_salon",
    "name": "Spotify Salon",
    "url": "http://gronas:5678/webhook/papyconnect-action?id=spotify_salon",
    "color": "#1DB954"
  }
]
```

- **id**: Unique key identifier.
- **name**: Label displayed on the LCD key.
- **url**: The unique n8n Gateway webhook URL.
- **color**: Hex color code for the border and label drawing.

### 2. Build and Deploy
- **Install .NET 8.0 SDK (if missing)**:
  ```bash
  make prepare
  ```
- **Build, Deploy, and Reload**:
  ```bash
  make build deploy restart
  ```
  *(This compiles the C# codebase, deploys it to the Logitech plugins folder, and restarts Logi Options+).*

---

## 🌐 Logitech Options+ JS/JSON Extension Blueprint

A modern JavaScript/JSON extension blueprint is located in [logi-js-plugin/](file:///home/eole/projects/papyconnect/logi-js-plugin).
It leverages the native Chromium Options+ Extension background scripts API.

### Files
- [manifest.json](file:///home/eole/projects/papyconnect/logi-js-plugin/manifest.json): Registers the dynamic action trigger and declares a user-facing **n8n Gateway URL** settings input field inside Logi+ Settings.
- [plugin.js](file:///home/eole/projects/papyconnect/logi-js-plugin/plugin.js): Fetches the actions list dynamically from the configured n8n gateway `/webhook/get-exposed-actions` and maps them to dynamic keypad keys.

---

## 🛠️ n8n Workflows Sync & Maintenance

You can manage, backup, and push n8n workflows using the Python toolkit:

- **Backup all workflows from n8n**:
  ```bash
  python3 toolkit/sync_n8n.py --backup-all
  ```
- **Push/Deploy local workflows to n8n**:
  ```bash
  python3 toolkit/sync_n8n.py --push-all
  ```
  *(Note: This automatically deactivates conflicting triggers, like the legacy router, to ensure clean activation).*

---

## 📺 PapyConnect Backend Service (Synology NAS)

PapyConnect runs as a FastAPI container stack on your Synology NAS `gronas`.

- **Redeploy / Recreate Container**:
  ```bash
  make papiconnect-recreate
  ```
- **API URL**: `http://gronas:8000/docs`
- **Dashboard URL**: `http://gronas:8000/` (features the 3-step Papy-friendly actions creation wizard).

---

## 🗂️ PapyConnect Data Structures & Vendor Catalog

PapyConnect utilizes a dynamic, schema-driven approach to interact with different hardware vendor devices.

### 1. Vendor Discovery Schema (`VENDORS_REGISTRY`)
Every constructeur belongs to a catalog sheet mapping how PapyConnect should execute discovery queries to retrieve their available applications. The query sheets are declared in `VENDORS_REGISTRY` inside [main.py](file:///home/eole/projects/papyconnect/papiconnect/app/main.py):

- **HTTP Discovery (e.g., Sony TV, Bbox, Google Home)**:
  Defines the HTTP method, request headers, targets, and JSON/XML request payloads.
- **Static Discovery (e.g., Xbox, Denon Amplifier)**:
  Returns a hardcoded list of compatible app shortcuts for socket/telnet protocols that do not support standard HTTP application lists.

### 2. The `/api/vendors/{vendor_name}/discover-schema` Endpoint
Exposes the query sheet directly to the n8n automation gateway, allowing it to retrieve request templates and perform network calls dynamically:
```bash
curl -s http://gronas:8000/api/vendors/google_home/discover-schema
```

### 3. Device Available Apps (`available_apps`)
When a device is refreshed or scanned, the backend resolves its vendor discovery schema, queries the device, parses the response (XML, JSON, or Static list), and updates the `"available_apps"` field:
```json
{
  "name": "BRAVIA 4K UR1",
  "ip": "192.168.1.55",
  "type": "tv",
  "vendor": "Sony",
  "available_apps": [
    "Netflix",
    "YouTube",
    "Spotify"
  ],
  "status": "online"
}
```
