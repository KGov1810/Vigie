"""Welcome to the Jungle (index de recherche Algolia public)."""
import requests
import json
import re

from ..communs import NAVIGATEUR, TIMEOUT, date_iso, lieu_en_idf, offre
from ..pertinence import offre_pertinente


WTTJ_APP_ID = "CSEKHVMS53"


WTTJ_CLE = "4bd8f6215d0cc52b26430765769e65a0"


WTTJ_INDEX = "wttj_jobs_production_fr_published_at_desc"


WTTJ_ENDPOINT = ("https://csekhvms53-dsn.algolia.net/1/indexes/*/queries"
                 "?x-algolia-agent=Algolia%20for%20JavaScript%20(4.20.0)%3B%20Browser"
                 "&search_origin=job_search_client")


def _cles_algolia_wttj():
    """Secours si les identifiants publics changent : on tente de relire
    ceux embarqués dans le site (peut être bloqué par leur anti-robot)."""
    r = requests.get("https://www.welcometothejungle.com/fr/jobs",
                     headers=NAVIGATEUR, timeout=TIMEOUT)
    r.raise_for_status()
    app_id = cle = index = None
    m = re.search(r'(?:applicationId|appId)["\']?\s*[:=]\s*["\']([A-Z0-9]{10})["\']', r.text)
    if m:
        app_id = m.group(1)
    m = re.search(r'(?:apiKey|searchApiKey)["\']?\s*[:=]\s*["\']([a-f0-9]{32,64})["\']', r.text)
    if m:
        cle = m.group(1)
    m = re.search(r'["\'](wttj_jobs[a-z_]*fr[a-z_]*)["\']', r.text)
    if m:
        index = m.group(1)
    if not (app_id and cle):
        raise RuntimeError("identifiants introuvables")
    return app_id, cle, index or WTTJ_INDEX


def _requete_wttj(app_id, cle, index, mot):
    entetes = {
        "User-Agent": NAVIGATEUR["User-Agent"],
        "Accept": "*/*",
        "Accept-Language": "fr,fr-FR;q=0.8,en;q=0.5",
        "Referer": "https://www.welcometothejungle.com/",
        "Origin": "https://www.welcometothejungle.com",
        "content-type": "application/x-www-form-urlencoded",
        "x-algolia-application-id": app_id,
        "x-algolia-api-key": cle,
    }
    # géolocalisé sur Paris avec un rayon couvrant l'Île-de-France
    params = (f"query={requests.utils.quote(mot)}&hitsPerPage=50"
              f"&aroundLatLng=48.8546%2C2.34771&aroundRadius=60000"
              f"&attributesToRetrieve=%5B%22*%22%5D")
    endpoint = (f"https://{app_id.lower()}-dsn.algolia.net/1/indexes/*/queries"
                "?x-algolia-agent=Algolia%20for%20JavaScript%20(4.20.0)%3B%20Browser"
                "&search_origin=job_search_client")
    r = requests.post(endpoint,
                      data=json.dumps({"requests": [{"indexName": index, "params": params}]}),
                      headers=entetes, timeout=TIMEOUT)
    r.raise_for_status()
    return (r.json().get("results") or [{}])[0].get("hits") or []


def source_wttj(mots):
    """Welcome to the Jungle — moteur de recherche Algolia public du site,
    une requête géolocalisée Paris par mot-clé, puis filtres IDF + pertinence."""
    jeux = [(WTTJ_APP_ID, WTTJ_CLE, WTTJ_INDEX)]
    out, vus = [], set()
    derniere_erreur, une_reussite = None, False
    for mot in mots[:6]:
        hits = []
        for app_id, cle, index in jeux:
            try:
                hits = _requete_wttj(app_id, cle, index, mot)
                une_reussite = True
                break
            except Exception as e:
                derniere_erreur = e
                # les identifiants publics ont peut-être changé : on relit le site
                if len(jeux) == 1:
                    try:
                        jeux.append(_cles_algolia_wttj())
                    except Exception:
                        pass
        for h in hits:
            ident = h.get("objectID") or h.get("slug")
            if not ident or ident in vus:
                continue
            titre = h.get("name") or h.get("title")
            if not titre:
                continue
            orga = h.get("organization") or {}
            villes = []
            for b in (h.get("offices") or []):
                if isinstance(b, dict):
                    villes.append(b.get("city", ""))
            for c in ("city", "office_city"):
                if h.get(c):
                    villes.append(str(h[c]))
            ville = next((v for v in villes if lieu_en_idf(v, strict=True)), None)
            if not ville:
                continue
            slug_o, slug_e = h.get("slug"), orga.get("slug")
            url = (f"https://www.welcometothejungle.com/fr/companies/{slug_e}/jobs/{slug_o}"
                   if slug_o and slug_e else "https://www.welcometothejungle.com/fr/jobs")
            description = " ".join(str(h.get(c, "")) for c in
                                   ("profile", "missions", "candidate_profile", "summary"))
            o = offre(ident, titre, orga.get("name", ""), ville, url,
                      "Welcome to the Jungle", date_iso(h.get("published_at")),
                      str(h.get("contract_type") or ""), description)
            if offre_pertinente(o, mots):
                vus.add(ident)
                out.append(o)
    if not une_reussite:
        raise RuntimeError(f"moteur inaccessible ({derniere_erreur})")
    return out
