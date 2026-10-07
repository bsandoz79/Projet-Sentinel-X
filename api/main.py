"""
SENTINEL-X · API
- écoute MQTT : sentinel/capteurs (1 mesure / s) et sentinel/evenements (journal chaîné)
- stocke dans SQLite
- sert le dashboard : /api/live, /api/incidents, /api/incidents/{id}/replay, /api/evenements, /api/integrite
Lancer en local : uvicorn main:app --host 0.0.0.0 --port 8000
"""
import json
import os
import sqlite3
import threading
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone

import paho.mqtt.client as mqtt
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from chaine import verifier_chaine

MQTT_HOST = os.getenv("MQTT_HOST", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_USER = os.getenv("MQTT_USER") or None
MQTT_PASS = os.getenv("MQTT_PASS") or None
DB_PATH = os.getenv("DB_PATH", "sentinel.db")
GARDER_JOURS = int(os.getenv("GARDER_JOURS", "7"))   # mesures conservées
AVANT, APRES = 30, 30                                 # secondes autour d'un incident

TITRES = {
    "intrusion": "Intrusion détectée", "presence": "Présence confirmée", "mouvement": "Mouvement détecté",
    "gaz": "Fuite de gaz", "temperature": "Température anormale", "humidite": "Humidité anormale",
    "bruit": "Bruit fort",
}

verrou = threading.Lock()
db = sqlite3.connect(DB_PATH, check_same_thread=False)
db.row_factory = sqlite3.Row
db.executescript("""
CREATE TABLE IF NOT EXISTS mesures (ts INTEGER PRIMARY KEY, data TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS evenements (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts TEXT NOT NULL, type TEXT NOT NULL, details TEXT NOT NULL,
  prev TEXT NOT NULL, hash TEXT NOT NULL UNIQUE
);
""")
db.commit()


# ---------------------------------------------------------------- outils
def iso_vers_ms(ts: str) -> int:
    d = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    if d.tzinfo is None:
        d = d.replace(tzinfo=timezone.utc)
    return int(d.timestamp() * 1000)


def lignes_evenements(sql="SELECT * FROM evenements ORDER BY id", args=()):
    with verrou:
        rows = db.execute(sql, args).fetchall()
    return [{"id": r["id"], "ts": r["ts"], "type": r["type"], "details": json.loads(r["details"]),
             "prev": r["prev"], "hash": r["hash"]} for r in rows]


def calculer_incidents():
    """Un incident = de la 1re alerte jusqu'au retour à un état sans alerte."""
    incidents, courant = [], None
    for e in lignes_evenements():
        alertes = e["details"].get("alertes") or []
        if e["type"] == "alerte":
            if courant is None:
                courant = {"debut": e["ts"], "fin": None, "alertes": [], "evenements": []}
            courant["evenements"].append(e["id"])
            courant["alertes"] += [a for a in alertes if a not in courant["alertes"]]
        elif courant is not None:
            courant["evenements"].append(e["id"])
            courant["fin"] = e["ts"]
            incidents.append(courant)
            courant = None
    if courant is not None:
        incidents.append(courant)          # incident encore en cours
    for i, inc in enumerate(incidents, start=1):
        inc["id"] = i
        prio = [a for a in ("gaz", "temperature", "intrusion", "presence", "mouvement", "bruit", "humidite") if a in inc["alertes"]]
        inc["titre"] = TITRES.get(prio[0], "Incident") if prio else "Incident"
        if "gaz" in inc["alertes"] and "temperature" in inc["alertes"]:
            inc["titre"] = "Départ de feu (chaleur + gaz)"
    return incidents


# ---------------------------------------------------------------- MQTT
def on_connect(client, userdata, flags, reason_code, properties=None):
    print("MQTT connecté :", reason_code)
    client.subscribe([("sentinel/capteurs", 0), ("sentinel/evenements", 1)])


def on_message(client, userdata, msg):
    try:
        data = json.loads(msg.payload)
        with verrou:
            if msg.topic == "sentinel/capteurs":
                db.execute("INSERT OR REPLACE INTO mesures VALUES (?, ?)", (int(data["ts"]), json.dumps(data)))
            elif msg.topic == "sentinel/evenements":
                db.execute(
                    "INSERT OR IGNORE INTO evenements (ts, type, details, prev, hash) VALUES (?, ?, ?, ?, ?)",
                    (data["ts"], data["type"], json.dumps(data["details"]), data["prev"], data["hash"]))
            db.commit()
    except Exception as ex:  # un message mal formé ne doit pas arrêter l'API
        print("Message ignoré :", msg.topic, ex)


def nettoyage():
    while True:
        limite = int(time.time() * 1000) - GARDER_JOURS * 86400_000
        with verrou:
            db.execute("DELETE FROM mesures WHERE ts < ?", (limite,))
            db.commit()
        time.sleep(3600)


@asynccontextmanager
async def lifespan(app):
    client = None
    if os.getenv("SANS_MQTT") != "1":
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="sentinel-api")
        if MQTT_USER:
            client.username_pw_set(MQTT_USER, MQTT_PASS)
        client.on_connect, client.on_message = on_connect, on_message
        client.connect_async(MQTT_HOST, MQTT_PORT)
        client.loop_start()
        threading.Thread(target=nettoyage, daemon=True).start()
    yield
    if client:
        client.loop_stop()


app = FastAPI(title="Sentinel-X API", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["GET"], allow_headers=["*"])


# ---------------------------------------------------------------- routes
@app.get("/api/live")
def live():
    with verrou:
        r = db.execute("SELECT data FROM mesures ORDER BY ts DESC LIMIT 1").fetchone()
    if not r:
        raise HTTPException(503, "Aucune mesure reçue (le script capteurs tourne-t-il ?)")
    return json.loads(r["data"])


@app.get("/api/incidents")
def incidents():
    return [{k: v for k, v in i.items() if k != "evenements"} for i in reversed(calculer_incidents())]


@app.get("/api/incidents/{inc_id}/replay")
def replay(inc_id: int):
    inc = next((i for i in calculer_incidents() if i["id"] == inc_id), None)
    if not inc:
        raise HTTPException(404, "Incident inconnu")
    debut = iso_vers_ms(inc["debut"])
    fin = iso_vers_ms(inc["fin"]) if inc["fin"] else int(time.time() * 1000)
    fin = min(fin, debut + 10 * 60_000)               # 10 min max
    with verrou:
        rows = db.execute("SELECT data FROM mesures WHERE ts BETWEEN ? AND ? ORDER BY ts",
                          (debut - AVANT * 1000, fin + APRES * 1000)).fetchall()
    mesures = []
    for r in rows:
        m = json.loads(r["data"])
        m["t"] = round((m["ts"] - debut) / 1000)
        mesures.append(m)
    evts = [e for e in lignes_evenements() if e["id"] in inc["evenements"]]
    return {**{k: v for k, v in inc.items() if k != "evenements"}, "mesures": mesures, "evenements": evts}


@app.get("/api/evenements")
def evenements():
    return lignes_evenements()


@app.get("/api/integrite")
def integrite():
    return verifier_chaine(lignes_evenements())


@app.get("/api/sante")
def sante():
    return {"ok": True}
