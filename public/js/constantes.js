// Réglages par défaut de chaque domaine et constantes de l'application.
/* ════════════════════════════════════════════════════════════════
   Réglages par défaut de chaque domaine (créés au premier lancement)
   ════════════════════════════════════════════════════════════════ */
export const DEFAUTS = {
  droit: {
    nom: "Droit & RH",
    secteurs: [
      { nom: "Droit du travail", mots: ["juriste droit du travail", "juriste droit social"], groupes: ["juridique", "generalistes"] },
      { nom: "Ressources humaines", mots: ["chargé ressources humaines", "gestionnaire RH", "juriste RH"], groupes: ["juridique", "generalistes"] },
      { nom: "Droit des affaires", mots: ["juriste droit des affaires", "juriste droit des sociétés"], groupes: ["juridique", "generalistes"] },
      { nom: "Droit pénal", mots: ["juriste droit pénal", "avocat droit pénal"], groupes: ["juridique", "generalistes"] },
    ],
  },
  tech: {
    nom: "Finance & Tech",
    secteurs: [
      { nom: "Big Tech", mots: ["software engineer", "data scientist", "machine learning engineer"], groupes: ["big_tech", "startups"] },
      { nom: "Finance de marché", mots: ["analyste quantitatif python", "quant developer", "finance de marché python", "risk analyst python"], groupes: ["finance", "startups"] },
    ],
  },
};

// familles de sites proposées à chaque domaine dans Réglages
export const GROUPES_PROFIL = {
  droit: ["juridique", "generalistes", "startups"],
  tech: ["big_tech", "finance", "startups"],
};

export const CONTRATS = { cdi: "CDI", cdd: "CDD, intérim", alternance: "Alternance", stage: "Stage", autre: "Non précisé" };

export const STATUTS = {
  a_postuler: "À postuler",
  postulee: "Postulée",
  relance: "Relancée",
  entretien: "Entretien",
  acceptee: "Acceptée",
  refusee: "Refusée",
};

export const JOURS_AVANT_RELANCE = 8;

export const JOUR = 86400000;

export const DELAI_SITE = 35000;

 // au-delà, un site est considéré comme muet
export const REACTUALISER_APRES = 5 * 60000;
