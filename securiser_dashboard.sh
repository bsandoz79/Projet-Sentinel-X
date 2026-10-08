#!/usr/bin/env bash
# SENTINEL-X · protège le dashboard par mot de passe
# À lancer sur le Pi, dans le dossier du projet :  bash securiser_dashboard.sh
#  1. ajoute DASHBOARD_USER / DASHBOARD_PASS dans .env (mot de passe aléatoire s'il n'existe pas)
#  2. génère nginx/secrets/htpasswd (mot de passe haché)
#  3. relance le dashboard (nginx) et l'API (qui n'écoute plus que sur le Pi)
# Pour changer le mot de passe : modifier DASHBOARD_PASS dans .env puis relancer ce script.
set -e
cd "$(dirname "$0")"
touch .env; chmod 600 .env

grep -q '^DASHBOARD_USER=' .env || echo "DASHBOARD_USER=sentinel" >> .env
grep -q '^DASHBOARD_PASS=' .env || echo "DASHBOARD_PASS=$(python3 -c 'import secrets; print(secrets.token_urlsafe(12))')" >> .env
grep -q '^DASHBOARD_DIST=' .env || echo "DASHBOARD_DIST=$HOME/dashboard-dist" >> .env
set -a; . ./.env; set +a

mkdir -p nginx/secrets "$DASHBOARD_DIST"
printf '%s:%s\n' "$DASHBOARD_USER" "$(openssl passwd -apr1 "$DASHBOARD_PASS")" > nginx/secrets/htpasswd
chmod 755 nginx/secrets; chmod 644 nginx/secrets/htpasswd
chmod -R a+rX "$DASHBOARD_DIST"

echo "Relance du dashboard protégé (port 8080)"
docker rm -f dashboard >/dev/null 2>&1 || true
docker compose up -d dashboard
echo "Relance de l'API (accessible seulement via le dashboard)"
docker compose up -d --build api

IP=$(hostname -I | awk '{print $1}')
echo
echo "OK : http://$IP:8080"
echo "  identifiant  : $DASHBOARD_USER"
echo "  mot de passe : $DASHBOARD_PASS   (dans le fichier .env)"
