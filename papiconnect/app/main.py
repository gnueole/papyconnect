"""
PapyConnect — Dynamic IoT Service Registry
==========================================
FastAPI backend sans requirements.txt externe.
Les dépendances sont installées via 'command:' dans docker-compose.yml.

Routes exposées :
  GET  /                   → Dashboard HTML (Cinema UI)
  GET  /api/devices        → Registre + ping live (online/offline)
  POST /api/scan           → Scan mDNS 3 s + ping appareils connus
  POST /api/devices        → Enregistrement manuel d'un appareil
  DELETE /api/devices/{ip} → Suppression d'un appareil
"""

import asyncio
import aiohttp
import json
import logging
import socket
from datetime import datetime
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from zeroconf import ServiceBrowser, Zeroconf
from zeroconf.asyncio import AsyncZeroconf

# ─────────────────────────────────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────────────────────────────────
REGISTRY_PATH = Path("./data/registry.json")
ACTIONS_PATH = Path("./data/actions.json")


def _load_actions() -> dict[str, dict]:
    """Charge les actions virtuelles configurées sous forme de dictionnaire."""
    try:
        if ACTIONS_PATH.exists() and ACTIONS_PATH.stat().st_size > 2:
            data = json.loads(ACTIONS_PATH.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
            elif isinstance(data, list):
                # Migration transparente de la liste vers le dictionnaire
                migrated = {}
                for idx, a in enumerate(data):
                    btn_id = f"papyconnect_btn_{idx+1}"
                    migrated[btn_id] = {
                        "device_ip": a.get("device_ip"),
                        "target_app": a.get("target_app"),
                        "state": a.get("state", "inactive"),
                        "title": a.get("title"),
                        "icon": a.get("icon")
                    }
                return migrated
    except Exception as exc:
        log.warning("Actions virtuelles illisibles — réinitialisation : %s", exc)
    return {}


def _save_actions(actions: dict[str, dict]) -> None:
    """Écrit les actions virtuelles sur le disque avec rename atomique."""
    ACTIONS_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = ACTIONS_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(actions, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(ACTIONS_PATH)


# Appareils à IP fixe — détectés par ping lors de chaque scan
# Complète selon ton réseau (ampli, TV câblée, box domotique…)
# Le catalogue définit le gabarit (Template) de l'action sans connaître l'appareil
CATALOGUE_CONSTRUCTEURS = {
    "amplifier": {
        "icon": "amplifier",
        "tuto": """
            <h3>🔊 Configuration Ampli Denon / Marantz (Telnet)</h3>
            <p>Le pilotage s'effectue via des commandes brutes sur le port 23.</p>
            <ul style="text-align: left; margin-top: 8px;">
                <li><b>Impératif :</b> Passez l'option <i>Network Control</i> sur <b>Always On</b> dans les menus de l'ampli (Configuration ➔ Réseau). Cela évite le boot de 30 secondes en veille.</li>
                <li>La commande <code style="color: #ff9800;">SINET</code> force l'allumage sur l'entrée réseau/Spotify Connect.</li>
            </ul>
        """,
        "actions": {
            "launch_spotify": {
                "protocol": "TCP",
                "port": 23,
                "payload": "SINET\r"  # Commande universelle Denon pour basculer sur l'entrée réseau
            },
            "power_off": {
                "protocol": "TCP",
                "port": 23,
                "payload": "PWSTANDBY\r"  # Commande universelle d'extinction
            }
        }
    },
    "sony_bravia_tv": {
        "icon": "tv",
        "tuto": """
            <h3>📺 Configuration Sony Bravia (Pre-Shared Key)</h3>
            <p>Pour piloter la TV sans gestion complexe de tokens :</p>
            <ul style="text-align: left; margin-top: 8px;">
                <li>Allez dans <b>Réglages ➔ Réseau ➔ Accès Réseau</b>.</li>
                <li>Activez l'option <b>Clé pré-partagée (PSK)</b>.</li>
                <li>Définissez la clé sur : <code style="color: #ff9800; background: #222; padding: 2px 6px; border-radius: 4px;">0000</code></li>
                <li>Allez dans <b>Paramètres IP Control</b> et activez <i>Simple IP Control</i>.</li>
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
    }
}

# Alias pour supporter la détection mDNS générique du type "tv" comme "sony_bravia_tv"
CATALOGUE_CONSTRUCTEURS["tv"] = CATALOGUE_CONSTRUCTEURS["sony_bravia_tv"]

# L'inventaire fournit les variables d'environnement propres à chaque salon
KNOWN_DEVICES: dict[str, dict] = {
    "192.168.1.193": {
        "name": "Denon AVC-X3800H Salon",
        "type": "amplifier",
        "ip": "192.168.1.193",
        "variables": {
            "zone": "MAIN",
            "max_volume": 80
        }
    },
    "192.168.1.200": {
        "name": "Denon de Louistib (Modèle Supérieur)",
        "type": "amplifier",
        "ip": "192.168.1.200",
        "variables": {
            "zone": "MAIN",
            "max_volume": 90
        }
    },
    "192.168.1.100": {
        "name": "Sony Bravia TV Salon",
        "type": "sony_bravia_tv",
        "ip": "192.168.1.100",
        "variables": {}
    }
}

# EXPOSED_ACTIONS: Chargé dynamiquement via _load_actions() depuis ACTIONS_PATH (./data/actions.json)
# Durée d'écoute mDNS (secondes) — 3 s est un bon compromis vitesse/fiabilité
MDNS_SCAN_DURATION = 3.0

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("papiconnect")

# ─────────────────────────────────────────────────────────────────────────────
# Persistance JSON — lecture / écriture atomique
# ─────────────────────────────────────────────────────────────────────────────

def _load() -> list[dict]:
    """Charge le registre depuis le disque. Retourne [] en cas d'absence ou d'erreur."""
    try:
        if REGISTRY_PATH.exists() and REGISTRY_PATH.stat().st_size > 2:
            return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        log.warning("Registre illisible — réinitialisation : %s", exc)
    return []


def _save(devices: list[dict]) -> None:
    """Écriture atomique : écrit dans .tmp puis rename() — évite la corruption."""
    REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = REGISTRY_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(devices, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(REGISTRY_PATH)


def _merge(devices: list[dict], new: dict) -> list[dict]:
    """
    Fusionne *new* dans *devices* sans écraser les champs déjà renseignés.
    Met à jour 'last_seen' à chaque redécouverte.
    """
    for existing in devices:
        if existing.get("ip") == new.get("ip"):
            existing.setdefault("name", new.get("name", "Inconnu"))
            existing["type"] = new.get("type", existing.get("type", "unknown"))
            # Fusionne ou met à jour les variables
            existing["variables"] = new.get("variables", existing.get("variables", {}))
            existing["last_seen"] = datetime.utcnow().isoformat()
            return devices
    new.setdefault("last_seen", datetime.utcnow().isoformat())
    devices.append(new)
    return devices

# ─────────────────────────────────────────────────────────────────────────────
# Ping asynchrone (utilise /bin/ping du conteneur — iputils-ping requis)
# ─────────────────────────────────────────────────────────────────────────────

async def _ping(ip: str, timeout: float = 1.5) -> bool:
    """Retourne True si l'hôte répond à un ping ICMP en moins de *timeout* secondes."""
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
    """Ping tous les appareils en parallèle et injecte leur statut (online/offline)."""
    if not devices:
        return devices
    statuses = await asyncio.gather(*[_ping(d["ip"]) for d in devices])
    for device, online in zip(devices, statuses):
        device["status"] = "online" if online else "offline"
    return devices


async def _send_tcp_command(ip: str, port: int, payload: str, timeout: float = 3.0) -> bool:
    """Ouvre une connexion TCP temporaire, transmet la payload et ferme la connexion."""
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
        log.error("Erreur lors de l'envoi de la commande TCP à %s:%s - %s", ip, port, e)
        return False


async def _send_http_command(url: str, method: str, headers: dict, payload: str, timeout: float = 5.0) -> bool:
    """Envoie une requête HTTP à l'appareil."""
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
        log.error("Erreur lors de l'envoi de la commande HTTP à %s - %s", url, e)
        return False

# ─────────────────────────────────────────────────────────────────────────────
# Découverte mDNS via Zeroconf (Android TV / Chromecast)
# ─────────────────────────────────────────────────────────────────────────────

class _MDNSListener:
    """Collecte les services mDNS découverts pendant la fenêtre d'écoute."""

    def __init__(self):
        self.found: list[dict] = []

    def add_service(self, zc: Zeroconf, type_: str, name: str) -> None:  # noqa: A002
        info = zc.get_service_info(type_, name)
        if not info or not info.addresses:
            return
        ip = socket.inet_ntoa(info.addresses[0])
        raw_name = info.properties.get(b"fn", b"")
        label = raw_name.decode(errors="replace") if raw_name else name.split(".")[0]
        log.info("mDNS découvert : %s @ %s", label, ip)
        self.found.append({"name": label, "ip": ip, "type": "tv", "source": "mdns"})

    def remove_service(self, *_): pass
    def update_service(self, *_): pass


async def _scan_mdns() -> list[dict]:
    """Écoute _googlecast._tcp.local. pendant MDNS_SCAN_DURATION secondes."""
    listener = _MDNSListener()
    azc = AsyncZeroconf()
    ServiceBrowser(azc.zeroconf, "_googlecast._tcp.local.", listener)
    await asyncio.sleep(MDNS_SCAN_DURATION)
    await azc.async_close()
    return listener.found


async def _scan_known_devices() -> list[dict]:
    """Ping les appareils à IP fixe de KNOWN_DEVICES et retourne ceux qui répondent."""
    online = []
    for ip, meta in KNOWN_DEVICES.items():
        if await _ping(ip):
            online.append(dict(meta))
    return online


async def _full_scan() -> None:
    """Tâche de fond : scan mDNS + ping connus → fusion dans registry.json."""
    log.info("Scan complet démarré (mDNS %ss + ping connus)…", int(MDNS_SCAN_DURATION))
    mdns_hits, known_hits = await asyncio.gather(
        _scan_mdns(), _scan_known_devices()
    )
    devices = _load()
    for d in mdns_hits + known_hits:
        devices = _merge(devices, d)
    _save(devices)
    log.info("Scan terminé — %d appareil(s) dans le registre.", len(devices))

# ─────────────────────────────────────────────────────────────────────────────
# Application FastAPI
# ─────────────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="PapyConnect",
    description="Registre dynamique d'appareils IoT pour workflows n8n",
    version="1.1.0",
)

_TEMPLATES_DIR = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))


from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    log.warning("Erreur HTTP %s sur %s %s : %s", exc.status_code, request.method, request.url.path, exc.detail)
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    log.error("Erreur de validation de requête sur %s %s : %s", request.method, request.url.path, exc.errors())
    return JSONResponse(
        status_code=422,
        content={"detail": exc.errors()},
    )


@app.on_event("startup")
async def _startup() -> None:
    """Initialise le registre JSON vide et les actions de base."""
    REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not REGISTRY_PATH.exists():
        _save([])
        log.info("Registre initialisé : %s", REGISTRY_PATH.resolve())
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
        log.info("Actions de base initialisées : %s", ACTIONS_PATH.resolve())
    log.info("PapyConnect démarré — http://0.0.0.0:8000")



# ── Dashboard ────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse, summary="Dashboard HTML")
async def dashboard(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


# ── Devices ──────────────────────────────────────────────────────────────────

@app.get("/api/devices", summary="Liste des appareils avec statut live")
async def get_devices():
    """
    Retourne tous les appareils du registre.
    Effectue un ping asynchrone sur chaque IP avant de répondre.
    """
    devices = await _enrich_status(_load())
    for device in devices:
        dtype = device.get("type")
        if dtype in CATALOGUE_CONSTRUCTEURS:
            device["catalog"] = CATALOGUE_CONSTRUCTEURS[dtype]
    return devices


class DeviceIn(BaseModel):
    name: str
    ip: str
    type: str = "unknown"
    variables: dict = {}


@app.post("/api/devices/{ip}/action/{action_name}", summary="Exécuter une action sur un appareil")
async def run_device_action(ip: str, action_name: str):
    """
    Exécute une action définie dans le catalogue sur l'appareil ciblé.
    Substitue les variables définies pour l'appareil dans la payload.
    """
    # 1. Trouver l'appareil dans le registre
    devices = _load()
    device = next((d for d in devices if d.get("ip") == ip), None)
    
    # Si non trouvé dans le registre local, chercher dans KNOWN_DEVICES
    if not device and ip in KNOWN_DEVICES:
        device = KNOWN_DEVICES[ip]
        
    if not device:
        raise HTTPException(status_code=404, detail=f"Appareil avec l'IP {ip} non trouvé.")
        
    # 2. Vérifier son type et récupérer le catalogue
    dtype = device.get("type")
    if dtype not in CATALOGUE_CONSTRUCTEURS:
        raise HTTPException(
            status_code=400, 
            detail=f"Aucune action disponible pour le type d'appareil '{dtype}'."
        )
        
    catalog = CATALOGUE_CONSTRUCTEURS[dtype]
    actions = catalog.get("actions", {})
    if action_name not in actions:
        raise HTTPException(
            status_code=404, 
            detail=f"Action '{action_name}' non définie pour le type '{dtype}'."
        )
        
    action = actions[action_name]
    protocol = action.get("protocol")
    port = action.get("port")
    payload = action.get("payload", "")
    
    # 3. Formater la payload si des variables sont définies
    variables = device.get("variables", {})
    if isinstance(payload, str) and variables:
        try:
            payload = payload.format(**variables)
        except Exception as e:
            log.warning("Échec du formatage de la payload pour %s: %s", ip, e)
            
    # 4. Exécuter selon le protocole
    if protocol == "TCP":
        log.info("Envoi de la commande TCP à %s:%s (payload: %r)", ip, port, payload)
        success = await _send_tcp_command(ip, port, payload)
        if not success:
            log.warning("Échec de la commande TCP à %s:%s", ip, port)
            raise HTTPException(
                status_code=502, 
                detail=f"Impossible de joindre l'appareil sur le port TCP {port}."
            )
        log.info("Commande TCP envoyée avec succès à %s:%s", ip, port)
        return {"ok": True, "message": f"Action '{action_name}' envoyée avec succès par TCP à {ip}."}
    elif protocol == "HTTP":
        path = action.get("path", "")
        url = f"http://{ip}:{port}{path}"
        headers = action.get("headers", {})
        method = action.get("method", "POST")
        log.info("Envoi de la requête HTTP %s %s (headers: %r, payload: %r)", method, url, headers, payload)
        success = await _send_http_command(url, method, headers, payload)
        if not success:
            log.warning("Échec de la requête HTTP %s sur %s", method, url)
            raise HTTPException(
                status_code=502, 
                detail=f"Impossible de joindre l'appareil sur {url}."
            )
        log.info("Requête HTTP %s envoyée avec succès sur %s", method, url)
        return {"ok": True, "message": f"Action '{action_name}' envoyée avec succès par HTTP à {ip}."}
    else:
        raise HTTPException(
            status_code=400, 
            detail=f"Protocole '{protocol}' non supporté pour le moment."
        )


@app.get("/api/devices/{ip}/action/{action_name}/config", summary="Récupérer la configuration d'une action pour n8n")
async def get_device_action_config(ip: str, action_name: str):
    """
    Retourne la configuration résolue et interpolée d'une action pour un appareil donné.
    Cette configuration est conçue pour être consommée directement par n8n.
    """
    # 1. Trouver l'appareil
    devices = _load()
    device = next((d for d in devices if d.get("ip") == ip), None)
    if not device and ip in KNOWN_DEVICES:
        device = KNOWN_DEVICES[ip]
        
    if not device:
        raise HTTPException(status_code=404, detail=f"Appareil avec l'IP {ip} non trouvé.")
        
    # 2. Vérifier son type et récupérer le catalogue
    dtype = device.get("type")
    if dtype not in CATALOGUE_CONSTRUCTEURS:
        raise HTTPException(status_code=400, detail=f"Aucune action disponible pour le type '{dtype}'.")
        
    catalog = CATALOGUE_CONSTRUCTEURS[dtype]
    actions = catalog.get("actions", {})
    if action_name not in actions:
        raise HTTPException(status_code=404, detail=f"Action '{action_name}' non définie pour le type '{dtype}'.")
        
    action = actions[action_name]
    
    # 3. Formater la payload si des variables sont définies
    payload = action.get("payload", "")
    variables = device.get("variables", {})
    if isinstance(payload, str) and variables:
        try:
            payload = payload.format(**variables)
        except Exception as e:
            log.warning("Échec du formatage de la payload pour %s: %s", ip, e)
            
    # 4. Construire la réponse de configuration résolue
    config = {
        "ip": ip,
        "name": device.get("name"),
        "type": dtype,
        "action": action_name,
        "protocol": action.get("protocol"),
        "port": action.get("port"),
        "payload": payload
    }
    
    # Ajouter les paramètres spécifiques à HTTP
    if action.get("protocol") == "HTTP":
        config["method"] = action.get("method", "POST")
        config["path"] = action.get("path", "")
        config["url"] = f"http://{ip}:{action.get('port', 80)}{action.get('path', '')}"
        config["headers"] = action.get("headers", {})
        
    return config


@app.post("/api/devices", status_code=201, summary="Enregistrement manuel")
async def add_device(body: DeviceIn):
    """Ajoute ou met à jour un appareil manuellement."""
    devices = _merge(_load(), body.model_dump())
    _save(devices)
    return {"ok": True, "total": len(devices)}


@app.delete("/api/devices/{ip}", summary="Suppression par IP")
async def delete_device(ip: str):
    """Supprime un appareil du registre par son adresse IP."""
    devices = _load()
    filtered = [d for d in devices if d.get("ip") != ip]
    if len(filtered) == len(devices):
        raise HTTPException(status_code=404, detail=f"Aucun appareil avec l'IP {ip}")
    _save(filtered)
    return {"ok": True, "removed": ip}


# ── Scan ─────────────────────────────────────────────────────────────────────

@app.post("/api/scan", summary="Scan réseau (mDNS + ping)")
async def trigger_scan(bg: BackgroundTasks):
    """
    Déclenche en arrière-plan :
      1. Écoute mDNS _googlecast._tcp.local. (3 s) → Android TV / Chromecast
      2. Ping des appareils statiques définis dans KNOWN_DEVICES
    Retourne immédiatement (la réponse arrive avant la fin du scan).
    """
    bg.add_task(_full_scan)
    return {
        "ok": True,
        "message": f"Scan démarré (mDNS {int(MDNS_SCAN_DURATION)}s + ping connus)",
    }



# ── Virtual Actions ──────────────────────────────────────────────────────────

@app.get("/api/icons/{filename}", summary="Servir les icônes de la console")
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


class ButtonConfigIn(BaseModel):
    btn_id: str
    device_ip: str
    target_app: str
    title: str | None = None
    icon: str | None = None


def resolve_btn_metadata(device_ip: str, target_app: str):
    devices = _load()
    device = next((d for d in devices if d.get("ip") == device_ip), None)
    if not device and device_ip in KNOWN_DEVICES:
        device = KNOWN_DEVICES[device_ip]
        
    device_name = device.get("name", "Appareil") if device else "Appareil"
    
    # Extraire la pièce ou simplifier le nom
    room = "Appareil"
    for r in ["Salon", "Chambre", "Cuisine", "Bureau"]:
        if r.lower() in device_name.lower():
            room = r
            break
    if room == "Appareil" and device:
        room = device_name.split()[-1]
        
    # Titre convivial de l'application
    app_clean = target_app.replace("launch_", "").replace("_", " ")
    app_friendly = " ".join(w.capitalize() for w in app_clean.split())
    
    title = f"{app_friendly} ({room})"
    icon = target_app.replace("launch_", "")
    return title, icon


@app.get("/api/actions", summary="Liste des actions configurées pour la console")
async def get_actions():
    """Renvoie la liste des 9 boutons de la console (configurés ou placeholder)."""
    actions = _load_actions()
    result = []
    for i in range(1, 10):
        btn_id = f"papyconnect_btn_{i}"
        cfg = actions.get(btn_id)
        if cfg:
            result.append({
                "id": btn_id,
                "title": cfg.get("title", f"Bouton {i}"),
                "icon": cfg.get("icon", "default"),
                "state": cfg.get("state", "inactive")
            })
        else:
            result.append({
                "id": btn_id,
                "title": f"Touche {i} (non configurée)",
                "icon": "default",
                "state": "inactive"
            })
    return result


@app.post("/api/actions/config", summary="Configurer l'association d'une touche physique")
async def config_button(body: ButtonConfigIn):
    """Associe une touche physique de la console (ex: papyconnect_btn_1) à un appareil et une application."""
    log.info("Requête de configuration du bouton %s reçue (IP: %s, App: %s, Titre: %s, Icône: %s)", body.btn_id, body.device_ip, body.target_app, body.title, body.icon)
    actions = _load_actions()
    
    btn_num = None
    if body.btn_id.startswith("papyconnect_btn_"):
        try:
            btn_num = int(body.btn_id.replace("papyconnect_btn_", ""))
        except ValueError:
            pass
            
    if btn_num is None or not (1 <= btn_num <= 9):
        log.warning("Échec de configuration: Identifiant de bouton invalide: %s", body.btn_id)
        raise HTTPException(status_code=400, detail="L'identifiant du bouton doit être entre papyconnect_btn_1 et papyconnect_btn_9.")
        
    title = body.title
    icon = body.icon
    if not title or not icon:
        resolved_title, resolved_icon = resolve_btn_metadata(body.device_ip, body.target_app)
        title = title or resolved_title
        icon = icon or resolved_icon
        
    actions[body.btn_id] = {
        "device_ip": body.device_ip,
        "target_app": body.target_app,
        "title": title,
        "icon": icon,
        "state": actions.get(body.btn_id, {}).get("state", "inactive")
    }
    
    _save_actions(actions)
    log.info("Configuration du bouton %s enregistrée avec succès (Titre: %s, Icône: %s)", body.btn_id, title, icon)
    return {"ok": True, "button": body.btn_id, "title": title, "icon": icon}


@app.delete("/api/actions/{btn_id}", summary="Effacer la configuration d'un bouton")
async def delete_action(btn_id: str):
    """Efface la configuration d'un bouton par son ID (le remet à non configuré)."""
    log.info("Requête de suppression de la configuration du bouton %s", btn_id)
    actions = _load_actions()
    if btn_id not in actions:
        log.warning("Échec de suppression: Touche %s non configurée dans la console", btn_id)
        raise HTTPException(status_code=404, detail=f"Touche '{btn_id}' non configurée dans la console.")
    del actions[btn_id]
    _save_actions(actions)
    log.info("Configuration du bouton %s supprimée avec succès", btn_id)
    return {"ok": True, "removed": btn_id}


@app.post("/api/actions/execute/{btn_id}", summary="Résoudre le contrat d'exécution pour n8n")
@app.post("/api/actions/{btn_id}/execute", summary="Résoudre le contrat d'exécution pour n8n (compatibilité)")
async def execute_action(btn_id: str):
    """
    Résout l'action du bouton physique, gère le Toggle, et renvoie le contrat pour n8n.
    """
    actions = _load_actions()
    btn_config = actions.get(btn_id)
    if not btn_config:
        raise HTTPException(status_code=404, detail=f"Touche '{btn_id}' non configurée.")
        
    ip = btn_config["device_ip"]
    
    # Logique Toggle : Détermine si l'action est active et alterne
    current_state = btn_config.get("state", "inactive")
    if current_state == "active":
        action_name = "power_off"
        btn_config["state"] = "inactive"
    else:
        action_name = btn_config["target_app"]
        btn_config["state"] = "active"
        # Désactive les autres boutons sur le même appareil IP
        for b_id, b_cfg in actions.items():
            if b_id != btn_id and b_cfg.get("device_ip") == ip:
                b_cfg["state"] = "inactive"
                
    _save_actions(actions)
    
    # Trouver l'appareil
    devices = _load()
    device = next((d for d in devices if d.get("ip") == ip), None)
    if not device and ip in KNOWN_DEVICES:
        device = KNOWN_DEVICES[ip]
        
    if not device:
        raise HTTPException(status_code=404, detail=f"Appareil cible avec l'IP {ip} non trouvé.")
        
    # Récupérer le catalogue constructeur
    dtype = device.get("type")
    if dtype not in CATALOGUE_CONSTRUCTEURS:
        raise HTTPException(status_code=400, detail=f"Aucune action disponible pour le type '{dtype}'.")
        
    catalog = CATALOGUE_CONSTRUCTEURS[dtype]
    actions_cat = catalog.get("actions", {})
    if action_name not in actions_cat:
        raise HTTPException(status_code=404, detail=f"Action '{action_name}' non définie pour le type '{dtype}'.")
        
    action = actions_cat[action_name]
    
    # Formater la payload si des variables sont définies
    payload = action.get("payload", "")
    variables = device.get("variables", {})
    if isinstance(payload, str) and variables:
        try:
            payload = payload.format(**variables)
        except Exception as e:
            log.warning("Échec du formatage de la payload pour %s: %s", ip, e)
            
    # Construire le contrat d'exécution
    config = {
        "action_id": btn_id,
        "ip": ip,
        "name": device.get("name"),
        "type": dtype,
        "action": action_name,
        "protocol": action.get("protocol"),
        "port": action.get("port"),
        "payload": payload
    }
    
    # Paramètres HTTP spécifiques
    if action.get("protocol") == "HTTP":
        config["method"] = action.get("method", "POST")
        config["path"] = action.get("path", "")
        config["url"] = f"http://{ip}:{action.get('port', 80)}{action.get('path', '')}"
        config["headers"] = action.get("headers", {})
        
    return config

