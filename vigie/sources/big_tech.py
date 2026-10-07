"""Sites carrières propres aux Big Tech : Google et Apple."""
import requests
import json
import re

from ..communs import NAVIGATEUR, TIMEOUT, _nettoie_html, date_iso, offre


def source_google(url, nom="Google"):
    """Google Careers — la page de résultats est rendue côté serveur."""
    r = requests.get(url, headers=NAVIGATEUR, timeout=TIMEOUT)
    r.raise_for_status()
    html = r.text
    out, vus = [], set()
    for m in re.finditer(r'href="(?:\./|/about/careers/applications/)?jobs/results/(\d+)-([a-z0-9-]+)', html):
        ident, slug = m.group(1), m.group(2)
        if ident in vus:
            continue
        vus.add(ident)
        titre = slug.replace("-", " ").capitalize()
        # le vrai intitulé est dans l'attribut aria-label de la même balise <a>
        debut_balise = html.rfind("<a", 0, m.start())
        fin_balise = html.find(">", m.end())
        if debut_balise != -1 and fin_balise != -1:
            balise = html[debut_balise:fin_balise]
            t = re.search(r'aria-label="(?:Learn more about|En savoir plus sur)\s+([^"]+)"', balise)
            if t:
                titre = t.group(1).strip()
        out.append(offre(ident, titre, nom, "Paris, France",
                         f"https://www.google.com/about/careers/applications/jobs/results/{ident}-{slug}",
                         "Site carrière"))
    return out


def _apple_postes(obj, trouves):
    """Parcourt une structure JSON quelconque et récupère les postes (dictionnaires avec postingTitle)."""
    if isinstance(obj, dict):
        if obj.get("postingTitle") and (obj.get("positionId") or obj.get("id") or obj.get("reqId")):
            trouves.append(obj)
            return
        for v in obj.values():
            _apple_postes(v, trouves)
    elif isinstance(obj, list):
        for v in obj:
            _apple_postes(v, trouves)


def source_apple(url, nom="Apple"):
    """Apple Jobs — les résultats sont dans la page, sous une forme qui a changé avec la refonte
    du site : on essaie l'ancien window.APP_STATE, puis les données d'hydratation du nouveau site
    (React Router), puis, en dernier recours, les liens /details/ affichés dans la page."""
    r = requests.get(url, headers=NAVIGATEUR, timeout=TIMEOUT)
    r.raise_for_status()
    html = r.text
    postes = []
    blocs = re.findall(r"window\.APP_STATE\s*=\s*(\{.*?\})\s*;?\s*</script>", html, re.S)
    for brut in re.findall(r'JSON\.parse\(\s*("(?:[^"\\]|\\.)*")\s*\)', html, re.S):
        try:
            blocs.append(json.loads(brut))
        except Exception:
            pass
    blocs += re.findall(r"__staticRouterHydrationData\s*=\s*(\{.*?\})\s*;?\s*</script>", html, re.S)
    for bloc in blocs:
        if "postingTitle" not in bloc:
            continue
        try:
            _apple_postes(json.loads(bloc), postes)
        except Exception:
            pass
    out, vus = [], set()
    for j in postes:
        ident = str(j.get("positionId") or j.get("id") or j.get("reqId"))
        if ident in vus:
            continue
        vus.add(ident)
        slug = j.get("transformedPostingTitle") or ""
        lieux = ", ".join(filter(None, (l.get("name", "") for l in (j.get("locations") or []) if isinstance(l, dict)))) or "Paris"
        out.append(offre(ident, j["postingTitle"], nom, lieux,
                         f"https://jobs.apple.com/fr-fr/details/{ident}/{slug}".rstrip("/"), "Site carrière",
                         date_iso(j.get("postDateInGMT") or j.get("postingDate"))))
    if out:
        return out
    # dernier recours : les liens d'offres rendus dans la page
    for m in re.finditer(r'<a[^>]+href="(?:https://jobs\.apple\.com)?(/[a-z]{2}-[a-z]{2}/details/([0-9][0-9-]*)/[^"?#]*)[^"]*"[^>]*>(.*?)</a>',
                         html, re.S):
        chemin, ident, titre = m.group(1), m.group(2), _nettoie_html(m.group(3))
        if not titre or ident in vus or len(titre) < 4:
            continue
        vus.add(ident)
        out.append(offre(ident, titre, nom, "Paris", "https://jobs.apple.com" + chemin, "Site carrière"))
    if not out:
        raise RuntimeError(f"aucune offre lisible dans la page Apple ({len(html) // 1000} Ko reçus, "
                           f"{'données intégrées présentes' if 'postingTitle' in html else 'sans données intégrées'})")
    return out
