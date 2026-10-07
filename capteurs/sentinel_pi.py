#!/usr/bin/env python3
# =====================================================
#  SENTINEL-X · Raspberry Pi 4 + GrovePi+
#  Tous les capteurs sur le GrovePi+ (plus d'ESP)
#  Lancer :  python3 sentinel_pi.py      (Ctrl+C pour arrêter)
# =====================================================
import time, json, hashlib, struct, math, os, threading

try:
    from smbus2 import SMBus
except ImportError:
    from smbus import SMBus

try:
    import paho.mqtt.client as mqtt
except ImportError:
    mqtt = None

# ---------- CE QUI EST BRANCHÉ : True = oui, False = non ----------
AVEC_GAZ = True     # A0
AVEC_SON = True     # A1
AVEC_PIR = True     # A2
AVEC_HP  = True     # D3 haut-parleur
AVEC_US  = True     # D4 ultrasons
AVEC_DHT = True     # D7
AVEC_LED = True     # D8
AVEC_LCD = True     # I2C

# ---------- PORTS DU GROVEPI+ ----------
PORT_GAZ, PORT_SON, PORT_PIR = 0, 1, 2      # A0, A1, A2
PORT_HP, PORT_US, PORT_DHT, PORT_LED = 3, 4, 7, 8
DHT_TYPE = 0        # 0 = DHT11 (bleu), 1 = DHT22 (blanc)

# ---------- SEUILS (à ajuster en regardant le terminal) ----------
SEUIL_TEMP       = 30.0   # °C
SEUIL_HUM        = 80.0   # %
DIST_ALERTE      = 30     # cm
DIST_VIGILANCE   = 100    # cm
ECART_GAZ_ALERTE = 100    # alerte si gaz > référence + 100
SEUIL_SON        = 600    # 0..1023
SEUIL_PIR        = 400    # A2 > 400 = mouvement

DHT_TOLERANCE    = 30     # s : on ne signale « DHT erreur » qu'après 30 s sans aucune lecture valide
DUREE_ALARME     = 5      # s : l'alarme sonne au moins 5 s, relancée tant que l'alerte dure

JOURNAL = "journal_sentinel.jsonl"  # journal chaîné (hash) des événements

# ---------- MQTT (envoi vers le serveur : API + dashboard) ----------
MQTT_HOST = os.getenv("MQTT_HOST", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_USER = os.getenv("MQTT_USER") or None
MQTT_PASS = os.getenv("MQTT_PASS") or None

# =====================================================
#  GrovePi+ (adresse 0x04) — mini pilote
# =====================================================
GP = 0x04
bus = SMBus(1)
verrou_i2c = threading.RLock()   # la sirène tourne dans un thread : un seul accès au GrovePi à la fois

def gp_cmd(cmd, pin=0, v1=0, v2=0):
    bus.write_i2c_block_data(GP, 1, [cmd, pin, v1, v2])

def gp_lire(n=32):
    try:
        bus.read_byte(GP)
    except OSError:
        pass
    return bus.read_i2c_block_data(GP, 1, n)

def essai(f, defaut=None, tentatives=3):
    for _ in range(tentatives):
        try:
            with verrou_i2c:          # commande + lecture sans être coupé par la sirène
                return f()
        except OSError:
            time.sleep(0.05)
    return defaut

def version():
    def f():
        gp_cmd(8); time.sleep(0.1)
        r = gp_lire(4)
        return f"{r[1]}.{r[2]}.{r[3]}"
    return essai(f, "inconnue")

def pin_mode(pin, sortie):
    essai(lambda: gp_cmd(5, pin, 1 if sortie else 0))

def digital_write(pin, v):
    essai(lambda: gp_cmd(2, pin, 1 if v else 0))

def analog_write(pin, v):
    essai(lambda: gp_cmd(4, pin, max(0, min(255, v))))

def analog_read(pin):
    def f():
        gp_cmd(3, pin); time.sleep(0.05)
        r = gp_lire(3)
        return r[1] * 256 + r[2]
    v = essai(f, -1)
    return v if 0 <= v <= 1023 else -1      # 65535 = le GrovePi+ ne répond plus : lecture invalide

def ultrason(pin):
    def f():
        gp_cmd(7, pin); time.sleep(0.1)
        r = gp_lire(3)
        return r[1] * 256 + r[2]
    d = essai(f, -1)
    return d if 0 < d < 500 else -1

def dht(pin, typ):
    def f():
        gp_cmd(40, pin, typ); time.sleep(0.6)
        r = gp_lire(9)
        t = struct.unpack('f', bytes(r[1:5]))[0]
        h = struct.unpack('f', bytes(r[5:9]))[0]
        return t, h
    v = essai(f, (math.nan, math.nan))
    t, h = v
    if math.isnan(t) or math.isnan(h) or not (-20 < t < 80) or not (0 <= h <= 100):
        return math.nan, math.nan
    return t, h

# =====================================================
#  Écran Grove LCD RGB (texte 0x3E, couleur 0x62 ou 0x30)
# =====================================================
LCD_TXT = 0x3E
LCD_RGB = None

def lcd_init():
    global LCD_RGB
    for adr in (0x62, 0x30):
        try:
            bus.read_byte(adr); LCD_RGB = adr; break
        except OSError:
            pass
    try:
        if LCD_RGB == 0x62:
            bus.write_byte_data(0x62, 0, 0); bus.write_byte_data(0x62, 1, 0)
            bus.write_byte_data(0x62, 0x08, 0xAA)
        elif LCD_RGB == 0x30:
            bus.write_byte_data(0x30, 0x00, 0x07); time.sleep(0.01)
            bus.write_byte_data(0x30, 0x04, 0x15)
        lcd_cmd(0x28); lcd_cmd(0x0C); lcd_cmd(0x01); time.sleep(0.05)
    except OSError:
        print("Ecran LCD non trouve (verifie la prise I2C)")

def lcd_cmd(c):
    bus.write_byte_data(LCD_TXT, 0x80, c)

def couleur(r, g, b):
    if not AVEC_LCD or LCD_RGB is None:
        return
    try:
        if LCD_RGB == 0x62:
            bus.write_byte_data(0x62, 4, r); bus.write_byte_data(0x62, 3, g); bus.write_byte_data(0x62, 2, b)
        else:
            bus.write_byte_data(0x30, 0x06, r); bus.write_byte_data(0x30, 0x07, g); bus.write_byte_data(0x30, 0x08, b)
    except OSError:
        pass

_texte = ["", ""]
def texte(l1, l2=""):
    if not AVEC_LCD:
        return
    l1, l2 = l1[:16].ljust(16), l2[:16].ljust(16)
    if [l1, l2] == _texte:
        return
    try:
        for ligne, adr in ((l1, 0x80), (l2, 0xC0)):
            lcd_cmd(adr)
            for ch in ligne:
                bus.write_byte_data(LCD_TXT, 0x40, ord(ch) if ord(ch) < 128 else ord('?'))
        _texte[:] = [l1, l2]
    except OSError:
        pass

# =====================================================
#  LED + haut-parleur
# =====================================================
def bip(duree=0.15, n=1):
    for _ in range(n):
        if AVEC_HP:  analog_write(PORT_HP, 128)
        if AVEC_LED: digital_write(PORT_LED, 1)
        time.sleep(duree)
        if AVEC_HP:  analog_write(PORT_HP, 0)
        if AVEC_LED: digital_write(PORT_LED, 0)
        time.sleep(duree)

# ---- Sirène : tourne en fond, sonne tant que l'heure de fin n'est pas passée ----
_fin_alarme = 0.0
_verrou_alarme = threading.Lock()

def alarme():
    """Appelée à chaque seconde d'alerte : (re)lance la sirène pour DUREE_ALARME s."""
    global _fin_alarme
    with _verrou_alarme:
        _fin_alarme = time.time() + DUREE_ALARME

def couper_alarme():
    global _fin_alarme
    with _verrou_alarme:
        _fin_alarme = 0.0

def _sirene():
    allume = False
    while True:
        with _verrou_alarme:
            active = time.time() < _fin_alarme
        if active:
            allume = not allume                    # bip-bip rapide : 0,25 s on / 0,25 s off
            if AVEC_HP:  analog_write(PORT_HP, 200 if allume else 0)
            if AVEC_LED: digital_write(PORT_LED, 1 if allume else 0)
            time.sleep(0.25)
        else:
            if allume:                             # fin de l'alarme : on éteint tout
                allume = False
                if AVEC_HP:  analog_write(PORT_HP, 0)
                if AVEC_LED: digital_write(PORT_LED, 0)
            time.sleep(0.1)

# =====================================================
#  Journal chaîné (chaque ligne contient le hash de la précédente)
# =====================================================
def lignes_valides():
    """Lit le journal en ignorant les lignes abîmées (ex. coupure de courant pendant une écriture)."""
    if not os.path.exists(JOURNAL):
        return []
    evts = []
    with open(JOURNAL, "rb") as f:
        for ligne in f.read().replace(b"\x00", b"").splitlines():
            try:
                evt = json.loads(ligne)
                if "hash" in evt:
                    evts.append(evt)
            except ValueError:
                print("Journal : ligne abîmée ignorée")
    return evts

def dernier_hash():
    evts = lignes_valides()
    return evts[-1]["hash"] if evts else "0" * 64

prev_hash = dernier_hash()

def journaliser(type_evt, details):
    global prev_hash
    evt = {"ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "type": type_evt,
           "details": details, "prev": prev_hash}
    evt["hash"] = hashlib.sha256(json.dumps(evt, sort_keys=True).encode()).hexdigest()
    with open(JOURNAL, "a") as f:
        f.write(json.dumps(evt) + "\n")
        f.flush(); os.fsync(f.fileno())     # écrit tout de suite sur la carte SD
    prev_hash = evt["hash"]
    publier("sentinel/evenements", evt, qos=1)
    print("  >> journal :", type_evt, evt["hash"][:12])

# =====================================================
#  MQTT
# =====================================================
client = None
if mqtt:
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="sentinel-capteurs")
    if MQTT_USER:
        client.username_pw_set(MQTT_USER, MQTT_PASS)
    client.connect_async(MQTT_HOST, MQTT_PORT)
    client.loop_start()          # reconnexion automatique si le serveur redémarre
else:
    print("paho-mqtt absent : pas d'envoi MQTT (pip install paho-mqtt)")

def publier(topic, data, qos=0):
    if client:
        client.publish(topic, json.dumps(data), qos=qos)

def renvoyer_journal():
    """Renvoie tout le journal local : l'API ignore les doublons (hash unique)."""
    for evt in lignes_valides():
        publier("sentinel/evenements", evt, qos=1)

# =====================================================
#  Démarrage
# =====================================================
print("GrovePi+ firmware :", version())
if AVEC_HP:  pin_mode(PORT_HP, True)
if AVEC_LED: pin_mode(PORT_LED, True)
if AVEC_LCD: lcd_init()

couleur(0, 80, 255); texte("Sentinel-X", "Demarrage...")
bip(0.1, 2)
threading.Thread(target=_sirene, daemon=True).start()

print("Stabilisation des capteurs (10 s), ne bouge pas devant le PIR...")
for i in range(10, 0, -1):
    couleur(0, 80, 255 if i % 2 else 120)
    texte("Sentinel-X", f"Stabilisation {i:2d}")
    print(i, "s"); time.sleep(1)

ref_gaz = 0
if AVEC_GAZ:
    mesures = [analog_read(PORT_GAZ) for _ in range(10)]
    mesures = [m for m in mesures if m >= 0]
    ref_gaz = sum(mesures) // len(mesures) if mesures else 0
    print("Reference gaz (air normal) :", ref_gaz)

print("Sentinel-X : surveillance active")
time.sleep(1); renvoyer_journal()
journaliser("demarrage", {"ref_gaz": ref_gaz})
etat_prec = None
dht_ok = None          # dernière lecture valide du DHT : (temp, hum, heure)

# =====================================================
#  Boucle principale
# =====================================================
try:
    while True:
        temp, hum = dht(PORT_DHT, DHT_TYPE) if AVEC_DHT else (math.nan, math.nan)
        # Le DHT11 rate parfois une lecture : on garde la dernière bonne valeur pendant DHT_TOLERANCE s
        if not math.isnan(temp):
            dht_ok = (temp, hum, time.time())
        elif dht_ok and time.time() - dht_ok[2] < DHT_TOLERANCE:
            temp, hum = dht_ok[0], dht_ok[1]
        dist     = ultrason(PORT_US) if AVEC_US else -1
        gaz      = analog_read(PORT_GAZ) if AVEC_GAZ else 0
        son      = analog_read(PORT_SON) if AVEC_SON else 0
        pir_val  = analog_read(PORT_PIR) if AVEC_PIR else 0
        presence = AVEC_PIR and pir_val > SEUIL_PIR
        dht_err  = AVEC_DHT and math.isnan(temp)

        # ----- Terminal -----
        ligne = []
        if AVEC_DHT: ligne.append("DHT: erreur" if dht_err else f"T: {temp:.1f}C  H: {hum:.0f}%")
        if AVEC_US:  ligne.append(f"Dist: {dist if dist > 0 else '--'} cm")
        if AVEC_PIR: ligne.append(f"PIR: {'MOUVEMENT' if presence else 'rien'}")
        if AVEC_GAZ: ligne.append(f"Gaz: {gaz} (ref {ref_gaz})")
        if AVEC_SON: ligne.append(f"Son: {son}")
        print(" | ".join(ligne))

        # ----- Décision -----
        alertes, vigilance = [], False
        if AVEC_DHT and not dht_err and temp > SEUIL_TEMP: alertes.append("temperature")
        if AVEC_DHT and not dht_err and hum  > SEUIL_HUM:  alertes.append("humidite")
        if AVEC_US  and 0 < dist < DIST_ALERTE:             alertes.append("intrusion")
        if AVEC_GAZ and ref_gaz > 0 and gaz > ref_gaz + ECART_GAZ_ALERTE: alertes.append("gaz")
        if AVEC_SON and son > SEUIL_SON:                     alertes.append("bruit")
        # Levée de doute : mouvement + approche = alerte
        if AVEC_PIR and AVEC_US and presence and 0 < dist < DIST_VIGILANCE: alertes.append("presence")
        if AVEC_PIR and not AVEC_US and presence:                         alertes.append("mouvement")

        if not alertes:
            if presence: vigilance = True
            if AVEC_US and 0 < dist < DIST_VIGILANCE: vigilance = True
            if AVEC_DHT and not dht_err and (temp > SEUIL_TEMP - 3 or hum > SEUIL_HUM - 10): vigilance = True
            if AVEC_GAZ and gaz > ref_gaz + ECART_GAZ_ALERTE // 2: vigilance = True

        # La référence gaz suit doucement l'air normal (sauf pendant une alerte gaz)
        if AVEC_GAZ and 0 <= gaz < ref_gaz + ECART_GAZ_ALERTE:
            ref_gaz = (ref_gaz * 19 + gaz) // 20

        # ----- Écran -----
        l1 = "DHT erreur" if dht_err else (f"{temp:.0f}C {hum:.0f}%  " + (f"{dist}cm" if dist > 0 else "") if AVEC_DHT else "Sentinel-X")
        if alertes:      etat = "ALERTE"       # une alerte passe avant une panne du DHT
        elif dht_err:    etat = "DHT"
        elif vigilance:  etat = "VIGILANCE"
        else:            etat = "OK"

        if etat == "DHT":         couleur(255, 0, 255);  texte(l1, "Verifier DHT")
        elif etat == "ALERTE":    couleur(255, 0, 0);    texte(l1, "ALERTE " + alertes[0]); alarme()
        elif time.time() < _fin_alarme: couleur(255, 0, 0); texte(l1, "Fin d'alarme...")   # les 5 s après l'alerte
        elif etat == "VIGILANCE": couleur(255, 120, 0);  texte(l1, "Vigilance")
        else:                     couleur(0, 200, 80);   texte(l1, "Tout est OK")

        # ----- Envoi de la mesure au serveur (1 / s) -----
        publier("sentinel/capteurs", {
            "ts": int(time.time() * 1000),
            "temp": None if dht_err or not AVEC_DHT else round(temp, 1),
            "hum": None if dht_err or not AVEC_DHT else round(hum),
            "dist": dist, "gaz": gaz, "ref_gaz": ref_gaz, "son": son, "pir": bool(presence),
            "etat": "dht" if etat == "DHT" else etat.lower(), "alertes": alertes,
        })

        # ----- Journal : on note chaque changement d'état -----
        cle = (etat, tuple(alertes))
        if cle != etat_prec:
            journaliser("dht" if etat == "DHT" else etat.lower(), {"alertes": alertes, "temp": None if dht_err else round(temp, 1),
                                       "hum": None if dht_err else round(hum), "dist": dist,
                                       "gaz": gaz, "son": son, "pir": presence})
            etat_prec = cle

        time.sleep(1)

except KeyboardInterrupt:
    print("\nArret.")
    couper_alarme(); time.sleep(0.3)
    journaliser("arret", {})
    couleur(0, 0, 0); texte("Sentinel-X", "Arrete")
    if AVEC_HP:  analog_write(PORT_HP, 0)
    if AVEC_LED: digital_write(PORT_LED, 0)
