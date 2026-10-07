"""Webcam USB : photo à chaque alerte + image en direct (fswebcam)."""
import hashlib
import os
import subprocess
import threading
import time

CAMERA = os.getenv("CAMERA", "/dev/video0")
PHOTOS_DIR = os.getenv("PHOTOS_DIR", "photos")
LIVE = os.path.join(PHOTOS_DIR, "_live.jpg")
os.makedirs(PHOTOS_DIR, exist_ok=True)
_verrou = threading.Lock()          # une seule capture à la fois


def disponible() -> bool:
    return os.path.exists(CAMERA)


def capturer(chemin: str, resolution: str = "1280x720") -> bool:
    if not disponible():
        return False
    tmp = chemin + ".tmp.jpg"
    with _verrou:
        try:
            r = subprocess.run(["fswebcam", "-q", "-d", CAMERA, "-r", resolution, "--no-banner",
                                "-S", "8", "--jpeg", "85", tmp], capture_output=True, timeout=20)
        except Exception as ex:
            print("Caméra : erreur", ex)
            return False
    if r.returncode == 0 and os.path.exists(tmp) and os.path.getsize(tmp) > 0:
        os.replace(tmp, chemin)
        return True
    print("Caméra : capture impossible", r.stderr.decode(errors="ignore")[:200])
    return False


def sha256_fichier(chemin: str) -> str:
    with open(chemin, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def image_live(max_age: float = 2.0):
    """Renvoie le chemin d'une image de moins de max_age secondes (ou None)."""
    if os.path.exists(LIVE) and time.time() - os.path.getmtime(LIVE) < max_age:
        return LIVE
    return LIVE if capturer(LIVE, "640x360") else (LIVE if os.path.exists(LIVE) else None)
