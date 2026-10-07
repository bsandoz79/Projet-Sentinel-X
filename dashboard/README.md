# Sentinel-X · Dashboard

Dashboard React (Vite) du projet Sentinel-X : état des capteurs en direct, **timeline rejouable** des incidents et **journal infalsifiable** (chaîne de hash SHA-256).

## Lancer

```bash
npm install
npm run dev
```

Ouvrir http://localhost:5173 (ou http://IP-DU-PC:5173 depuis un téléphone sur le même réseau).

## Deux modes

| Mode | Quand | Comment |
|---|---|---|
| **Démo** | L'API du Pi n'existe pas encore | `VITE_API_URL` vide (par défaut) : données simulées dans le navigateur |
| **API** | L'API FastAPI tourne sur le Pi | Copier `.env.example` en `.env` et mettre `VITE_API_URL=http://sentinel.local:8000` |

En mode démo :
- **Live** : boutons pour simuler une intrusion, une fuite de gaz ou un départ de feu (l'incident apparaît ensuite dans la Timeline).
- **Journal** : bouton « Falsifier un événement » pour montrer au jury que la modification est détectée.

## Pages

- **Live** : bandeau d'état (vert / orange / rouge / violet, comme l'écran LCD), 6 cartes capteurs avec mini-courbes, derniers incidents.
- **Timeline** : liste des incidents, lecteur (lecture / pause / vitesse ×1 à ×10 / curseur), 4 courbes avec le curseur de lecture, événements du journal qui s'allument au fur et à mesure.
- **Journal** : tous les événements avec `prev` et `hash`, vérification d'intégrité, ligne cassée en rouge.

## Contrat de l'API (à implémenter dans FastAPI)

Toutes les routes renvoient du JSON. Penser à activer le CORS pour l'adresse du dashboard.

### `GET /api/live` : dernière mesure
```json
{ "ts": 1759761090000, "temp": 22.8, "hum": 48, "dist": 180, "gaz": 304, "ref_gaz": 300,
  "son": 103, "pir": false, "etat": "ok", "alertes": [] }
```
- `ts` : millisecondes (ou date ISO)
- `etat` : `ok` | `vigilance` | `alerte` | `dht`
- `alertes` : parmi `temperature`, `humidite`, `intrusion`, `gaz`, `bruit`, `presence`, `mouvement`
- `temp` / `hum` à `null` si le DHT est en erreur, `dist` à `-1` si rien devant

### `GET /api/incidents` : liste (plus récent en premier)
```json
[{ "id": 3, "titre": "Fuite de gaz", "debut": "2026-10-06T15:59:27", "fin": "2026-10-06T16:00:27", "alertes": ["gaz"] }]
```

### `GET /api/incidents/{id}/replay` : tout pour rejouer
```json
{ "id": 3, "titre": "Fuite de gaz", "debut": "...", "fin": "...", "alertes": ["gaz"],
  "mesures": [ { "t": -30, "ts": 1759761090000, "temp": 22.8, "...": "...", "etat": "ok", "alertes": [] } ],
  "evenements": [ { "id": 10, "ts": "...", "type": "alerte", "details": {}, "prev": "…", "hash": "…" } ] }
```
- `mesures` : une par seconde, de 30 s avant à 60 s après le début ; `t` = secondes depuis le début (négatif avant)

### `GET /api/evenements` : tout le journal (ordre chronologique)
```json
[{ "id": 1, "ts": "...", "type": "demarrage", "details": { "ref_gaz": 300 }, "prev": "000…0", "hash": "…" }]
```

### `GET /api/integrite` : vérification côté serveur
```json
{ "ok": false, "total": 17, "premier_invalide": 9 }
```
- `premier_invalide` : index (0 = premier événement) du premier maillon cassé, `null` si tout est bon
- Le serveur recalcule chaque hash **avec la même méthode que celle utilisée pour l'écrire** (dans `sentinel_pi.py` : `sha256(json.dumps(evt_sans_hash, sort_keys=True))`).

## Structure

```
src/
  api/        mock.js (démo) · real.js (API du Pi) · index.js (choix du mode)
  pages/      Live.jsx · Timeline.jsx · Journal.jsx
  components/ BandeauEtat · CarteCapteur · BadgeIntegrite
  utils.js    états, seuils, SHA-256, vérification de la chaîne
```
