"""
Webcam USB en capture CONTINUE (ffmpeg) :
- la webcam reste ouverte, la dernière image est réécrite ~10 fois / s dans _live.jpg
- /api/camera/stream envoie un flux vidéo MJPEG (fluide dans le navigateur)
- photo d'alerte = copie instantanée de la dernière image
"""
import asyncio
from collections import deque
import hashlib
import os
import shutil
import subprocess
import threading
import time

CAMERA = os.getenv("CAMERA", "/dev/video0")
RESOLUTION = os.getenv("CAMERA_RESOLUTION", "1280x720")
FPS = os.getenv("CAMERA_FPS", "10")
PHOTOS_DIR = os.getenv("PHOTOS_DIR", "photos")
LIVE = os.path.join(PHOTOS_DIR, "_live.jpg")
IMAGES_DIR = os.path.join(PHOTOS_DIR, "incidents")
os.makedirs(IMAGES_DIR, exist_ok=True)

# ---- Séquence d'incident : 1 image / s, 10 s AVANT et 10 s APRÈS l'alerte ----
SECONDES_AVANT = int(os.getenv("CAMERA_AVANT", "10"))
SECONDES_APRES = int(os.getenv("CAMERA_APRES", "10"))
_tampon = deque(maxlen=SECONDES_AVANT)   # les 10 dernières secondes, en mémoire
_enregistrer_jusqua = 0.0
_verrou_seq = threading.Lock()
_sauver = None                            # fonction de l'API qui range l'image en base


def disponible() -> bool:
    return os.path.exists(CAMERA)


def image_recente(max_age: float = 3.0) -> bool:
    return os.path.exists(LIVE) and time.time() - os.path.getmtime(LIVE) < max_age


def _commandes():
    # 1) la webcam fournit directement du JPEG (MJPEG) : aucun ré-encodage, très léger
    mjpeg = ["ffmpeg", "-loglevel", "error", "-f", "v4l2", "-input_format", "mjpeg",
             "-video_size", RESOLUTION, "-framerate", FPS, "-i", CAMERA,
             "-c:v", "copy", "-bsf:v", "mjpeg2jpeg",
             "-f", "image2", "-update", "1", "-atomic_writing", "1", "-y", LIVE]
    # 2) secours : format brut ré-encodé en JPEG, plus petit et moins d'images / s
    brut = ["ffmpeg", "-loglevel", "error", "-f", "v4l2", "-video_size", "640x480", "-i", CAMERA,
            "-vf", "fps=5", "-q:v", "5",
            "-f", "image2", "-update", "1", "-atomic_writing", "1", "-y", LIVE]
    return [mjpeg, brut]


def _boucle():
    """Garde ffmpeg en vie : le relance s'il s'arrête (webcam débranchée, etc.)."""
    essai = 0
    while True:
        if not disponible():
            time.sleep(5)
            continue
        cmd = _commandes()[essai % 2]
        debut = time.time()
        try:
            proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
            _, err = proc.communicate()
        except FileNotFoundError:
            print("Caméra : ffmpeg n'est pas installé")
            time.sleep(30)
            continue
        if time.time() - debut < 5:              # arrêt immédiat : on tente l'autre mode
            print("Caméra : ffmpeg arrêté ->", (err or b"").decode(errors="ignore")[-200:])
            essai += 1
        time.sleep(2)


def _ecrire(ts_ms: int, data: bytes):
    chemin = os.path.join(IMAGES_DIR, f"{ts_ms}.jpg")
    with open(chemin, "wb") as f:
        f.write(data)
    if _sauver:
        _sauver(ts_ms, chemin, hashlib.sha256(data).hexdigest())


def _boucle_sequence():
    """Toutes les secondes : garde l'image en mémoire, ou l'enregistre si un incident est en cours."""
    while True:
        debut = time.time()
        if image_recente(2):
            try:
                with open(LIVE, "rb") as f:
                    data = f.read()
            except OSError:
                data = None
            if data:
                ts = int(debut * 1000)
                with _verrou_seq:
                    en_cours = debut < _enregistrer_jusqua
                if en_cours:
                    _ecrire(ts, data)
                else:
                    _tampon.append((ts, data))
        time.sleep(max(0.0, 1.0 - (time.time() - debut)))


def declencher():
    """Appelé à chaque seconde d'alerte : sauve les 10 s d'avant puis enregistre 1 image / s
    pendant TOUT l'incident, jusqu'à 10 s après la dernière seconde d'alerte."""
    global _enregistrer_jusqua
    with _verrou_seq:
        nouvelle_sequence = time.time() >= _enregistrer_jusqua
        _enregistrer_jusqua = time.time() + SECONDES_APRES
    if nouvelle_sequence:
        while _tampon:
            ts, data = _tampon.popleft()
            _ecrire(ts, data)


def demarrer(sauver=None):
    global _sauver
    _sauver = sauver
    threading.Thread(target=_boucle, daemon=True).start()
    threading.Thread(target=_boucle_sequence, daemon=True).start()


def capturer(chemin: str) -> bool:
    """Photo d'alerte : copie de la dernière image (attend jusqu'à 3 s qu'elle existe)."""
    for _ in range(30):
        if image_recente():
            shutil.copyfile(LIVE, chemin)
            return True
        time.sleep(0.1)
    return False


def sha256_fichier(chemin: str) -> str:
    with open(chemin, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def image_live():
    return LIVE if image_recente(10) else None


async def flux_mjpeg():
    """Flux multipart/x-mixed-replace : le navigateur l'affiche comme une vidéo."""
    dernier = 0.0
    while True:
        try:
            m = os.path.getmtime(LIVE)
            if m != dernier:
                dernier = m
                with open(LIVE, "rb") as f:
                    img = f.read()
                yield (b"--frame\r\nContent-Type: image/jpeg\r\nContent-Length: "
                       + str(len(img)).encode() + b"\r\n\r\n" + img + b"\r\n")
        except FileNotFoundError:
            pass
        await asyncio.sleep(0.08)
