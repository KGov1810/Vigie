"""Sites juridiques : Village de la Justice et Carrières Juridiques."""
import requests
import re
from email.utils import parsedate_to_datetime

from ..communs import TIMEOUT, UA, date_iso, lieu_en_idf, offre
from ..pertinence import annonce_juridique_pertinente


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
