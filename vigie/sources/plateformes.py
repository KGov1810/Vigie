"""Plateformes de recrutement utilisées par plusieurs entreprises : Greenhouse, Lever, Ashby, Eightfold, Oracle, SuccessFactors."""
import requests
import re
from datetime import datetime, timezone

from ..communs import NAVIGATEUR, TIMEOUT, UA, _nettoie_html, date_iso, lieu_en_idf, offre


def source_greenhouse(slug, nom=None):
    r = requests.get(f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs",
                     headers=UA, timeout=TIMEOUT)
    r.raise_for_status()
    out = []
    for j in r.json().get("jobs", []):
        lieu = ((j.get("location") or {}).get("name")) or ""
        if not lieu_en_idf(lieu):
            continue
        out.append(offre(j.get("id"), j.get("title"), nom or slug.capitalize(), lieu,
                         j.get("absolute_url"), "Site carrière",
                         date_iso(j.get("updated_at"))))
    return out


def source_lever(slug, nom=None):
    r = requests.get(f"https://api.lever.co/v0/postings/{slug}", params={"mode": "json"},
                     headers=UA, timeout=TIMEOUT)
    r.raise_for_status()
    out = []
    for j in r.json():
        lieu = ((j.get("categories") or {}).get("location")) or ""
        if not lieu_en_idf(lieu):
            continue
        out.append(offre(j.get("id"), j.get("text"), nom or slug.capitalize(), lieu,
                         j.get("hostedUrl"), "Site carrière", date_iso(j.get("createdAt"))))
    return out


def source_ashby(slug, nom=None):
    r = requests.get(f"https://api.ashbyhq.com/posting-api/job-board/{slug}",
                     headers=UA, timeout=TIMEOUT)
    r.raise_for_status()
    out = []
    for j in r.json().get("jobs", []):
        lieux = [j.get("location") or ""] + [s.get("location", "") for s in j.get("secondaryLocations") or []]
        lieu = next((l for l in lieux if lieu_en_idf(l)), None)
        if not lieu:
            continue
        out.append(offre(j.get("id"), j.get("title"), nom or slug.capitalize(), lieu,
                         j.get("jobUrl") or j.get("applyUrl"), "Site carrière",
                         date_iso(j.get("publishedAt"))))
    return out


def source_eightfold(hote, domaine, nom):
    """Plateforme Eightfold AI (Microsoft, Millennium…) — API JSON publique."""
    r = requests.get(f"{hote}/api/apply/v2/jobs",
                     params={"domain": domaine, "start": 0, "num": 50,
                             "location": "Paris, France", "sort_by": "timestamp"},
                     headers={**NAVIGATEUR, "Accept": "application/json"}, timeout=TIMEOUT)
    r.raise_for_status()
    out = []
    for p in r.json().get("positions", []):
        lieux = [p.get("location") or ""] + [str(l) for l in (p.get("locations") or [])]
        lieu = next((l for l in lieux if lieu_en_idf(l, strict=True)), None)
        if not lieu:
            continue
        ts = p.get("t_update") or p.get("t_create")
        date = None
        if ts:
            try:
                date = datetime.fromtimestamp(float(ts), tz=timezone.utc).isoformat()
            except Exception:
                pass
        url = p.get("canonicalPositionUrl") or f"{hote}/careers?pid={p.get('id')}&domain={domaine}"
        out.append(offre(p.get("id"), p.get("name"), nom, lieu, url, "Site carrière", date))
    return out


def source_oracle(hote, site, lieu_id, nom):
    """Oracle Cloud HCM (JPMorgan…) — API REST publique des offres."""
    finder = f"findReqs;siteNumber={site},limit=50,sortBy=POSTING_DATES_DESC,locationId={lieu_id}"
    r = requests.get(f"{hote}/hcmRestApi/resources/latest/recruitingCEJobRequisitions",
                     params={"onlyData": "true", "finder": finder},
                     headers={**NAVIGATEUR, "Accept": "application/json"}, timeout=TIMEOUT)
    r.raise_for_status()
    out = []
    for bloc in r.json().get("items", []):
        for j in bloc.get("requisitionList", []):
            lieu = j.get("PrimaryLocation") or ""
            if not lieu_en_idf(lieu, strict=True):
                continue
            out.append(offre(
                j.get("Id"), j.get("Title"), nom, lieu,
                f"{hote}/hcmUI/CandidateExperience/en/sites/{site}/job/{j.get('Id')}",
                "Site carrière", date_iso(j.get("PostedDate"))))
    return out


def source_successfactors(hote, nom):
    """SAP SuccessFactors (CFM…) — page de résultats rendue côté serveur."""
    r = requests.get(f"{hote}/search/", params={"q": "", "locationsearch": "Paris"},
                     headers=NAVIGATEUR, timeout=TIMEOUT)
    r.raise_for_status()
    out, vus = [], set()
    for m in re.finditer(r'<a[^>]+href="(/job/[^"]+)"[^>]*>(.*?)</a>', r.text, re.S):
        chemin, titre = m.group(1), _nettoie_html(m.group(2))
        ident = chemin.rstrip("/").rsplit("/", 1)[-1]
        if not titre or ident in vus:
            continue
        vus.add(ident)
        out.append(offre(ident, titre, nom, "Paris", hote + chemin, "Site carrière"))
    return out
