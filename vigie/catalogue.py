"""Catalogue des sites lisibles par le relais (aucune autre adresse n'est jamais lue)."""
from .config import cle_disponible


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
    # Mistral recrute sur Ashby : deux départements choisis, à Paris, en CDI (filtres de la page Ashby)
    "mistral": {"nom": "Mistral AI", "groupe": "big_tech", "type": "ashby_filtre", "organisation": "mistral.ai",
                "departements": ["0e254708-ce04-4bd7-8fbe-c6b9a45e0f16", "cdcd26c0-0c1e-4aff-91f7-5f6306b726b3"],
                "lieu_id": "bb6ddf2e-f6bf-4259-a8ca-09d5e2c51f7b", "contrat": "FullTime",
                "lien": "https://jobs.ashbyhq.com/mistral.ai?employmentType=FullTime&locationId=bb6ddf2e-f6bf-4259-a8ca-09d5e2c51f7b"},
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


PAR_MOT_CLE = {"france_travail", "adzuna", "wttj", "cadremploi"}


def catalogue_public():
    return [
        {"id": cle, "nom": c["nom"], "groupe": c["groupe"], "mots": bool(c.get("mots")),
         "lien_seul": bool(c.get("lien_seul")),
         "lien": c.get("lien"), "cle_manquante": bool(c.get("cle")) and not cle_disponible(c["cle"])}
        for cle, c in CATALOGUE.items()
    ]
