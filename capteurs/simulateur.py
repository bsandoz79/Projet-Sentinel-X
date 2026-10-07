#!/usr/bin/env python3
"""
Simulateur : envoie de fausses mesures et événements en MQTT, au même format que sentinel_pi.py.
Permet de tester API + dashboard SANS le Pi ni les capteurs.
  python3 simulateur.py --host sentinel.local          (incident toutes les 2 min)
"""
import argparse, hashlib, json, random, time
import paho.mqtt.client as mqtt

ap = argparse.ArgumentParser()
ap.add_argument("--host", default="localhost"); ap.add_argument("--port", type=int, default=1883)
ap.add_argument("--user"); ap.add_argument("--password")
ap.add_argument("--periode", type=int, default=120, help="secondes entre deux incidents")
a = ap.parse_args()

c = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"sentinel-simu-{random.randint(0, 9999)}")
if a.user: c.username_pw_set(a.user, a.password)
c.connect(a.host, a.port); c.loop_start()

prev = "0" * 64
def journaliser(type_evt, details):
    global prev
    e = {"ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "type": type_evt, "details": details, "prev": prev}
    e["hash"] = hashlib.sha256(json.dumps(e, sort_keys=True).encode()).hexdigest()
    prev = e["hash"]
    c.publish("sentinel/evenements", json.dumps(e), qos=1)
    print("journal :", type_evt, details.get("alertes"))

journaliser("demarrage", {"ref_gaz": 300})
t0, etat_prec = time.time(), None
while True:
    dt = int(time.time() - t0) % a.periode - 40        # incident de dt=0 à 30
    m = {"ts": int(time.time() * 1000), "temp": round(22.5 + random.uniform(-.2, .2), 1),
         "hum": 45 + random.randint(-1, 1), "dist": 180 + random.randint(-2, 2), "gaz": 300 + random.randint(-5, 5),
         "ref_gaz": 300, "son": 120 + random.randint(-30, 30), "pir": False}
    if -8 <= dt < 30: m["pir"] = True
    if -8 <= dt < 0: m["dist"] = int(180 - (dt + 8) / 8 * 150)
    elif 0 <= dt < 25: m["dist"] = 22 + random.randint(-2, 2)
    al = []
    if 0 < m["dist"] < 30: al.append("intrusion")
    if m["pir"] and 0 < m["dist"] < 100: al.append("presence")
    m["alertes"] = al
    m["etat"] = "alerte" if al else ("vigilance" if m["pir"] or m["dist"] < 100 else "ok")
    c.publish("sentinel/capteurs", json.dumps(m))
    cle = (m["etat"], tuple(al))
    if cle != etat_prec:
        journaliser(m["etat"], {k: v for k, v in m.items() if k not in ("ts", "etat")})
        etat_prec = cle
    time.sleep(1)
