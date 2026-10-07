"""Sites d'emploi généralistes : France Travail et Adzuna (API à clé), Cadremploi."""
import requests
import json
import re
import time

from ..communs import NAVIGATEUR, TIMEOUT, UA, _nettoie_html, date_iso, lieu_en_idf, offre
from ..pertinence import intitule_pertinent


_ft_token = {"valeur": None, "expire": 0}


def token_france_travail(cles):
    if _ft_token["valeur"] and time.time() < _ft_token["expire"] - 60:
        return _ft_token["valeur"]
    r = requests.post(
        "https://entreprise.francetravail.fr/connexion/oauth2/access_token",
        params={"realm": "/partenaire"},
        data={
            "grant_type": "client_credentials",
            "client_id": cles["francetravail_id"],
            "client_secret": cles["francetravail_secret"],
            "scope": "api_offresdemploiv2 o2dsoffre",
        },
        headers=UA,
        timeout=TIMEOUT,
    )
    r.raise_for_status()
    d = r.json()
    _ft_token["valeur"] = d["access_token"]
    _ft_token["expire"] = time.time() + int(d.get("expires_in", 1400))
    return _ft_token["valeur"]


def source_france_travail(mots, cles):
    """API officielle France Travail (ex-Pôle emploi), filtrée région 11 = Île-de-France."""
    token = token_france_travail(cles)
    resultats = []
    for mot in mots:
        r = requests.get(
            "https://api.francetravail.io/partenaire/offresdemploi/v2/offres/search",
            params={"motsCles": mot, "region": "11", "sort": "1", "range": "0-49"},
            headers={**UA, "Authorization": f"Bearer {token}"},
            timeout=TIMEOUT,
        )
        if r.status_code == 204:
            continue
        r.raise_for_status()
        for o in r.json().get("resultats", []):
            url = (o.get("origineOffre") or {}).get("urlOrigine") or \
                  f"https://candidat.francetravail.fr/offres/recherche/detail/{o.get('id')}"
            candidate = offre(
                o.get("id"), o.get("intitule"),
                (o.get("entreprise") or {}).get("nom"),
                (o.get("lieuTravail") or {}).get("libelle"),
                url, "France Travail",
                date_iso(o.get("dateCreation")),
                (o.get("typeContrat") or ""),
                o.get("description", ""),
            )
            # France Travail élargit la recherche : on ne garde que les intitulés pertinents.
            if intitule_pertinent(candidate["titre"], mots):
                resultats.append(candidate)
    return resultats


def _adzuna_page(mot, cles, critere):
    r = requests.get(
        "https://api.adzuna.com/v1/api/jobs/fr/search/1",
        params={
            "app_id": cles["adzuna_id"], "app_key": cles["adzuna_key"],
            critere: mot, "where": "Ile-de-France", "distance": 40,
            "results_per_page": 50, "sort_by": "date",
        },
        headers=UA, timeout=TIMEOUT,
    )
    r.raise_for_status()
    return r.json().get("results", [])


def _adzuna_retenues(resultats, mots):
    retenues = []
    for o in resultats:
        lieu = (o.get("location") or {}).get("display_name", "")
        if not lieu_en_idf(lieu, strict=True):
            continue
        candidate = offre(
            o.get("id"), o.get("title"),
            (o.get("company") or {}).get("display_name"),
            lieu, o.get("redirect_url"), "Adzuna",
            date_iso(o.get("created")),
            o.get("contract_type") or o.get("contract_time") or "",
            o.get("description", ""),
        )
        if intitule_pertinent(candidate["titre"], mots):
            retenues.append(candidate)
    return retenues


def source_adzuna(mots, cles):
    """Adzuna agrège de nombreux sites d'emploi (Indeed, LinkedIn, sites carrières…).
    Sa recherche classique fouille aussi les descriptions et renvoie beaucoup d'offres
    hors sujet : on cherche d'abord dans les seuls intitulés (title_only), puis, si rien
    de pertinent ne revient, par la recherche classique. Dans les deux cas, seul
    l'intitulé décide (intitule_pertinent)."""
    resultats = []
    for mot in mots:
        retenues = _adzuna_retenues(_adzuna_page(mot, cles, "title_only"), mots)
        if not retenues:
            retenues = _adzuna_retenues(_adzuna_page(mot, cles, "what"), mots)
        resultats.extend(retenues)
    return resultats


def _parcourir_json_cadremploi(noeud, collecte):
    """Parcourt le JSON embarqué dans la page à la recherche d'objets « offre »."""
    if isinstance(noeud, dict):
        titre = noeud.get("intitule") or noeud.get("title") or noeud.get("jobTitle")
        ident = noeud.get("offreId") or noeud.get("idOffre") or noeud.get("id")
        if titre and ident and isinstance(titre, str):
            entreprise = noeud.get("nomEntreprise") or noeud.get("companyName") or ""
            if not entreprise and isinstance(noeud.get("entreprise"), dict):
                entreprise = noeud["entreprise"].get("nom", "")
            collecte.append({
                "id": str(ident), "titre": titre,
                "entreprise": entreprise,
                "lieu": noeud.get("localisation") or noeud.get("ville") or noeud.get("location") or "",
                "date": noeud.get("datePublication") or noeud.get("publicationDate"),
                "contrat": noeud.get("typeContrat") or noeud.get("contractType") or "",
                "url": noeud.get("urlOffre") or noeud.get("url") or "",
            })
        for v in noeud.values():
            _parcourir_json_cadremploi(v, collecte)
    elif isinstance(noeud, list):
        for v in noeud:
            _parcourir_json_cadremploi(v, collecte)


def source_cadremploi(mots):
    """Cadremploi — lecture des pages de résultats : JSON embarqué si présent,
    sinon repli sur les liens d'offres du HTML. Le site utilise une protection
    anti-robot : on passe par une session avec en-têtes de navigateur complets."""
    s = requests.Session()
    s.headers.update({
        **NAVIGATEUR,
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "same-origin",
        "Upgrade-Insecure-Requests": "1",
    })
    # premier passage sur l'accueil pour récupérer les cookies du site
    try:
        s.get("https://www.cadremploi.fr/", timeout=TIMEOUT)
    except Exception:
        pass
    out, vus = [], set()
    une_page_lue, brut_trouve, bloque = False, False, False
    for mot in mots[:6]:
        try:
            r = s.get("https://www.cadremploi.fr/emploi/liste_offres",
                      params={"motscles": mot, "localisation": "Île-de-France"},
                      timeout=TIMEOUT)
            if r.status_code in (403, 401, 429):
                bloque = True
                continue
            if r.status_code != 200:
                continue
        except Exception:
            continue
        une_page_lue = True
        html = r.text
        bruts = []
        m = re.search(r'<script[^>]*id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.S)
        if m:
            try:
                _parcourir_json_cadremploi(json.loads(m.group(1)), bruts)
            except Exception:
                pass
        if not bruts:
            for lm in re.finditer(
                r'href="((?:https://www\.cadremploi\.fr)?/emploi/detail_offre[^"]+)"[^>]*>(.*?)</a>',
                html, re.S,
            ):
                titre = _nettoie_html(lm.group(2))
                if len(titre) < 5:
                    continue
                url = lm.group(1)
                bruts.append({"id": url, "titre": titre, "entreprise": "", "lieu": "",
                              "date": None, "contrat": "", "url": url})
        for b in bruts:
            brut_trouve = True
            if b["id"] in vus:
                continue
            if b["lieu"] and not lieu_en_idf(b["lieu"], strict=True):
                continue
            url = b["url"] or f"https://www.cadremploi.fr/emploi/detail_offre?offreId={b['id']}"
            if url.startswith("/"):
                url = "https://www.cadremploi.fr" + url
            o = offre(b["id"], b["titre"], b["entreprise"],
                      b["lieu"] or "Île-de-France", url, "Cadremploi",
                      date_iso(b["date"]), b["contrat"])
            if intitule_pertinent(o["titre"], mots):
                vus.add(b["id"])
                out.append(o)
    if bloque and not une_page_lue:
        raise RuntimeError("accès refusé par la protection anti-robot du site (403) — utilisez le lien direct")
    if not une_page_lue:
        raise RuntimeError("site injoignable — utilisez le lien direct")
    if not out and not brut_trouve:
        raise RuntimeError("structure de page inattendue — utilisez le lien direct")
    return out
