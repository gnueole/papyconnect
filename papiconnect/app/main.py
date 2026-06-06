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

# Appareils à IP fixe — détectés par ping lors de chaque scan
# Complète selon ton réseau (ampli, TV câblée, box domotique…)
# Le catalogue définit le gabarit (Template) de l'action sans connaître l'appareil
CATALOGUE_CONSTRUCTEURS = {
    "amplifier": {
        "icon": "amplifier",
        "tuto": """
            <h3>🔊 Configuration Amplificateur Denon / Marantz</h3>
            <p>Le pilotage s'effectue en TCP/Telnet brut sur le port 23.</p>
            <ul>
                <li><b>Impératif :</b> Passe l'option <i>Network Control</i> sur "Always On" dans les menus de l'ampli pour éviter un boot de 30s.</li>
                <li>La commande utilise le protocole standard Denon AVR pour basculer les sources instantanément.</li>
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
            <h3>📺 Configuration TV Sony Bravia</h3>
            <p>Le pilotage s'effectue en HTTP POST.</p>
            <ul>
                <li><b>Impératif :</b> Activez la clé pré-partagée (PSK) sur "0000" dans les paramètres réseau de votre TV.</li>
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
            }
        }
    }
}

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


@app.on_event("startup")
async def _startup() -> None:
    """Initialise le registre JSON vide s'il n'existe pas encore."""
    REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not REGISTRY_PATH.exists():
        _save([])
        log.info("Registre initialisé : %s", REGISTRY_PATH.resolve())
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
        success = await _send_tcp_command(ip, port, payload)
        if not success:
            raise HTTPException(
                status_code=502, 
                detail=f"Impossible de joindre l'appareil sur le port TCP {port}."
            )
        return {"ok": True, "message": f"Action '{action_name}' envoyée avec succès par TCP à {ip}."}
    elif protocol == "HTTP":
        path = action.get("path", "")
        url = f"http://{ip}:{port}{path}"
        headers = action.get("headers", {})
        method = action.get("method", "POST")
        success = await _send_http_command(url, method, headers, payload)
        if not success:
            raise HTTPException(
                status_code=502, 
                detail=f"Impossible de joindre l'appareil sur {url}."
            )
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
