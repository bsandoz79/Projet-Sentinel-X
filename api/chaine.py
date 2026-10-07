"""Journal chaîné : même calcul de hash que capteurs/sentinel_pi.py."""
import hashlib
import json

GENESE = "0" * 64


def calculer_hash(evt: dict) -> str:
    """sha256 du JSON trié de l'événement, sans les champs 'hash' et 'id'."""
    contenu = {k: v for k, v in evt.items() if k not in ("hash", "id")}
    return hashlib.sha256(json.dumps(contenu, sort_keys=True).encode()).hexdigest()


def verifier_chaine(evenements: list[dict]) -> dict:
    """Recalcule toute la chaîne. Renvoie l'index du premier maillon cassé."""
    prev = GENESE
    for i, e in enumerate(evenements):
        if e["prev"] != prev or calculer_hash(e) != e["hash"]:
            return {"ok": False, "total": len(evenements), "premier_invalide": i}
        prev = e["hash"]
    return {"ok": True, "total": len(evenements), "premier_invalide": None}
