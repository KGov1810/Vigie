"""Lecture d'un site du catalogue pour le téléphone : aiguillage, mots-clés en parallèle, tri, dédoublonnage."""
from concurrent.futures import ThreadPoolExecutor

from .catalogue import CATALOGUE, PAR_MOT_CLE
from .config import cle_disponible
from .pertinence import poste_tech_pertinent
from .sources.aiguillage import lire_site


def lire_source(id_source, mots):
    """Renvoie {"etat": "ok"|"erreur"|"cle_manquante", "offres": [...], "detail": "..."}."""
    conf = CATALOGUE.get(id_source)
    if not conf:
        return {"etat": "erreur", "offres": [], "detail": "site inconnu"}
    if conf.get("lien_seul"):
        return {"etat": "erreur", "offres": [], "detail": "site consultable uniquement par son lien direct"}
    if conf.get("cle") and not cle_disponible(conf["cle"]):
        return {"etat": "cle_manquante", "offres": [], "detail": "clé à ajouter dans Vercel (voir le guide)"}
    if conf.get("mots") and not mots:
        return {"etat": "ok", "offres": [], "detail": "aucun mot-clé"}

    if conf["type"] in PAR_MOT_CLE and len(mots) > 1:
        # une requête par mot-clé, en parallèle : plus rapide, et un mot en échec ne bloque pas les autres
        offres, erreurs = [], []
        with ThreadPoolExecutor(max_workers=min(6, len(mots))) as pool:
            for fut in [pool.submit(lire_site, conf, [m]) for m in mots]:
                try:
                    offres.extend(fut.result())
                except Exception as e:  # noqa: BLE001
                    erreurs.append(e)
        if erreurs and len(erreurs) == len(mots):
            raise erreurs[0]
    else:
        offres = lire_site(conf, mots)

    if conf["groupe"] in ("big_tech", "finance"):
        offres = [o for o in offres if poste_tech_pertinent(o["titre"], conf["groupe"], mots)]

    vus, uniques = set(), []
    for o in offres:
        if o["id"] in vus or not o.get("url"):
            continue
        vus.add(o["id"])
        o.pop("description", None)  # inutile au téléphone : on allège la réponse
        uniques.append(o)
    return {"etat": "ok", "offres": uniques}


def _mots_propres(valeur):
    if not isinstance(valeur, list):
        return []
    mots = []
    for m in valeur:
        if isinstance(m, str) and m.strip() and m.strip() not in mots:
            mots.append(m.strip()[:80])
    return mots[:12]
