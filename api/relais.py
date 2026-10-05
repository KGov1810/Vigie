# -*- coding: utf-8 -*-
"""
Vigie mobile — relais de lecture des offres d'emploi (fonction serverless Vercel).

Le téléphone ne peut pas lire directement les sites carrières (Safari l'interdit),
ce relais le fait à sa place, en temps réel, à chaque actualisation :
  GET  /api/relais            -> configuration publique (Firebase + catalogue des sites)
  POST /api/relais            -> {"source": "<id>", "mots": [...]} : lit UN site, renvoie ses offres

Sécurité :
  - seuls les sites du CATALOGUE ci-dessous peuvent être lus (jamais une adresse arbitraire) ;
  - chaque appel doit porter le jeton d'un compte Firebase de VOTRE projet.

Variables d'environnement (Vercel > Settings > Environment Variables) :
  FIREBASE_CONFIG        obligatoire : la configuration web Firebase (copier-coller tel quel)
  EMAILS_AUTORISES       conseillé   : e-mails autorisés à utiliser le relais, séparés par des virgules
  FRANCE_TRAVAIL_ID      facultatif  : identifiant client francetravail.io
  FRANCE_TRAVAIL_SECRET  facultatif  : clé secrète francetravail.io
  ADZUNA_ID              facultatif  : App ID developer.adzuna.com
  ADZUNA_KEY             facultatif  : App Key developer.adzuna.com

Les fonctions de lecture des sites sont reprises telles quelles de Vigie (version ordinateur).
"""
import json
import os
import re
import time
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from html import unescape as _decoder_entites
from http.server import BaseHTTPRequestHandler

import requests

# ==========================================================================
# Lecture des sites (reprise de Vigie)
# ==========================================================================
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


MOTS_VIDES = {
    "de", "du", "des", "la", "le", "les", "l", "d", "et", "en", "a", "au", "aux",
    "pour", "avec", "sur", "un", "une", "ou", "h", "f", "hf",
}


def normaliser_texte(texte):
    """minuscules, sans accents, sans ponctuation — pour comparer sans surprise."""
    t = unicodedata.normalize("NFD", (texte or "").lower())
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9+#]+", " ", t).strip()


def termes_significatifs(phrase):
    return [m for m in normaliser_texte(phrase).split() if m not in MOTS_VIDES and len(m) > 1]


def offre_pertinente(o, mots_cles, seuil=1.0):
    """True si l'offre correspond à au moins un mot-clé.
    seuil=1.0 : tous les termes du mot-clé doivent être présents (strict).
    seuil=0.6 : 60 % suffisent (souple, pour les sites déjà spécialisés)."""
    texte = normaliser_texte(f"{o['titre']} {o.get('description', '')}")
    mots_texte = set(texte.split())

    def present(terme):
        if terme in mots_texte:
            return True
        # tolérance de préfixe dans les deux sens :
        # « quant » doit retrouver « quantitatif », « quantitatif » → « quantitative »
        if len(terme) >= 5 and any(m.startswith(terme) for m in mots_texte):
            return True
        if len(terme) >= 7:
            prefixe = terme[:7]
            return any(m.startswith(prefixe) for m in mots_texte)
        return False

    for phrase in mots_cles:
        termes = termes_significatifs(phrase)
        if not termes:
            continue
        trouves = sum(1 for t in termes if present(t))
        if trouves >= max(1, round(len(termes) * seuil)):
            return True
    return False


# --------------------------------------------------------------------------
# Pertinence des offres Droit & RH : on juge l'INTITULÉ du poste.
# Les descriptions des sites généralistes citent trop de mots au hasard
# (« prise en charge », « gestion », « direction des ressources humaines »,
# « siège social »…) : les chercher en vrac laissait passer un dentiste
# pour « gestionnaire RH ».
# --------------------------------------------------------------------------
# Mots qui précisent sans être indispensables : « Juriste social » vaut « juriste droit social ».
MOTS_SOUPLES = {"droit", "senior", "junior", "confirme", "confirmee", "experimente", "experimentee"}
# Écritures équivalentes, ramenées à une seule forme avant comparaison.
EQUIVALENCES = [
    (re.compile(r"\bressources? humaines?\b"), "rh"),
    (re.compile(r"\bhuman resources?\b"), "rh"),
    (re.compile(r"\bhr\b"), "rh"),
]
# Mots de métier : sur un site juridique, seule la spécialité départage les annonces.
METIERS = {
    "juriste", "avocat", "avocate", "charge", "chargee", "gestionnaire", "assistant", "assistante",
    "responsable", "stagiaire", "stage", "alternant", "alternante", "alternance", "apprenti", "apprentie",
    "consultant", "consultante", "directeur", "directrice", "conseiller", "conseillere", "collaborateur",
    "collaboratrice", "paralegal", "clerc", "notaire", "manager", "specialiste", "expert", "experte",
    "analyste", "legal", "counsel", "officer",
}


MOTS_VIDES_EN = {"and", "of", "the", "for", "to", "in", "with", "at", "on"}


def _jetons(texte):
    t = normaliser_texte(texte)
    for motif, forme in EQUIVALENCES:
        t = motif.sub(forme, t)
    return [m for m in t.split() if m not in MOTS_VIDES and m not in MOTS_VIDES_EN and len(m) > 1]


def _expression_presente(expression, jetons):
    n = len(expression)
    return any(all(_meme_mot(expression[k], jetons[i + k]) for k in range(n))
               for i in range(len(jetons) - n + 1))


def _meme_mot(terme, mot):
    """« penal » retrouve « penaliste », « societes » retrouve « societe » ; « rh » reste exact."""
    return mot == terme or (len(terme) >= 5 and mot.startswith(terme)) or \
        (len(terme) >= 7 and mot.startswith(terme[:7]))


def _present(terme, mots):
    return any(_meme_mot(terme, m) for m in mots)


def _essentiels(termes):
    return [t for t in termes if t not in MOTS_SOUPLES] or termes


def intitule_pertinent(titre, mots_cles):
    """Sites généralistes : l'intitulé doit contenir tous les termes essentiels
    d'au moins un mot-clé, c'est-à-dire le métier ET la spécialité."""
    mots_titre = set(_jetons(titre))
    for phrase in mots_cles:
        essentiels = _essentiels(_jetons(phrase))
        if essentiels and all(_present(t, mots_titre) for t in essentiels):
            return True
    return False


def annonce_juridique_pertinente(titre, description, mots_cles):
    """Sites juridiques : toutes les annonces sont déjà des postes juridiques, on exige la
    spécialité du mot-clé (« travail », « penal », « rh »…) dans l'intitulé, ou sous forme
    d'expression suivie dans la description (« droit du travail », jamais des mots épars)."""
    mots_titre = set(_jetons(titre))
    desc = _jetons(description)
    for phrase in mots_cles:
        termes = _jetons(phrase)
        if not termes:
            continue
        essentiels = _essentiels(termes)
        specialite = [t for t in essentiels if t not in METIERS] or essentiels
        if all(_present(t, mots_titre) for t in specialite):
            return True
        expression = termes
        while expression and expression[0] in METIERS:
            expression = expression[1:]
        if len(expression) >= 2 and _expression_presente(expression, desc):
            return True
    return False


# --------------------------------------------------------------------------
# Pertinence des offres des sites carrières (profil Finance & Tech).
# Ces sites renvoient TOUS leurs postes à Paris : RH, growth, commercial…
# On garde les postes techniques et quantitatifs, et tout intitulé qui
# contient l'un des mots-clés du secteur (vos mots-clés priment toujours).
# --------------------------------------------------------------------------
def _expressions(*textes):
    return [texte.split() for texte in textes]


POSTES_TECH = _expressions(
    "engineer", "engineering", "ingenieur", "ingenieure", "developer", "developpeur", "developpeuse",
    "devops", "sre", "software", "logiciel", "programmer", "scientist", "researcher", "research",
    "recherche", "chercheur", "chercheuse", "data", "ml", "ai", "ia", "llm", "nlp", "machine",
    "python", "c++", "rust", "kernel", "compiler", "gpu", "cuda", "infrastructure", "platform",
    "backend", "frontend", "fullstack", "cloud", "cybersecurity", "cybersecurite", "security", "securite",
    "architect", "architecte", "algorithm", "algorithmique", "technical staff",
)
POSTES_FINANCE = _expressions(
    "quant", "quantitatif", "quantitative", "trader", "trading", "portfolio", "structurer", "structuring",
    "derivatives", "derives", "pricing", "risk", "risque", "strats", "market making", "market maker",
)
# Fonctions non techniques : écartées même si l'intitulé contient « engineer » ou « data »
# (« Technical Recruiter », « Sales Engineer », « HR Data Analyst »).
FONCTIONS_NON_TECH = _expressions(
    "rh", "hrbp", "people", "recruiter", "recruiting", "recruitment", "recrutement", "recruteur",
    "talent", "sourcer", "payroll", "paie", "sales", "vente", "ventes", "commercial", "account",
    "marketing", "communications", "communication", "legal", "counsel", "juriste", "avocat",
    "paralegal", "policy", "gtm", "go market", "customer success", "business development",
    "business partner", "executive assistant", "office manager",
)


def poste_tech_pertinent(titre, groupe, mots_cles):
    if mots_cles and intitule_pertinent(titre, mots_cles):
        return True
    jetons = _jetons(titre)
    if any(_expression_presente(e, jetons) for e in FONCTIONS_NON_TECH):
        return False
    vocabulaire = POSTES_TECH + (POSTES_FINANCE if groupe == "finance" else [])
    return any(_expression_presente(e, jetons) for e in vocabulaire)


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


def _nettoie_html(brut):
    """Retire les balises et décode les entités (« &amp; » → « & »)."""
    return re.sub(r"\s+", " ", _decoder_entites(re.sub(r"<[^>]+>", " ", brut or ""))).strip()


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


def source_meta(url, nom="Meta"):
    """Meta Careers — API GraphQL non documentée : meilleur effort, souvent verrouillée.
    En cas d'échec, le lien direct reste disponible dans le bandeau de l'application."""
    s = requests.Session()
    r = s.get(url, headers=NAVIGATEUR, timeout=TIMEOUT)
    r.raise_for_status()
    m = re.search(r'"LSD",\[\],\{"token":"([^"]+)"', r.text)
    if not m:
        raise RuntimeError("jeton d'accès introuvable (page protégée)")
    lsd = m.group(1)
    variables = {"search_input": {
        "q": None, "divisions": [], "offices": ["Paris, France"],
        "roles": ["Full time employment"], "teams": ["Artificial Intelligence"],
        "leadership_levels": [], "saved_jobs": [], "saved_searches": [], "sub_teams": [],
        "is_leadership": False, "is_remote_only": False, "sort_by_new": True,
        "results_per_page": None,
    }}
    r2 = s.post("https://www.metacareers.com/graphql",
                data={"lsd": lsd, "variables": json.dumps(variables),
                      "doc_id": "9114524511922157",
                      "fb_api_req_friendly_name": "CareersJobSearchResultsDataQuery"},
                headers={**NAVIGATEUR, "x-fb-lsd": lsd,
                         "content-type": "application/x-www-form-urlencoded"},
                timeout=TIMEOUT)
    r2.raise_for_status()
    d = json.loads(r2.text.split("\n")[0])
    donnees = d.get("data") or {}
    jobs = (donnees.get("job_search_with_featured_jobs") or {}).get("all_jobs") \
        or donnees.get("job_search") or []
    out = []
    for j in jobs:
        out.append(offre(j.get("id"), j.get("title"), nom,
                         ", ".join(j.get("locations") or ["Paris"]),
                         f"https://www.metacareers.com/jobs/{j.get('id')}", "Site carrière"))
    if not out:
        raise RuntimeError("API Meta inaccessible — utilisez le lien direct")
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


def source_talentview(hote, nom):
    """Plateforme Talentview (Tikehau…) — tentative sur les API JSON usuelles."""
    derniere, reussi = None, False
    out = []
    for chemin in ("/api/v1/jobs", "/api/jobs", "/api/offers", "/api/search"):
        try:
            r = requests.get(hote + chemin, params={"city": "Paris", "distance": 50},
                             headers={**NAVIGATEUR, "Accept": "application/json"},
                             timeout=TIMEOUT)
            r.raise_for_status()
            d = r.json()
            jobs = d if isinstance(d, list) else (
                d.get("jobs") or d.get("data") or d.get("results") or d.get("hits") or [])
            reussi = True
            for j in jobs:
                if not isinstance(j, dict):
                    continue
                titre = j.get("title") or j.get("name") or j.get("label")
                if not titre:
                    continue
                lieu = str(j.get("city") or j.get("location") or "Paris")
                if not lieu_en_idf(lieu):
                    continue
                ident = j.get("id") or j.get("slug") or titre
                out.append(offre(ident, titre, nom, lieu,
                                 j.get("url") or j.get("link") or hote, "Site carrière",
                                 date_iso(j.get("published_at") or j.get("created_at"))))
            if out:
                return out
        except Exception as e:
            derniere = e
    if reussi:
        return out
    raise RuntimeError(f"API introuvable — utilisez le lien direct ({derniere})")


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


def source_village_justice(mots):
    """Village de la Justice — flux RSS officiel de la catégorie Île-de-France (cat=155),
    avec repli sur la page HTML si le flux est indisponible."""
    import xml.etree.ElementTree as ET
    out = []
    try:
        r = requests.get("https://www.village-justice.com/annonces/rss.php",
                         params={"cat": "155"}, headers=UA, timeout=TIMEOUT)
        r.raise_for_status()
        racine = ET.fromstring(r.content)
        for item in racine.iter("item"):
            titre = (item.findtext("title") or "").strip()
            lien = (item.findtext("link") or "").strip()
            desc = re.sub(r"<[^>]+>", " ", item.findtext("description") or "")
            desc = re.sub(r"\s+", " ", desc).strip()
            date = None
            brut = item.findtext("pubDate")
            if brut:
                try:
                    date = parsedate_to_datetime(brut).isoformat()
                except Exception:
                    date = date_iso(brut)
            ident = lien.rstrip("/").rsplit("/", 1)[-1] or titre
            o = offre(ident, titre, "Village de la Justice", "Île-de-France",
                      lien, "Village Justice", date, "", desc)
            if annonce_juridique_pertinente(titre, desc, mots):
                out.append(o)
        return out
    except Exception:
        pass  # repli HTML ci-dessous

    r = requests.get("https://www.village-justice.com/annonces/index.php",
                     params={"cat": "155"}, headers=UA, timeout=TIMEOUT)
    r.raise_for_status()
    for m in re.finditer(
        r'href="(https://www\.village-justice\.com/annonces/[^"]*/offres/(\d+)[^"]*)"[^>]*>(.*?)</a>',
        r.text, re.S,
    ):
        lien, ident, brut = m.group(1), m.group(2), m.group(3)
        titre = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", brut)).strip()
        if not titre or any(o["id"].endswith(f":{ident}") for o in out):
            continue
        o = offre(ident, titre, "Village de la Justice", "Île-de-France",
                  lien.split("?")[0], "Village Justice")
        if annonce_juridique_pertinente(titre, "", mots):
            out.append(o)
    return out


def source_carrieres_juridiques(mots):
    """Carrières-Juridiques.com — lecture des pages d'offres publiques,
    puis filtrage local Île-de-France + pertinence."""
    out = []
    for page in (1, 2, 3):
        r = requests.get("https://www.carrieres-juridiques.com/emploi-juridique",
                         params={"page": page} if page > 1 else None,
                         headers=UA, timeout=TIMEOUT)
        if page == 1:
            r.raise_for_status()
        elif r.status_code != 200:
            break
        html = r.text
        # une annonce = un lien /offre/<slug>/<id> ; on découpe le HTML par annonce
        liens = list(re.finditer(r'<a[^>]+href="(/offre/[^"]+/(\d+))"[^>]*>(.*?)</a>', html, re.S))
        for i, m in enumerate(liens):
            chemin, ident, brut = m.group(1), m.group(2), m.group(3)
            titre = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", brut)).strip()
            if not titre:
                continue
            bloc = html[m.end(): liens[i + 1].start() if i + 1 < len(liens) else m.end() + 2500]
            entreprise = ""
            e = re.search(
                r'href="/(?:emploi-juridique-offre|metiers-du-droit-jobfair-virtuelle)/[^"]+"[^>]*>(.*?)</a>',
                bloc, re.S,
            )
            if e:
                entreprise = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", e.group(1))).strip()
            contrat = ""
            c = re.search(r"\b(CDI|CDD|Stage|Contrat d'apprentissage|Contrat en alternance|"
                          r"Contrat de collaboration|VIE)\b", bloc)
            if c:
                contrat = c.group(1)
            d = re.search(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}", bloc)
            date = date_iso(d.group(0)) if d else None
            # le lieu apparaît en texte libre dans le bloc ; on cherche une mention IDF
            texte_bloc = re.sub(r"<[^>]+>", " ", bloc)
            if not lieu_en_idf(texte_bloc, strict=True):
                continue
            lieu = "Île-de-France"
            v = re.search(r"(?i)\b(paris(?:\s*\d{1,2}(?:e|er|ème|eme)?)?|hauts-de-seine|"
                          r"seine-saint-denis|val-de-marne|val-d'oise|yvelines|essonne|"
                          r"seine-et-marne|ile de france|île-de-france)\b",
                          texte_bloc)
            if v:
                lieu = v.group(1).strip().title()
            o = offre(ident, titre, entreprise,
                      lieu, f"https://www.carrieres-juridiques.com{chemin}",
                      "Carrières Juridiques", date, contrat)
            if annonce_juridique_pertinente(titre, "", mots):
                out.append(o)
        if "page=" + str(page + 1) not in html:
            break
    # dédoublonne par identifiant (une annonce peut être « à la une » et dans la liste)
    vus, uniques = set(), []
    for o in out:
        if o["id"] in vus:
            continue
        vus.add(o["id"])
        uniques.append(o)
    return uniques

# ==========================================================================
# Catalogue des sites lisibles par le relais
# ==========================================================================
# groupe : famille de sites, rattachée aux secteurs dans l'application
# mots   : True si le site est interrogé avec les mots-clés du secteur
# lien   : page du site déjà filtrée (bouton « Ouvrir le site » dans l'app)
GROUPES = {
    "juridique": "Sites juridiques",
    "generalistes": "Sites d'emploi généralistes",
    "startups": "Startups et scale-ups",
    "big_tech": "Big Tech",
    "finance": "Finance de marché",
}

CATALOGUE = {
    # --- Droit & RH ---------------------------------------------------------
    "village_justice": {"nom": "Village de la Justice", "groupe": "juridique", "type": "village_justice", "mots": True,
                        "lien": "https://www.village-justice.com/annonces/avocats-juristes-autres/emploi/ile-de-france-paris.html"},
    "carrieres_juridiques": {"nom": "Carrières Juridiques", "groupe": "juridique", "type": "carrieres_juridiques", "mots": True,
                             "lien": "https://www.carrieres-juridiques.com/emploi-juridique"},
    "cadremploi": {"nom": "Cadremploi", "groupe": "generalistes", "type": "cadremploi", "mots": True,
                   "lien": "https://www.cadremploi.fr/emploi/liste_offres?motscles=juriste&localisation=%C3%8Ele-de-France"},
    "france_travail": {"nom": "France Travail", "groupe": "generalistes", "type": "france_travail", "mots": True,
                       "cle": "france_travail"},
    "adzuna": {"nom": "Adzuna (Indeed, LinkedIn…)", "groupe": "generalistes", "type": "adzuna", "mots": True,
               "cle": "adzuna"},
    # --- Startups -------------------------------------------------------------
    "wttj": {"nom": "Welcome to the Jungle", "groupe": "startups", "type": "wttj", "mots": True,
             "lien": "https://www.welcometothejungle.com/fr/jobs"},
    # --- Big Tech -------------------------------------------------------------
    "openai": {"nom": "OpenAI", "groupe": "big_tech", "type": "ashby", "slug": "openai",
               "lien": "https://openai.com/careers/search/?l=a875cd3f-88a3-4d2d-9e24-6e985f2c86d5"},
    "anthropic": {"nom": "Anthropic", "groupe": "big_tech", "type": "greenhouse", "slug": "anthropic",
                  "lien": "https://www.anthropic.com/careers/jobs?office=4045847008"},
    "mistral": {"nom": "Mistral AI", "groupe": "big_tech", "type": "lever", "slug": "mistral",
                "lien": "https://jobs.lever.co/mistral?location=Paris&commitment=Full-time"},
    "google": {"nom": "Google", "groupe": "big_tech", "type": "google",
               "url": "https://www.google.com/about/careers/applications/jobs/results?hl=en_US&location=Paris%2C%20France&degree=MASTERS&employment_type=FULL_TIME",
               "lien": "https://www.google.com/about/careers/applications/jobs/results?hl=en_US&location=Paris%2C%20France&degree=MASTERS&employment_type=FULL_TIME"},
    # Meta interdit la collecte automatisée sur ses sites : lien direct uniquement, jamais lu par le relais.
    "meta": {"nom": "Meta", "groupe": "big_tech", "type": "meta", "lien_seul": True,
             "url": "https://www.metacareers.com/jobsearch/?teams[0]=Artificial%20Intelligence&offices[0]=Paris%2C%20France&roles[0]=Full%20time%20employment",
             "lien": "https://www.metacareers.com/jobsearch/?teams[0]=Artificial%20Intelligence&offices[0]=Paris%2C%20France&roles[0]=Full%20time%20employment"},
    "apple": {"nom": "Apple", "groupe": "big_tech", "type": "apple",
              "url": "https://jobs.apple.com/fr-fr/search?location=paris-PAR&team=infrastructure-d-apprentissage-automatique-MLAI-MLI+apprentissage-en-profondeur-et-apprentissage-par-renforcement-MLAI-DLRL+traitement-du-langage-naturel-et-technologies-vocales-MLAI-NLP+vision-artificielle-MLAI-CV+recherche-appliqu%25C3%25A9e-MLAI-AR+apps-et-frameworks-SFTWR-AF+cloud-et-infrastructures-SFTWR-CLD+syst%25C3%25A8mes-d-exploitation-cl%25C3%25A9s-SFTWR-COS+devops-et-fiabilit%25C3%25A9-des-sites-SFTWR-DSR+gestion-de-projets-d-ing%25C3%25A9nierie-SFTWR-EPM+service-informatique-SFTWR-ISTECH+apprentissage-automatique-SFTWR-MCHLN+s%25C3%25A9curit%25C3%25A9-et-confidentialit%25C3%25A9-SFTWR-SEC+qualit%25C3%25A9-des-logiciels-automatisation-outils-SFTWR-SQAT+logiciels-sans-fil-SFTWR-WSFT",
              "lien": "https://jobs.apple.com/fr-fr/search?location=paris-PAR&team=infrastructure-d-apprentissage-automatique-MLAI-MLI+apprentissage-en-profondeur-et-apprentissage-par-renforcement-MLAI-DLRL+traitement-du-langage-naturel-et-technologies-vocales-MLAI-NLP+vision-artificielle-MLAI-CV+recherche-appliqu%25C3%25A9e-MLAI-AR+apps-et-frameworks-SFTWR-AF+cloud-et-infrastructures-SFTWR-CLD+syst%25C3%25A8mes-d-exploitation-cl%25C3%25A9s-SFTWR-COS+devops-et-fiabilit%25C3%25A9-des-sites-SFTWR-DSR+gestion-de-projets-d-ing%25C3%25A9nierie-SFTWR-EPM+service-informatique-SFTWR-ISTECH+apprentissage-automatique-SFTWR-MCHLN+s%25C3%25A9curit%25C3%25A9-et-confidentialit%25C3%25A9-SFTWR-SEC+qualit%25C3%25A9-des-logiciels-automatisation-outils-SFTWR-SQAT+logiciels-sans-fil-SFTWR-WSFT"},
    "microsoft": {"nom": "Microsoft", "groupe": "big_tech", "type": "eightfold",
                  "hote": "https://apply.careers.microsoft.com", "domaine": "microsoft.com",
                  "lien": "https://apply.careers.microsoft.com/careers?start=0&location=Paris%2C++IDF%2C++France&sort_by=match&filter_distance=160&filter_include_remote=1"},
    # --- Finance de marché ----------------------------------------------------
    "qube": {"nom": "Qube RT", "groupe": "finance", "type": "greenhouse", "slug": "quberesearchandtechnologies",
             "lien": "https://www.qube-rt.com/careers/"},
    "cfm": {"nom": "CFM", "groupe": "finance", "type": "successfactors", "hote": "https://jobs.cfm.com",
            "lien": "https://jobs.cfm.com/search/?q=&locationsearch=Paris"},
    "point72": {"nom": "Point72", "groupe": "finance", "type": "greenhouse", "slug": "point72",
                "lien": "https://careers.point72.com/?location=paris"},
    "millennium": {"nom": "Millennium", "groupe": "finance", "type": "eightfold",
                   "hote": "https://career.mlp.com", "domaine": "mlp.com",
                   "lien": "https://career.mlp.com/careers?location=Paris%2C%20France&domain=mlp.com&sort_by=relevance"},
    "squarepoint": {"nom": "Squarepoint", "groupe": "finance", "type": "greenhouse", "slug": "squarepointcapital",
                    "lien": "https://www.squarepoint-capital.com/open-opportunities?loc=14636"},
    "citadel": {"nom": "Citadel", "groupe": "finance", "type": "citadel",
                "lien": "https://www.citadel.com/careers/open-opportunities?location-filter=paris&selected-job-sections=388,389,387,390&current_page=1&sort_order=DESC&per_page=10&action=careers_listing_filter"},
    "jpmorgan": {"nom": "JPMorgan", "groupe": "finance", "type": "oracle",
                 "hote": "https://jpmc.fa.oraclecloud.com", "site": "CX_1001", "lieu_id": "300000036802490",
                 "lien": "https://jpmc.fa.oraclecloud.com/hcmUI/CandidateExperience/en/sites/CX_1001/jobs?location=Paris%2C+France&locationId=300000036802490&locationLevel=state&mode=location"},
    "goldmansachs": {"nom": "Goldman Sachs", "groupe": "finance", "type": "gs",
                     "lien": "https://higher.gs.com/results?LOCATION=Paris&page=1&sort=RELEVANCE"},
    "bofa": {"nom": "Bank of America", "groupe": "finance", "type": "bofa",
             "lien": "https://careers.bankofamerica.com/en-us/job-search/france?ref=search&start=0&rows=10&search=jobsByLocation&searchstring=Paris%2C+France"},
    "citi": {"nom": "Citi", "groupe": "finance", "type": "citi",
             "url": "https://jobs.citi.com/location/paris-jobs/287/3017382-3012874-2968815-2988506-6455259-2988507/4",
             "lien": "https://jobs.citi.com/location/paris-jobs/287/3017382-3012874-2968815-2988506-6455259-2988507/4"},
}

# sites interrogés une fois par mot-clé (en parallèle) ; les autres sont lus d'un bloc
PAR_MOT_CLE = {"france_travail", "adzuna", "wttj", "cadremploi"}


# ==========================================================================
# Configuration (variables d'environnement Vercel)
# ==========================================================================
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


def catalogue_public():
    return [
        {"id": cle, "nom": c["nom"], "groupe": c["groupe"], "mots": bool(c.get("mots")),
         "lien_seul": bool(c.get("lien_seul")),
         "lien": c.get("lien"), "cle_manquante": bool(c.get("cle")) and not cle_disponible(c["cle"])}
        for cle, c in CATALOGUE.items()
    ]


# ==========================================================================
# Vérification du compte (jeton Firebase)
# ==========================================================================
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
    _jetons_valides[jeton] = maintenant + 45 * 60  # un jeton Firebase vit 60 min


# ==========================================================================
# Lecture d'un site
# ==========================================================================
def _executer(conf, mots):
    t = conf["type"]
    nom = conf["nom"]
    if t == "france_travail":
        return source_france_travail(mots, cles_api())
    if t == "adzuna":
        return source_adzuna(mots, cles_api())
    if t == "wttj":
        return source_wttj(mots)
    if t == "cadremploi":
        return source_cadremploi(mots)
    if t == "village_justice":
        return source_village_justice(mots)
    if t == "carrieres_juridiques":
        return source_carrieres_juridiques(mots)
    if t == "greenhouse":
        return source_greenhouse(conf["slug"], nom)
    if t == "lever":
        return source_lever(conf["slug"], nom)
    if t == "ashby":
        return source_ashby(conf["slug"], nom)
    if t == "eightfold":
        return source_eightfold(conf["hote"], conf["domaine"], nom)
    if t == "oracle":
        return source_oracle(conf["hote"], conf["site"], conf["lieu_id"], nom)
    if t == "successfactors":
        return source_successfactors(conf["hote"], nom)
    if t == "citadel":
        return source_citadel(nom)
    if t == "google":
        return source_google(conf["url"], nom)
    if t == "apple":
        return source_apple(conf["url"], nom)
    if t == "meta":
        return source_meta(conf["url"], nom)
    if t == "gs":
        return source_gs(nom)
    if t == "bofa":
        return source_bofa(nom)
    if t == "citi":
        return source_citi(conf["url"], nom)
    if t == "talentview":
        return source_talentview(conf["hote"], nom)
    raise RuntimeError(f"type de site inconnu : {t}")


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
            for fut in [pool.submit(_executer, conf, [m]) for m in mots]:
                try:
                    offres.extend(fut.result())
                except Exception as e:  # noqa: BLE001
                    erreurs.append(e)
        if erreurs and len(erreurs) == len(mots):
            raise erreurs[0]
    else:
        offres = _executer(conf, mots)

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


# ==========================================================================
# Point d'entrée HTTP (format attendu par Vercel)
# ==========================================================================
class handler(BaseHTTPRequestHandler):
    def _json(self, code, contenu):
        corps = json.dumps(contenu, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(corps)))
        self.end_headers()
        self.wfile.write(corps)

    def do_GET(self):  # noqa: N802
        self._json(200, {
            "firebase": firebase_config(),
            "groupes": GROUPES,
            "catalogue": catalogue_public(),
        })

    def do_POST(self):  # noqa: N802
        try:
            longueur = min(int(self.headers.get("Content-Length") or 0), 20000)
            demande = json.loads(self.rfile.read(longueur) or b"{}")
        except Exception:
            return self._json(400, {"etat": "erreur", "offres": [], "detail": "requête illisible"})
        try:
            verifier_jeton(self.headers.get("Authorization", ""))
        except CompteRefuse as e:
            return self._json(403, {"etat": "erreur", "offres": [], "detail": str(e)})
        except PermissionError as e:
            return self._json(401, {"etat": "erreur", "offres": [], "detail": str(e)})
        except Exception as e:  # noqa: BLE001
            return self._json(500, {"etat": "erreur", "offres": [], "detail": f"vérification impossible : {e}"})
        try:
            resultat = lire_source(str(demande.get("source", "")), _mots_propres(demande.get("mots")))
        except Exception as e:  # noqa: BLE001
            resultat = {"etat": "erreur", "offres": [], "detail": str(e)[:200]}
        self._json(200, resultat)

    def log_message(self, *args):  # journal Vercel suffisant
        pass
