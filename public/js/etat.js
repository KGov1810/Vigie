// État partagé de l'application (compte, profil, offres, favoris, candidatures…).
// au retour dans l'app

/* ════════════════════════════════════════════════════════════════
   État
   ════════════════════════════════════════════════════════════════ */
export const etat = {
  config: null,
  catalogue: {},
  user: null,
  profil: null,
  profilJson: "",
  secteur: "",
  parSource: new Map(), // id du site -> offres reçues
  etats: {}, // id du site -> { etat, detail, n }
  attendus: 0,
  recus: 0,
  enCours: null,
  derniereMaj: null,
  vues: {},
  vuesVides: true,
  vuesModifiees: false,
  favoris: new Map(),
  candidatures: new Map(),
  index: new Map(), // hachage -> offre affichée (pour les boutons)
  vue: "offres",
  abonnements: [],
  collectionsSuivies: false,
  reglagesModifies: false,
  renduCandidaturesEnAttente: false,
};
