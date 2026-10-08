#!/usr/bin/env bash
# SENTINEL-X · sécurise Mosquitto (comptes + mots de passe + droits)
# À lancer sur le Pi, dans le dossier du projet :  ./securiser_mqtt.sh
#  1. crée .env avec des mots de passe aléatoires (s'il n'existe pas)
#  2. génère mosquitto/secrets/passwd (mots de passe hachés) + copie l'acl
#  3. redémarre Mosquitto, l'API et le script capteurs
set -e
cd "$(dirname "$0")"

if [ ! -f .env ]; then
  echo "Création de .env avec des mots de passe aléatoires"
  {
    echo "MQTT_CAPTEURS_USER=capteurs"
    echo "MQTT_CAPTEURS_PASS=$(python3 -c 'import secrets; print(secrets.token_urlsafe(24))')"
    echo "MQTT_API_USER=api"
    echo "MQTT_API_PASS=$(python3 -c 'import secrets; print(secrets.token_urlsafe(24))')"
  } > .env
fi
chmod 600 .env
set -a; . ./.env; set +a

echo "Génération des mots de passe Mosquitto (hachés)"
mkdir -p mosquitto/secrets
docker run --rm -v "$PWD/mosquitto:/m" eclipse-mosquitto:2 sh -c "
  rm -f /m/secrets/passwd /m/secrets/acl
  touch /m/secrets/passwd
  mosquitto_passwd -b /m/secrets/passwd '$MQTT_CAPTEURS_USER' '$MQTT_CAPTEURS_PASS'
  mosquitto_passwd -b /m/secrets/passwd '$MQTT_API_USER' '$MQTT_API_PASS'
  cp /m/acl /m/secrets/acl
  chown -R mosquitto:mosquitto /m/secrets
  chmod 700 /m/secrets
  chmod 600 /m/secrets/passwd /m/secrets/acl
"

echo "Redémarrage de Mosquitto (version sécurisée)"
docker rm -f mosquitto >/dev/null 2>&1 || true
docker compose up -d mosquitto
docker compose up -d --force-recreate api

if systemctl list-unit-files sentinel.service >/dev/null 2>&1; then
  sudo systemctl restart sentinel
fi
echo "OK : MQTT sécurisé. Test : docker logs mosquitto --tail 20"
