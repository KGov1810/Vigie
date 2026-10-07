"""Vérification du compte Firebase qui appelle le relais."""
import requests
import os
import time

from .config import firebase_config


_jetons_valides = {}


class CompteRefuse(PermissionError):
    """Compte Firebase valide, mais absent de EMAILS_AUTORISES."""


def emails_autorises():
    return {e.strip().lower() for e in os.environ.get("EMAILS_AUTORISES", "").split(",") if e.strip()}


def verifier_jeton(entete):
    if not entete or not entete.startswith("Bearer "):
        raise PermissionError("connexion requise")
    jeton = entete[7:].strip()
    maintenant = time.time()
    if _jetons_valides.get(jeton, 0) > maintenant:
        return
    cle = firebase_config().get("apiKey")
    if not cle:
        raise RuntimeError("FIREBASE_CONFIG absente du relais")
    r = requests.post(f"https://identitytoolkit.googleapis.com/v1/accounts:lookup?key={cle}",
                      json={"idToken": jeton}, timeout=8)
    comptes = r.json().get("users") if r.status_code == 200 else None
    if not comptes:
        raise PermissionError("session expirée, reconnectez-vous")
    # La clé web Firebase est publique : n'importe qui pourrait se créer un compte dans le projet.
    # EMAILS_AUTORISES réserve alors le relais (et vos clés France Travail / Adzuna) à vos comptes.
    autorises = emails_autorises()
    if autorises and (comptes[0].get("email") or "").strip().lower() not in autorises:
        raise CompteRefuse("ce compte n'est pas autorisé sur ce relais (voir EMAILS_AUTORISES)")
    if len(_jetons_valides) > 500:
        _jetons_valides.clear()
    _jetons_valides[jeton] = maintenant + 45 * 60
