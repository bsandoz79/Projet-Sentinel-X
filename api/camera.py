"""
Webcam USB en capture CONTINUE (ffmpeg) :
- la webcam reste ouverte, la dernière image est réécrite ~10 fois / s dans _live.jpg
- /api/camera/stream envoie un flux vidéo MJPEG (fluide dans le navigateur)
- photo d'alerte = copie instantanée de la dernière image
"""
import asyncio
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
os.makedirs(PHOTOS_DIR, exist_ok=True)


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


def demarrer():
    threading.Thread(target=_boucle, daemon=True).start()


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
