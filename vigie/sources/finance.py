"""Sites carrières propres à la finance : Citadel, Goldman Sachs, Bank of America, Citi."""
import requests
import re
from concurrent.futures import ThreadPoolExecutor

from ..communs import NAVIGATEUR, TIMEOUT, _nettoie_html, lieu_en_idf, offre


VILLES_CITADEL = ("Chicago", "Greenwich", "Houston", "Miami", "New York", "Dublin", "Hamburg", "London",
                  "Paris", "Zurich", "Hong Kong", "Singapore", "Sydney", "Tokyo", "Toronto", "Gurugram",
                  "Shanghai", "Boston", "San Francisco", "Seattle", "Washington", "Chicago")


def _citadel_annonces(html):
    """Chaque annonce est un lien /careers/details/<nom>/ contenant l'intitulé, les villes et « Apply Now »."""
    annonces = []
    for m in re.finditer(r'<a[^>]+href="((?:https://www\.citadel\.com)?/careers/details/[^"]+)"[^>]*>(.*?)</a>',
                         html, re.S):
        url = m.group(1)
        if url.startswith("/"):
            url = "https://www.citadel.com" + url
        morceaux = [_nettoie_html(t) for t in re.split(r"<[^>]+>", m.group(2))]
        morceaux = [t for t in morceaux if t and t.lower() != "apply now"]
        if not morceaux:
            continue
        if len(morceaux) > 1:
            titre, villes = morceaux[0], " ".join(morceaux[1:])
        else:
            # tout le texte d'un bloc : on détache la liste de villes en fin d'intitulé
            texte = re.sub(r"\s*Apply Now\s*$", "", morceaux[0])
            motif = "|".join(re.escape(v) for v in VILLES_CITADEL)
            v = re.search(rf"\s((?:(?:{motif})(?:,\s*)?)+)$", texte)
            titre, villes = (texte[:v.start()].strip(), v.group(1)) if v else (texte, "")
        annonces.append((url, titre, villes))
    return annonces


def source_citadel(nom="Citadel"):
    """Citadel — la liste « Open Opportunities » est rendue dans la page, 10 annonces par page :
    on lit toutes les pages en parallèle et on garde celles situées à Paris."""
    base = "https://www.citadel.com/careers/open-opportunities/"
    r = requests.get(base, headers=NAVIGATEUR, timeout=TIMEOUT)
    r.raise_for_status()
    pages = [r.text]
    derniere = max([int(n) for n in re.findall(r"/careers/open-opportunities/page/(\d+)/", r.text)] or [1])
    if derniere > 1:
        def lire(n):
            rp = requests.get(f"{base}page/{n}/", headers=NAVIGATEUR, timeout=TIMEOUT)
            rp.raise_for_status()
            return rp.text
        with ThreadPoolExecutor(max_workers=6) as pool:
            for texte in pool.map(lire, range(2, min(derniere, 15) + 1)):
                pages.append(texte)
    out, vus, total = [], set(), 0
    for html in pages:
        for url, titre, villes in _citadel_annonces(html):
            total += 1
            ident = url.rstrip("/").rsplit("/", 1)[-1]
            if ident in vus or "paris" not in villes.lower():
                continue
            vus.add(ident)
            out.append(offre(ident, titre, nom, "Paris", url, "Site carrière"))
    if not total:
        raise RuntimeError("aucune annonce dans la page Citadel (structure modifiée) — utilisez le lien direct")
    return out


GS_API = "https://api-higher.gs.com/gateway/api/v1/graphql"


GS_REQUETE = """query GetRoles($searchQueryInput: RoleSearchQueryInput!) {
  roleSearch(searchQueryInput: $searchQueryInput) {
    totalCount
    items { roleId jobTitle division locations { primary state country city } }
  }
}"""


GS_EXPERIENCES = ["PROFESSIONAL", "EARLY_CAREER", "CAMPUS"]


def _gs_page(numero, filtres, experiences, taille=100):
    corps = {
        "operationName": "GetRoles",
        "query": GS_REQUETE,
        "variables": {"searchQueryInput": {
            "page": {"pageSize": taille, "pageNumber": numero},
            "sort": {"sortStrategy": "RELEVANCE", "sortOrder": "DESC"},
            "filters": filtres, "experiences": experiences, "searchTerm": "",
        }},
    }
    r = requests.post(GS_API, json=corps, timeout=TIMEOUT, headers={
        **NAVIGATEUR, "Content-Type": "application/json", "Accept": "application/json",
        "Origin": "https://higher.gs.com", "Referer": "https://higher.gs.com/"})
    r.raise_for_status()
    d = r.json()
    if d.get("errors"):
        raise RuntimeError("API Goldman Sachs : " + str(d["errors"][0].get("message", ""))[:150])
    return d["data"]["roleSearch"]


def _gs_tout(filtres, experiences, max_pages=12):
    premiere = _gs_page(0, filtres, experiences)
    items = list(premiere.get("items") or [])
    pages = min(max_pages, -(-int(premiere.get("totalCount") or 0) // 100))
    if pages > 1:
        with ThreadPoolExecutor(max_workers=6) as pool:
            for res in pool.map(lambda n: _gs_page(n, filtres, experiences), range(1, pages)):
                items.extend(res.get("items") or [])
    return int(premiere.get("totalCount") or 0), items


def source_gs(nom="Goldman Sachs"):
    """Goldman Sachs — API GraphQL publique (sans compte) que la page higher.gs.com appelle
    elle-même. On demande les postes en France ; si ce filtre ne renvoie rien (libellé de
    pays différent), on lit toute la liste et on filtre l'Île-de-France ici."""
    france = [{"filterCategoryType": "LOCATION", "filters": [{"filter": "France", "subFilters": []}]}]
    try:
        total, items = _gs_tout(france, GS_EXPERIENCES)
        if not total:
            total, items = _gs_tout([], GS_EXPERIENCES)
    except RuntimeError as e:
        # une catégorie d'expérience refusée par l'API : on interroge chacune séparément
        items, erreurs = [], []
        for exp in GS_EXPERIENCES:
            try:
                items += _gs_tout(france, [exp])[1]
            except Exception as e2:  # noqa: BLE001
                erreurs.append(e2)
        if len(erreurs) == len(GS_EXPERIENCES):
            raise e
    out, vus = [], set()
    for it in items:
        lieux = it.get("locations") or []
        lieu = next((l for l in lieux if lieu_en_idf(f"{l.get('city') or ''} {l.get('state') or ''}", strict=True)), None)
        titre, ident = it.get("jobTitle"), str(it.get("roleId") or "")
        if not (lieu and titre and ident) or ident in vus:
            continue
        vus.add(ident)
        numero = ident.split("_")[0]
        out.append(offre(numero, titre, nom, lieu.get("city") or "Paris",
                         f"https://higher.gs.com/roles/{numero}", "Site carrière"))
    return out


def source_bofa(nom="Bank of America"):
    """Bank of America — page de recherche rendue côté serveur."""
    r = requests.get("https://careers.bankofamerica.com/en-us/job-search/france",
                     params={"ref": "search", "start": 0, "rows": 50,
                             "search": "jobsByLocation", "searchstring": "Paris, France"},
                     headers=NAVIGATEUR, timeout=TIMEOUT)
    r.raise_for_status()
    out, vus = [], set()
    for m in re.finditer(
        r'href="((?:https://careers\.bankofamerica\.com)?/en-us/job-detail/[^"]+)"[^>]*>(.*?)</a>',
        r.text, re.S,
    ):
        url = m.group(1)
        if url.startswith("/"):
            url = "https://careers.bankofamerica.com" + url
        titre = _nettoie_html(m.group(2))
        ident = url.rstrip("/").split("/job-detail/")[-1].split("/")[0]
        if not titre or len(titre) < 4 or ident in vus:
            continue
        vus.add(ident)
        out.append(offre(ident, titre, nom, "Paris", url, "Site carrière"))
    if not out:
        raise RuntimeError("aucune offre lisible — utilisez le lien direct")
    return out


def source_citi(url, nom="Citi"):
    """Citi (plateforme Radancy) — liste rendue côté serveur."""
    r = requests.get(url, headers=NAVIGATEUR, timeout=TIMEOUT)
    r.raise_for_status()
    out, vus = [], set()
    for m in re.finditer(
        r'href="((?:https://jobs\.citi\.com)?/job/[^"]+)"[^>]*>(.*?)</a>', r.text, re.S,
    ):
        url_o = m.group(1)
        if url_o.startswith("/"):
            url_o = "https://jobs.citi.com" + url_o
        if "/job/paris" not in url_o.lower():
            continue
        titre = _nettoie_html(m.group(2))
        ident = url_o.rstrip("/").rsplit("/", 1)[-1]
        if not titre or ident in vus:
            continue
        vus.add(ident)
        out.append(offre(ident, titre, nom, "Paris", url_o, "Site carrière"))
    return out
