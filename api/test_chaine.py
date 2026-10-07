"""Tests de la chaîne de hash (lancés par la CI GitHub)."""
import copy
from chaine import GENESE, calculer_hash, verifier_chaine


def fabriquer(n=5):
    evts, prev = [], GENESE
    for i in range(n):
        e = {"ts": f"2026-10-08T10:00:0{i}Z", "type": "alerte" if i % 2 else "ok",
             "details": {"gaz": 300 + i, "alertes": ["gaz"] if i % 2 else []}, "prev": prev}
        e["hash"] = calculer_hash(e)
        e["id"] = i + 1
        prev = e["hash"]
        evts.append(e)
    return evts


def test_chaine_intacte():
    assert verifier_chaine(fabriquer())["ok"] is True


def test_modification_detectee():
    evts = fabriquer()
    evts[2]["details"]["gaz"] = 999          # on falsifie le 3e événement
    r = verifier_chaine(evts)
    assert r["ok"] is False and r["premier_invalide"] == 2


def test_suppression_detectee():
    evts = fabriquer()
    del evts[1]                               # on efface un événement
    r = verifier_chaine(evts)
    assert r["ok"] is False and r["premier_invalide"] == 1


def test_recalcul_du_hash_detecte():
    evts = fabriquer()
    evts[2]["details"]["gaz"] = 999
    evts[2]["hash"] = calculer_hash(evts[2])  # le fraudeur recalcule le hash...
    r = verifier_chaine(evts)
    assert r["ok"] is False and r["premier_invalide"] == 3   # ...mais le suivant ne colle plus


def test_meme_hash_que_le_script_pi():
    import hashlib, json
    e = {"ts": "2026-10-08T10:00:00Z", "type": "ok", "details": {"a": 1}, "prev": GENESE}
    attendu = hashlib.sha256(json.dumps(e, sort_keys=True).encode()).hexdigest()
    assert calculer_hash(copy.deepcopy(e)) == attendu
