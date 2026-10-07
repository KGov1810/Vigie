"""Aiguillage : à chaque type de site du catalogue correspond la fonction qui sait le lire."""
from ..config import cles_api
from .big_tech import source_apple, source_google
from .emploi import source_adzuna, source_cadremploi, source_france_travail
from .finance import source_bofa, source_citadel, source_citi, source_gs
from .juridique import source_carrieres_juridiques, source_village_justice
from .plateformes import (source_ashby, source_ashby_filtre, source_eightfold, source_greenhouse, source_lever,
                          source_oracle, source_successfactors)
from .startups import source_wttj

# type -> fonction(conf, mots) ; conf est l'entrée du catalogue, mots les mots-clés du secteur
LECTEURS = {
    # sites interrogés avec les mots-clés
    "france_travail": lambda conf, mots: source_france_travail(mots, cles_api()),
    "adzuna": lambda conf, mots: source_adzuna(mots, cles_api()),
    "wttj": lambda conf, mots: source_wttj(mots),
    "cadremploi": lambda conf, mots: source_cadremploi(mots),
    "village_justice": lambda conf, mots: source_village_justice(mots),
    "carrieres_juridiques": lambda conf, mots: source_carrieres_juridiques(mots),
    # plateformes de recrutement partagées
    "greenhouse": lambda conf, mots: source_greenhouse(conf["slug"], conf["nom"]),
    "lever": lambda conf, mots: source_lever(conf["slug"], conf["nom"]),
    "ashby": lambda conf, mots: source_ashby(conf["slug"], conf["nom"]),
    "ashby_filtre": lambda conf, mots: source_ashby_filtre(conf["organisation"], conf["departements"],
                                                          conf["lieu_id"], conf["contrat"], conf["nom"]),
    "eightfold": lambda conf, mots: source_eightfold(conf["hote"], conf["domaine"], conf["nom"]),
    "oracle": lambda conf, mots: source_oracle(conf["hote"], conf["site"], conf["lieu_id"], conf["nom"]),
    "successfactors": lambda conf, mots: source_successfactors(conf["hote"], conf["nom"]),
    # sites carrières propres à une entreprise
    "google": lambda conf, mots: source_google(conf["url"], conf["nom"]),
    "apple": lambda conf, mots: source_apple(conf["url"], conf["nom"]),
    "citadel": lambda conf, mots: source_citadel(conf["nom"]),
    "gs": lambda conf, mots: source_gs(conf["nom"]),
    "bofa": lambda conf, mots: source_bofa(conf["nom"]),
    "citi": lambda conf, mots: source_citi(conf["url"], conf["nom"]),
}


def lire_site(conf, mots):
    lecteur = LECTEURS.get(conf["type"])
    if not lecteur:
        raise RuntimeError(f"type de site inconnu : {conf['type']}")
    return lecteur(conf, mots)
