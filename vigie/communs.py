"""Outils partagés par toutes les sources : en-têtes HTTP, lieux d'Île-de-France, dates, format d'une offre."""
import re
from datetime import datetime, timezone
from html import unescape as _decoder_entites


UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) VigieEmploi/1.0"}


NAVIGATEUR = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
}


TIMEOUT = 8


MOTS_IDF = [
    "île-de-france", "ile-de-france", "ile de france", "paris", "75", "77", "78",
    "91", "92", "93", "94", "95", "boulogne", "courbevoie", "la défense", "la defense",
    "nanterre", "issy", "levallois", "saint-denis", "montreuil", "créteil", "creteil",
    "versailles", "evry", "évry", "cergy", "melun", "clichy", "neuilly", "puteaux",
    "saclay", "massy", "roissy", "vélizy", "velizy", "rueil", "france",
]


def lieu_en_idf(lieu, strict=False):
    """Vérifie qu'un intitulé de lieu correspond à l'Île-de-France.
    strict=True exige Paris/IDF explicitement (pour les sources non filtrées en amont)."""
    if not lieu:
        return False
    l = lieu.lower()
    if strict:
        cibles = [m for m in MOTS_IDF if m != "france"]
        return any(m in l for m in cibles) or "remote" in l and "france" in l
    return any(m in l for m in MOTS_IDF)


def date_iso(valeur):
    """Normalise différentes dates en ISO ; renvoie None si inconnue."""
    if not valeur:
        return None
    try:
        if isinstance(valeur, (int, float)):  # timestamp ms (Lever)
            return datetime.fromtimestamp(valeur / 1000, tz=timezone.utc).isoformat()
        v = str(valeur).replace("Z", "+00:00")
        return datetime.fromisoformat(v).isoformat()
    except Exception:
        return None


def offre(id_, titre, entreprise, lieu, url, source, date=None, contrat="", description=""):
    return {
        "id": f"{source}:{id_}",
        "titre": (titre or "").strip(),
        "entreprise": (entreprise or "").strip() or "Entreprise non précisée",
        "lieu": (lieu or "Île-de-France").strip(),
        "url": url,
        "source": source,
        "date": date,
        "contrat": contrat or "",
        "description": (description or "")[:6000],
    }


def _nettoie_html(brut):
    """Retire les balises et décode les entités (« &amp; » → « & »)."""
    return re.sub(r"\s+", " ", _decoder_entites(re.sub(r"<[^>]+>", " ", brut or ""))).strip()
