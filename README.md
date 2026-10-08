# Sentinel-X · boîte noire de sécurité (Raspberry Pi 4 + GrovePi+)

Capteurs → **MQTT** → **API** (journal chaîné SHA-256) → **dashboard** avec timeline rejouable.

```
capteurs/sentinel_pi.py ──MQTT──> Mosquitto ──> api (FastAPI + SQLite) ──> dashboard (React)
   (GrovePi+, LCD, alarme)          :1883            :8000                     :8080
```

## Structure
| Dossier | Contenu |
|---|---|
| `capteurs/` | `sentinel_pi.py` (capteurs + écran + alarme + journal + MQTT), `simulateur.py` (fausses données sans le Pi), `sentinel.service` (démarrage auto) |
| `api/` | API FastAPI : stockage, incidents, replay, vérification d'intégrité · `test_chaine.py` |
| `dashboard/` | Interface React (Live, Timeline, Journal) |
| `mosquitto/` | Config du broker MQTT (si pas déjà installé) |
| `.github/workflows/ci.yml` | CI : tests de la chaîne de hash, build du dashboard, build Docker |

## Installation sur le Pi
```bash
# 1. Copier le projet (depuis le PC)
scp -r sentinel-x admin@sentinel.local:~/

# 2. Serveur : API + dashboard (Mosquitto déjà installé sur le Pi)
cd ~/sentinel-x
API_URL=http://<IP-du-Pi>:8000 docker compose up -d --build
#    Mosquitto PAS installé ?  ->  API_URL=http://<IP-du-Pi>:8000 docker compose --profile mqtt up -d --build

# 3. Script capteurs
sudo apt install -y python3-smbus2 python3-paho-mqtt
rm -f capteurs/journal_sentinel.jsonl          # repartir d'un journal propre
python3 capteurs/sentinel_pi.py                # test ; Ctrl+C pour arrêter

# 4. Démarrage automatique du script
sudo cp capteurs/sentinel.service /etc/systemd/system/
sudo systemctl enable --now sentinel
```
Dashboard : **http://IP-du-Pi:8080** · API : **http://IP-du-Pi:8000/docs**

## Tester sans le Pi (sur un PC)
```bash
docker run -d -p 1883:1883 eclipse-mosquitto:2 mosquitto -c /mosquitto-no-auth.conf
cd api && pip install -r requirements.txt && uvicorn main:app --port 8000
python3 capteurs/simulateur.py                # incident toutes les 2 minutes
cd dashboard && echo VITE_API_URL=http://localhost:8000 > .env && npm install && npm run dev
```

## Vérifications rapides
```bash
mosquitto_sub -h localhost -u api -P "$MQTT_API_PASS" -t 'sentinel/#' -v   # voir passer les messages (après : set -a; . ./.env)
curl http://localhost:8000/api/live                 # dernière mesure
curl http://localhost:8000/api/integrite            # {"ok": true, ...}
cd api && pytest -q                                  # 5 tests
```

## Topics MQTT
- `sentinel/capteurs` : 1 mesure / seconde `{ts, temp, hum, dist, gaz, ref_gaz, son, pir, etat, alertes}`
- `sentinel/evenements` (QoS 1) : changement d'état `{ts, type, details, prev, hash}` avec `hash = sha256(json trié sans "hash")`

## Sécurité
- **MQTT authentifié** : plus de connexion anonyme. Sur le Pi, une seule commande : `./securiser_mqtt.sh`
  - crée `.env` avec des mots de passe aléatoires (jamais versionné, voir `.env.example`) ;
  - génère `mosquitto/secrets/passwd` (mots de passe **hachés**) et applique `mosquitto/acl` ;
  - redémarre Mosquitto, l'API et le service capteurs.
- **Moindre privilège (ACL)** : le compte `capteurs` peut seulement **écrire** `sentinel/capteurs` et `sentinel/evenements`, le compte `api` peut seulement **lire** `sentinel/#`. Un compte volé ne permet pas d'injecter de faux événements depuis l'API.
- Connexions refusées visibles : `docker logs mosquitto | grep "not authorised"`.
- Simulateur avec le broker sécurisé : `python3 capteurs/simulateur.py --host <ip> --user capteurs --password <MQTT_CAPTEURS_PASS>`.
- Limite connue du hash chaîné : il détecte une **modification** ou une **suppression au milieu**, mais pas la suppression des **derniers** événements → amélioration : copie du dernier hash ailleurs (autre machine, signature horodatée).
