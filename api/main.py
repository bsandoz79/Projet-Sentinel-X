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
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware

import camera
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
CREATE TABLE IF NOT EXISTS images (ts INTEGER PRIMARY KEY, fichier TEXT NOT NULL, sha256 TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS photos (
  evt_hash TEXT PRIMARY KEY, fichier TEXT NOT NULL, sha256 TEXT NOT NULL, ts INTEGER NOT NULL
);
""")
db.commit()


# ---------------------------------------------------------------- outils
def iso_vers_ms(ts: str) -> int:
    d = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    if d.tzinfo is None:
        d = d.replace(tzinfo=timezone.utc)
    return int(d.timestamp() * 1000)


def lignes_evenements(avec_photos=False):
    with verrou:
        rows = db.execute("SELECT * FROM evenements ORDER BY id").fetchall()
        photos = {p["evt_hash"]: p["sha256"] for p in db.execute("SELECT evt_hash, sha256 FROM photos")} if avec_photos else {}
    evts = []
    for r in rows:
        e = {"id": r["id"], "ts": r["ts"], "type": r["type"], "details": json.loads(r["details"]),
             "prev": r["prev"], "hash": r["hash"]}
        if r["hash"] in photos:                      # hors du hash : la photo a sa propre empreinte
            e["photo"] = f"/api/photos/{r['hash']}"
            e["photo_sha256"] = photos[r["hash"]]
        evts.append(e)
    return evts


def sauver_image(ts_ms: int, chemin: str, sha: str):
    """Image d'une séquence d'incident (1 / s) : rangée en base avec son empreinte."""
    with verrou:
        db.execute("INSERT OR IGNORE INTO images VALUES (?, ?, ?)", (ts_ms, chemin, sha))
        db.commit()


def photographier(evt_hash: str):
    """Photo prise au moment d'une alerte, rangée avec son empreinte SHA-256."""
    chemin = os.path.join(camera.PHOTOS_DIR, f"{evt_hash[:16]}.jpg")
    if camera.capturer(chemin):
        with verrou:
            db.execute("INSERT OR IGNORE INTO photos VALUES (?, ?, ?, ?)",
                       (evt_hash, chemin, camera.sha256_fichier(chemin), int(time.time() * 1000)))
            db.commit()
        print("Photo enregistrée :", chemin)


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
        nouvelle_alerte = False
        with verrou:
            if msg.topic == "sentinel/capteurs":
                db.execute("INSERT OR REPLACE INTO mesures VALUES (?, ?)", (int(data["ts"]), json.dumps(data)))
            elif msg.topic == "sentinel/evenements":
                cur = db.execute(
                    "INSERT OR IGNORE INTO evenements (ts, type, details, prev, hash) VALUES (?, ?, ?, ?, ?)",
                    (data["ts"], data["type"], json.dumps(data["details"]), data["prev"], data["hash"]))
                nouvelle_alerte = cur.rowcount == 1 and data["type"] == "alerte"
            db.commit()
        if msg.topic == "sentinel/evenements" and nouvelle_alerte and camera.disponible():
            camera.declencher()                                   # séquence 10 s avant / 10 s après
            threading.Thread(target=photographier, args=(data["hash"],), daemon=True).start()
    except Exception as ex:  # un message mal formé ne doit pas arrêter l'API
        print("Message ignoré :", msg.topic, ex)


def nettoyage():
    while True:
        limite = int(time.time() * 1000) - GARDER_JOURS * 86400_000
        with verrou:
            db.execute("DELETE FROM mesures WHERE ts < ?", (limite,))
            vieilles = db.execute("SELECT fichier FROM images WHERE ts < ?", (limite,)).fetchall()
            db.execute("DELETE FROM images WHERE ts < ?", (limite,))
            db.commit()
        for r in vieilles:
            try:
                os.remove(r["fichier"])
            except OSError:
                pass
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
    camera.demarrer(sauver_image)                                  # capture continue de la webcam
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
    evts = [e for e in lignes_evenements(avec_photos=True) if e["id"] in inc["evenements"]]
    with verrou:
        imgs = db.execute("SELECT ts, sha256 FROM images WHERE ts BETWEEN ? AND ? ORDER BY ts",
                          (debut - AVANT * 1000, fin + APRES * 1000)).fetchall()
    images = [{"ts": r["ts"], "t": round((r["ts"] - debut) / 1000), "url": f"/api/images/{r['ts']}",
               "sha256": r["sha256"]} for r in imgs]
    return {**{k: v for k, v in inc.items() if k != "evenements"}, "mesures": mesures,
            "evenements": evts, "images": images}


@app.get("/api/evenements")
def evenements():
    return lignes_evenements(avec_photos=True)


@app.get("/api/photos/{evt_hash}")
def photo(evt_hash: str):
    with verrou:
        r = db.execute("SELECT fichier FROM photos WHERE evt_hash = ?", (evt_hash,)).fetchone()
    if not r or not os.path.exists(r["fichier"]):
        raise HTTPException(404, "Pas de photo pour cet événement")
    return FileResponse(r["fichier"], media_type="image/jpeg")


@app.get("/api/images/{ts}")
def image_incident(ts: int):
    with verrou:
        r = db.execute("SELECT fichier FROM images WHERE ts = ?", (ts,)).fetchone()
    if not r or not os.path.exists(r["fichier"]):
        raise HTTPException(404, "Image introuvable")
    return FileResponse(r["fichier"], media_type="image/jpeg")


@app.get("/api/camera")
def camera_live():
    chemin = camera.image_live()
    if not chemin:
        raise HTTPException(404, "Caméra non disponible")
    return FileResponse(chemin, media_type="image/jpeg", headers={"Cache-Control": "no-store"})


@app.get("/api/camera/stream")
def camera_stream():
    if not camera.disponible():
        raise HTTPException(404, "Caméra non disponible")
    return StreamingResponse(camera.flux_mjpeg(), media_type="multipart/x-mixed-replace; boundary=frame",
                             headers={"Cache-Control": "no-store"})


@app.get("/api/integrite")
def integrite():
    return verifier_chaine(lignes_evenements())


@app.get("/api/sante")
def sante():
    return {"ok": True, "camera": camera.disponible(), "camera_images": camera.image_recente()}
