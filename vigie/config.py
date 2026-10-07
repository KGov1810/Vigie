"""Configuration lue dans les variables d'environnement Vercel."""
import json
import os
import re


def cles_api():
    return {
        "francetravail_id": os.environ.get("FRANCE_TRAVAIL_ID", "").strip(),
        "francetravail_secret": os.environ.get("FRANCE_TRAVAIL_SECRET", "").strip(),
        "adzuna_id": os.environ.get("ADZUNA_ID", "").strip(),
        "adzuna_key": os.environ.get("ADZUNA_KEY", "").strip(),
    }


def cle_disponible(nom):
    c = cles_api()
    if nom == "france_travail":
        return bool(c["francetravail_id"] and c["francetravail_secret"])
    if nom == "adzuna":
        return bool(c["adzuna_id"] and c["adzuna_key"])
    return True


def firebase_config():
    """Accepte la configuration telle que la console Firebase l'affiche
    (« const firebaseConfig = { apiKey: "…", … }; ») ou en JSON."""
    brut = os.environ.get("FIREBASE_CONFIG", "").strip()
    if not brut:
        return {}
    try:
        d = json.loads(brut)
    except Exception:
        d = dict(re.findall(r"""["']?(\w+)["']?\s*:\s*["']([^"']*)["']""", brut))
    champs = ("apiKey", "authDomain", "projectId", "storageBucket", "messagingSenderId", "appId")
    return {k: d[k] for k in champs if d.get(k)}
