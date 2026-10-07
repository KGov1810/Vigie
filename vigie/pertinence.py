"""Tri des offres : correspondent-elles aux mots-clés et au métier recherché ?"""
import re
import unicodedata


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


MOTS_SOUPLES = {"droit", "senior", "junior", "confirme", "confirmee", "experimente", "experimentee"}


EQUIVALENCES = [
    (re.compile(r"\bressources? humaines?\b"), "rh"),
    (re.compile(r"\bhuman resources?\b"), "rh"),
    (re.compile(r"\bhr\b"), "rh"),
]


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
