import * as FB from "./firebase.js";

/* ════════════════════════════════════════════════════════════════
   Réglages par défaut de chaque domaine (créés au premier lancement)
   ════════════════════════════════════════════════════════════════ */
const DEFAUTS = {
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
const GROUPES_PROFIL = {
  droit: ["juridique", "generalistes", "startups"],
  tech: ["big_tech", "finance", "startups"],
};
const CONTRATS = { cdi: "CDI", cdd: "CDD, intérim", alternance: "Alternance", stage: "Stage", autre: "Non précisé" };
const STATUTS = {
  a_postuler: "À postuler",
  postulee: "Postulée",
  relance: "Relancée",
  entretien: "Entretien",
  acceptee: "Acceptée",
  refusee: "Refusée",
};
const JOURS_AVANT_RELANCE = 8;
const JOUR = 86400000;
const DELAI_SITE = 35000; // au-delà, un site est considéré comme muet
const REACTUALISER_APRES = 5 * 60000; // au retour dans l'app

/* ════════════════════════════════════════════════════════════════
   État
   ════════════════════════════════════════════════════════════════ */
const etat = {
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

/* ════════════════════════════════════════════════════════════════
   Utilitaires
   ════════════════════════════════════════════════════════════════ */
const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];

function echappe(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

function normaliser(s) {
  return String(s || "").toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "").replace(/[^a-z0-9+#]+/g, " ").trim();
}

// identifiant court et sûr pour Firestore (les identifiants d'offres contiennent « / », « : »…)
function hachage(str) {
  let h1 = 0xdeadbeef, h2 = 0x41c6ce57;
  for (let i = 0; i < str.length; i++) {
    const ch = str.charCodeAt(i);
    h1 = Math.imul(h1 ^ ch, 2654435761);
    h2 = Math.imul(h2 ^ ch, 1597334677);
  }
  h1 = Math.imul(h1 ^ (h1 >>> 16), 2246822507) ^ Math.imul(h2 ^ (h2 >>> 13), 3266489909);
  h2 = Math.imul(h2 ^ (h2 >>> 16), 2246822507) ^ Math.imul(h1 ^ (h1 >>> 13), 3266489909);
  return "o" + (4294967296 * (2097151 & h2) + (h1 >>> 0)).toString(36);
}

function categorieContrat(brut) {
  const t = normaliser(brut);
  if (!t) return "autre";
  if (/alternance|apprenti|professionnalisation|apprenticeship|work study/.test(t)) return "alternance";
  if (/stage|intern/.test(t)) return "stage";
  if (/indetermin|\bcdi\b|permanent/.test(t)) return "cdi";
  if (/\bcdd\b|temporaire|temporary|interim|saisonnier|determin|fixed|contractor|\bmis\b|\bsai\b|\bvie\b|freelance/.test(t)) return "cdd";
  if (/full time|collaboration|temps plein/.test(t)) return "cdi";
  return "autre";
}

function joursDepuis(ms) {
  const debut = new Date(); debut.setHours(0, 0, 0, 0);
  const d = new Date(ms); d.setHours(0, 0, 0, 0);
  return Math.round((debut - d) / JOUR);
}
function relatif(ms) {
  const j = joursDepuis(ms);
  if (j <= 0) return "aujourd'hui";
  if (j === 1) return "hier";
  if (j < 30) return `il y a ${j} j`;
  const m = Math.round(j / 30);
  return `il y a ${m} mois`;
}
function depuisMinutes(ms) {
  const min = Math.round((Date.now() - ms) / 60000);
  if (min < 1) return "à l'instant";
  if (min < 60) return `il y a ${min} min`;
  const h = Math.floor(min / 60);
  if (h < 24) return `il y a ${h} h`;
  return relatif(ms);
}

let minuteurToast;
function toast(message) {
  const t = $("#toast");
  t.textContent = message;
  t.hidden = false;
  clearTimeout(minuteurToast);
  minuteurToast = setTimeout(() => { t.hidden = true; }, 3800);
}

function afficherEcran(nom) {
  for (const id of ["demarrage", "ecran-erreur", "ecran-connexion", "ecran-profil", "app"]) {
    $("#" + id).hidden = id !== nom;
  }
}

function erreur(titre, html) {
  $("#erreur-titre").textContent = titre;
  $("#erreur-texte").innerHTML = html;
  afficherEcran("ecran-erreur");
}

/* ════════════════════════════════════════════════════════════════
   Démarrage
   ════════════════════════════════════════════════════════════════ */
async function demarrer() {
  afficherEcran("demarrage");
  let config;
  try {
    const r = await fetch("/api/relais", { cache: "no-store" });
    if (!r.ok) throw new Error("HTTP " + r.status);
    config = await r.json();
    localStorage.setItem("vigie-config", JSON.stringify(config));
  } catch {
    try { config = JSON.parse(localStorage.getItem("vigie-config") || "null"); } catch { config = null; }
    if (!config) {
      return erreur("Pas de connexion",
        "<p>Vigie a besoin d'internet pour son tout premier lancement. Vérifiez votre réseau, puis réessayez.</p>");
    }
  }
  if (!config.firebase || !config.firebase.apiKey) {
    return erreur("Vigie n'est pas encore reliée à Firebase",
      `<p>Il manque la configuration Firebase sur Vercel :</p>
       <ol>
         <li>Dans Vercel, ouvrez votre projet, puis <strong>Settings</strong> et <strong>Environment Variables</strong>.</li>
         <li>Ajoutez la variable <code>FIREBASE_CONFIG</code> et collez-y la configuration copiée depuis Firebase.</li>
         <li>Dans <strong>Deployments</strong>, relancez le dernier déploiement avec <strong>Redeploy</strong>.</li>
       </ol>
       <p>Le guide d'installation détaille chaque étape.</p>`);
  }
  etat.config = config;
  etat.catalogue = Object.fromEntries(config.catalogue.map((c) => [c.id, c]));
  try {
    await FB.initialiser(config.firebase);
  } catch {
    return erreur("Firebase ne répond pas",
      "<p>Les outils de connexion n'ont pas pu être chargés. Vérifiez votre réseau, puis réessayez.</p>");
  }
  FB.surChangementCompte(surCompte);
}

function surCompte(user) {
  etat.abonnements.forEach((f) => f());
  etat.abonnements = [];
  etat.enCours?.abort();
  Object.assign(etat, {
    user, profil: null, profilJson: "", parSource: new Map(), etats: {}, favoris: new Map(),
    candidatures: new Map(), vues: {}, derniereMaj: null, reglagesModifies: false,
    collectionsSuivies: false,
  });
  if (!user) {
    afficherEcran("ecran-connexion");
    return;
  }
  afficherEcran("demarrage");
  etat.abonnements.push(FB.ecouterProfil(user.uid, (profil, depuisCache, err) => {
    if (profil === undefined) {
      if (!etat.profil) erreur("Données inaccessibles", `<p>Firebase a refusé la lecture de votre profil. Vérifiez les règles Firestore décrites dans le guide.</p><p>${echappe(err?.message || "")}</p>`);
      return;
    }
    if (!profil) {
      if (depuisCache && navigator.onLine) return; // on attend la réponse du serveur
      if (depuisCache) return erreur("Pas de connexion", "<p>Connectez-vous à internet pour terminer la première configuration.</p>");
      afficherEcran("ecran-profil");
      return;
    }
    const json = JSON.stringify(profil);
    if (json === etat.profilJson) return;
    const domaineAvant = etat.profil?.profil;
    etat.profil = profil;
    etat.profilJson = json;
    if (domaineAvant !== profil.profil) lancerApp();
    else surProfilModifie();
  }));
}

async function lancerApp() {
  const uid = etat.user.uid;
  document.documentElement.dataset.profil = etat.profil.profil;
  $("#nom-profil").textContent = etat.profil.nom;
  $("#compte-email").textContent = `Connecté avec ${etat.user.email}`;
  afficherEcran("app");
  montrerVue("offres");

  const memorise = localStorage.getItem(`vigie-secteur-${uid}`) || "";
  etat.secteur = etat.profil.secteurs.some((s) => s.nom === memorise) ? memorise : "";

  if (!etat.collectionsSuivies) {
  etat.collectionsSuivies = true;
  etat.abonnements.push(FB.ecouterCollection(uid, "favoris", (docs) => {
    etat.favoris = new Map(docs.map((d) => [d.docId, d]));
    dessinerOffres();
    if (etat.vue === "favoris") dessinerFavoris();
  }));
  etat.abonnements.push(FB.ecouterCollection(uid, "candidatures", (docs) => {
    etat.candidatures = new Map(docs.map((d) => [d.docId, d]));
    majPastille();
    dessinerOffres();
    if (etat.vue === "favoris") dessinerFavoris();
    if (etat.vue === "candidatures") dessinerCandidatures();
  }));
  }

  etat.vues = await FB.lireVues(uid);
  etat.vuesVides = Object.keys(etat.vues).length === 0;

  dessinerSecteurs();
  dessinerReglages();
  dessinerLiensDirects();
  chargerCache();
  dessinerOffres();
  actualiser();
}

function surProfilModifie() {
  $("#nom-profil").textContent = etat.profil.nom;
  if (!etat.profil.secteurs.some((s) => s.nom === etat.secteur)) etat.secteur = "";
  dessinerSecteurs();
  dessinerLiensDirects();
  if (!etat.reglagesModifies) dessinerReglages();
  dessinerFiltres();
  dessinerOffres();
}

/* ════════════════════════════════════════════════════════════════
   Connexion et premier lancement
   ════════════════════════════════════════════════════════════════ */
$("#form-connexion").addEventListener("submit", async (e) => {
  e.preventDefault();
  const email = $("#email").value.trim();
  const mdp = $("#mdp").value;
  const msg = $("#connexion-erreur");
  msg.hidden = true;
  if (!email || !mdp) {
    msg.textContent = "Saisissez votre e-mail et votre mot de passe.";
    msg.hidden = false;
    return;
  }
  const bouton = $("#btn-connexion");
  bouton.disabled = true;
  bouton.textContent = "Connexion…";
  try {
    await FB.connecter(email, mdp);
    $("#mdp").value = "";
  } catch (err) {
    const code = err?.code || "";
    msg.textContent =
      /invalid-credential|wrong-password|user-not-found|invalid-email/.test(code) ? "E-mail ou mot de passe incorrect." :
      /too-many-requests/.test(code) ? "Trop d'essais. Patientez quelques minutes, puis réessayez." :
      /network/.test(code) ? "Pas de connexion internet." :
      "La connexion a échoué. Réessayez.";
    msg.hidden = false;
  } finally {
    bouton.disabled = false;
    bouton.textContent = "Se connecter";
  }
});

$("#btn-mdp-oublie").addEventListener("click", async () => {
  const email = $("#email").value.trim();
  if (!email) {
    const msg = $("#connexion-erreur");
    msg.textContent = "Saisissez d'abord votre e-mail.";
    msg.hidden = false;
    return;
  }
  try {
    await FB.reinitialiserMotDePasse(email);
    toast(`E-mail de réinitialisation envoyé à ${email}.`);
  } catch {
    toast("Envoi impossible. Vérifiez l'adresse e-mail.");
  }
});

$$(".choix-profil").forEach((b) => b.addEventListener("click", () => {
  const id = b.dataset.profil;
  const d = DEFAUTS[id];
  FB.remplacerProfil(etat.user.uid, {
    profil: id, nom: d.nom, secteurs: d.secteurs,
    sources_off: [], filtres: { contrats: [], sources: [] },
    cree_le: new Date().toISOString(),
  });
  afficherEcran("demarrage");
}));

$("#btn-reessayer").addEventListener("click", () => location.reload());

/* ════════════════════════════════════════════════════════════════
   Navigation
   ════════════════════════════════════════════════════════════════ */
function montrerVue(nom) {
  etat.vue = nom;
  for (const v of ["offres", "favoris", "candidatures", "reglages"]) $("#vue-" + v).hidden = v !== nom;
  $$(".onglet").forEach((o) => o.classList.toggle("actif", o.dataset.vue === nom));
  if (nom === "favoris") dessinerFavoris();
  if (nom === "candidatures") dessinerCandidatures();
  if (nom === "reglages" && !etat.reglagesModifies) dessinerReglages();
  window.scrollTo(0, 0);
}
$$(".onglet").forEach((o) => o.addEventListener("click", () => montrerVue(o.dataset.vue)));

/* ════════════════════════════════════════════════════════════════
   Secteurs et plan de lecture des sites
   ════════════════════════════════════════════════════════════════ */
function dessinerSecteurs() {
  const zone = $("#secteurs");
  const puces = [{ nom: "", libelle: "Tous" }, ...etat.profil.secteurs.map((s) => ({ nom: s.nom, libelle: s.nom }))];
  zone.innerHTML = puces.map((p) =>
    `<button class="secteur ${p.nom === etat.secteur ? "actif" : ""}" data-secteur="${echappe(p.nom)}" type="button" aria-pressed="${p.nom === etat.secteur}">${echappe(p.libelle)}</button>`
  ).join("");
  $$(".secteur", zone).forEach((b) => b.addEventListener("click", () => {
    if (b.dataset.secteur === etat.secteur) return;
    etat.secteur = b.dataset.secteur;
    localStorage.setItem(`vigie-secteur-${etat.user.uid}`, etat.secteur);
    dessinerSecteurs();
    chargerCache();
    dessinerOffres();
    actualiser();
  }));
}

function planDeLecture() {
  const secteurs = etat.secteur
    ? etat.profil.secteurs.filter((s) => s.nom === etat.secteur)
    : etat.profil.secteurs;
  const eteints = new Set(etat.profil.sources_off || []);
  const plan = new Map();
  for (const s of secteurs) {
    for (const c of Object.values(etat.catalogue)) {
      if (!(s.groupes || []).includes(c.groupe) || eteints.has(c.id)) continue;
      if (!plan.has(c.id)) plan.set(c.id, new Set());
      if (c.mots) (s.mots || []).forEach((m) => plan.get(c.id).add(m));
    }
  }
  return [...plan].map(([id, mots]) => ({ id, mots: [...mots].slice(0, 12) }));
}

/* ════════════════════════════════════════════════════════════════
   Cache local : l'écran se remplit immédiatement, même sans réseau
   ════════════════════════════════════════════════════════════════ */
const cleCache = () => `vigie-cache-${etat.user.uid}-${etat.secteur || "*"}`;

function chargerCache() {
  etat.parSource = new Map();
  etat.etats = {};
  etat.derniereMaj = null;
  try {
    const c = JSON.parse(localStorage.getItem(cleCache()) || "null");
    if (c) {
      const prevus = new Set(planDeLecture().map((t) => t.id));
      etat.parSource = new Map(c.parSource.filter(([id]) => prevus.has(id)));
      etat.etats = c.etats || {};
      etat.derniereMaj = c.t;
    }
  } catch { /* cache illisible : ignoré */ }
  majStatut();
}

function sauverCache() {
  try {
    localStorage.setItem(cleCache(), JSON.stringify({ t: etat.derniereMaj, parSource: [...etat.parSource], etats: etat.etats }));
  } catch { /* stockage plein : sans conséquence */ }
}

/* ════════════════════════════════════════════════════════════════
   Actualisation en temps réel : un appel au relais par site, en parallèle
   ════════════════════════════════════════════════════════════════ */
async function lireSite(tache, jeton, signalGlobal) {
  const ctrl = new AbortController();
  const arret = () => ctrl.abort();
  signalGlobal.addEventListener("abort", arret);
  const minuteur = setTimeout(arret, DELAI_SITE);
  try {
    const r = await fetch("/api/relais", {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${jeton}` },
      body: JSON.stringify({ source: tache.id, mots: tache.mots }),
      signal: ctrl.signal,
    });
    const d = await r.json().catch(() => ({ etat: "erreur", offres: [], detail: `réponse illisible (HTTP ${r.status})` }));
    if (r.status === 401) d.expire = true;
    if (r.status === 403) d.refuse = true;
    return d;
  } catch (e) {
    if (signalGlobal.aborted) throw e;
    return { etat: "erreur", offres: [], detail: navigator.onLine ? "le site n'a pas répondu à temps" : "pas de réseau" };
  } finally {
    clearTimeout(minuteur);
    signalGlobal.removeEventListener("abort", arret);
  }
}

let renduPrevu = false;
function planifierRendu() {
  if (renduPrevu) return;
  renduPrevu = true;
  requestAnimationFrame(() => { renduPrevu = false; dessinerOffres(); });
}

async function actualiser() {
  if (!etat.profil || !etat.user) return;
  etat.enCours?.abort();
  const ctrl = new AbortController();
  etat.enCours = ctrl;
  const plan = planDeLecture();
  const prevus = new Set(plan.map((t) => t.id));
  for (const id of [...etat.parSource.keys()]) if (!prevus.has(id)) etat.parSource.delete(id);
  etat.etats = {};
  etat.attendus = plan.length;
  etat.recus = 0;
  majStatut();
  if (!plan.length) {
    etat.enCours = null;
    majStatut();
    dessinerOffres();
    return;
  }

  let jeton;
  try {
    jeton = await FB.jeton();
  } catch {
    etat.enCours = null;
    majStatut();
    toast(navigator.onLine ? "Session expirée : reconnectez-vous." : "Pas de réseau : offres de la dernière actualisation.");
    return;
  }

  let sessionExpiree = false;
  let compteRefuse = false;
  await Promise.all(plan.map(async (tache) => {
    let d;
    try {
      d = await lireSite(tache, jeton, ctrl.signal);
    } catch {
      return; // actualisation remplacée par une plus récente
    }
    if (ctrl.signal.aborted) return;
    if (d.expire) sessionExpiree = true;
    if (d.refuse) compteRefuse = true;
    etat.etats[tache.id] = { etat: d.etat, detail: d.detail || "", n: (d.offres || []).length };
    if (d.etat === "ok") etat.parSource.set(tache.id, d.offres || []);
    etat.recus++;
    majStatut();
    planifierRendu();
  }));
  if (ctrl.signal.aborted) return;

  etat.enCours = null;
  const reussites = Object.values(etat.etats).filter((e) => e.etat === "ok").length;
  if (reussites) {
    etat.derniereMaj = Date.now();
    sauverCache();
  } else if (Object.values(etat.etats).some((e) => e.etat === "erreur")) {
    // aucun site n'a répondu : réseau absent ou trop faible (métro, tunnel)
    toast(etat.parSource.size
      ? "Aucun site n'a répondu : réseau trop faible. Offres de la dernière actualisation affichées."
      : "Aucun site n'a répondu : vérifiez votre connexion, puis actualisez.");
  }
  if (compteRefuse) toast("Ce compte n'est pas autorisé sur le relais : ajoutez son e-mail à EMAILS_AUTORISES dans Vercel.");
  else if (sessionExpiree) toast("Session expirée : déconnectez-vous puis reconnectez-vous.");
  dessinerOffres();
  enregistrerVues();
  etat.vuesVides = false;
  majStatut();
}

function enregistrerVues() {
  if (!etat.vuesModifiees) return;
  etat.vuesModifiees = false;
  let ids = etat.vues;
  const cles = Object.keys(ids);
  if (cles.length > 6000) {
    // on garde les 5000 plus récentes pour rester léger
    ids = Object.fromEntries(cles.sort((a, b) => ids[b] - ids[a]).slice(0, 5000).map((k) => [k, ids[k]]));
    etat.vues = ids;
  }
  FB.ecrireVues(etat.user.uid, ids);
}

$("#btn-actualiser").addEventListener("click", () => actualiser());
document.addEventListener("visibilitychange", () => {
  if (document.visibilityState !== "visible" || !etat.profil || etat.enCours) return;
  if (!etat.derniereMaj || Date.now() - etat.derniereMaj > REACTUALISER_APRES) actualiser();
});
setInterval(() => { if (!etat.enCours) majStatut(); }, 30000);

function majStatut() {
  if (!etat.profil) return;
  const enCours = !!etat.enCours;
  $("#btn-actualiser").classList.toggle("tourne", enCours);
  $("#btn-actualiser").setAttribute("aria-busy", String(enCours));
  const barre = $("#progression span");
  if (enCours) {
    barre.style.opacity = "1";
    barre.style.width = `${etat.attendus ? Math.max(6, (etat.recus / etat.attendus) * 100) : 6}%`;
    $("#statut-maj").textContent = `Lecture des sites : ${etat.recus} sur ${etat.attendus}`;
  } else {
    barre.style.width = etat.attendus ? "100%" : "0%";
    barre.style.opacity = "0";
    $("#statut-maj").textContent = etat.derniereMaj ? `Actualisé ${depuisMinutes(etat.derniereMaj)}` : "";
  }
  dessinerEtatsSites();
}

/* ════════════════════════════════════════════════════════════════
   État des sites
   ════════════════════════════════════════════════════════════════ */
function dessinerEtatsSites() {
  const bouton = $("#etat-sites");
  const liste = Object.entries(etat.etats);
  if (!liste.length || etat.enCours) { bouton.hidden = true; $("#liste-etats").hidden = true; return; }
  const sansCle = liste.filter(([, e]) => e.etat === "cle_manquante").length;
  const interroges = liste.length - sansCle;
  const enPanne = liste.filter(([, e]) => e.etat === "erreur").length;
  const repondu = interroges - enPanne;
  let texte =
    repondu === 0 ? "Aucun site n'a répondu" :
    repondu === interroges ? (interroges > 1 ? `Les ${interroges} sites ont répondu` : "Le site a répondu") :
    `${repondu} site${repondu > 1 ? "s" : ""} sur ${interroges} ${repondu > 1 ? "ont" : "a"} répondu`;
  if (enPanne) texte += `, <span class="souci">${enPanne} indisponible${enPanne > 1 ? "s" : ""}</span>`;
  if (sansCle) texte += `. ${sansCle} sans clé`;
  bouton.innerHTML = texte;
  bouton.hidden = false;
  const ouvert = bouton.getAttribute("aria-expanded") === "true";
  const zone = $("#liste-etats");
  zone.hidden = !ouvert;
  if (!ouvert) return;
  const libelle = { ok: "", erreur: "indisponible", cle_manquante: "clé à ajouter" };
  zone.innerHTML = liste
    .sort(([, a], [, b]) => (a.etat === "erreur" ? -1 : 0) - (b.etat === "erreur" ? -1 : 0))
    .map(([id, e]) => {
      const nom = etat.catalogue[id]?.nom || id;
      const suffixe = e.etat === "ok" ? `${e.n}` : libelle[e.etat] || e.etat;
      return `<button class="etat ${e.etat}" type="button" data-detail="${echappe(e.detail)}">${echappe(nom)} : ${echappe(suffixe)}</button>`;
    }).join("");
  $$(".etat", zone).forEach((b) => b.addEventListener("click", () => {
    if (b.dataset.detail) toast(b.dataset.detail);
  }));
}
$("#etat-sites").addEventListener("click", (e) => {
  const b = e.currentTarget;
  b.setAttribute("aria-expanded", String(b.getAttribute("aria-expanded") !== "true"));
  dessinerEtatsSites();
});

/* ════════════════════════════════════════════════════════════════
   Offres
   ════════════════════════════════════════════════════════════════ */
function offresFusionnees() {
  const uniques = new Map();
  for (const liste of etat.parSource.values()) {
    for (const o of liste) {
      const cle = normaliser(o.titre) + "|" + normaliser(o.entreprise);
      if (!uniques.has(cle)) uniques.set(cle, o);
    }
  }
  const maintenant = Date.now();
  return [...uniques.values()].map((o) => {
    const h = hachage(o.id);
    if (!(h in etat.vues)) {
      // 1 = offre déjà en ligne lors du tout premier usage : jamais marquée « Nouveau »
      etat.vues[h] = etat.vuesVides ? 1 : maintenant;
      etat.vuesModifiees = true;
    }
    const vu = etat.vues[h];
    const publiee = o.date ? Date.parse(o.date) : NaN;
    return { ...o, h, vu, nouveau: vu > maintenant - JOUR, tri: Number.isFinite(publiee) ? publiee : vu };
  }).sort((a, b) => b.tri - a.tri);
}

function filtres() {
  const f = etat.profil?.filtres || {};
  return { contrats: new Set(f.contrats || []), sources: new Set(f.sources || []) };
}

function railDate(o) {
  const publiee = o.date ? Date.parse(o.date) : NaN;
  const rail = (classe, jour, mois, legende) =>
    `<div class="rail ${classe}"><span class="rail-jour">${jour}</span><span class="rail-mois">${mois}</span>${legende ? `<span class="rail-rel">${legende}</span>` : ""}</div>`;
  const mois = (d) => d.toLocaleDateString("fr-FR", { month: "short" });
  if (Number.isFinite(publiee)) {
    const d = new Date(publiee);
    return rail("", d.getDate(), mois(d), "");
  }
  if (o.vu > 1) {
    const d = new Date(o.vu);
    return rail("rail-vue", d.getDate(), mois(d), "repérée");
  }
  return rail("rail-vue", "—", "", "sans date");
}

function carteOffre(o) {
  const fav = etat.favoris.has(o.h);
  const cand = etat.candidatures.get(o.h);
  const contrat = o.contrat ? CONTRATS[categorieContrat(o.contrat)] : "";
  etat.index.set(o.h, o);
  return `
  <article class="offre">
    <a class="offre-lien" href="${echappe(o.url)}" target="_blank" rel="noopener">
      ${railDate(o)}
      <div class="offre-corps">
        <h3 class="offre-titre">${echappe(o.titre)}</h3>
        <p class="offre-entreprise">${echappe(o.entreprise)}</p>
        <p class="offre-meta">
          <span>${echappe(o.lieu)}</span>
          ${contrat && contrat !== CONTRATS.autre ? `<span class="offre-contrat">${echappe(contrat)}</span>` : ""}
          ${o.source && o.source !== "Site carrière" ? `<span>via ${echappe(o.source)}</span>` : ""}
        </p>
        ${o.nouveau || cand ? `<p class="drapeaux">
          ${o.nouveau ? `<span class="drapeau-nouveau">Nouveau</span>` : ""}
          ${cand ? `<span class="drapeau-suivi">${echappe(STATUTS[cand.statut] || cand.statut)}</span>` : ""}
        </p>` : ""}
      </div>
    </a>
    <div class="offre-actions">
      <button class="btn-favori ${fav ? "actif" : ""}" data-h="${o.h}" type="button" aria-pressed="${fav}" aria-label="${fav ? "Retirer des favoris" : "Ajouter aux favoris"}">
        <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3.5l2.6 5.3 5.8.8-4.2 4.1 1 5.8L12 16.8l-5.2 2.7 1-5.8-4.2-4.1 5.8-.8z"/></svg>
      </button>
      <button class="btn-suivre ${cand ? "actif" : ""}" data-h="${o.h}" type="button">${cand ? "Suivie" : "Suivre"}</button>
    </div>
  </article>`;
}

function dessinerOffres() {
  if (!etat.profil) return;
  const zone = $("#liste-offres");
  const toutes = offresFusionnees();
  const { contrats, sources } = filtres();
  const texte = normaliser($("#filtre-texte").value);
  const apresFiltres = toutes.filter((o) => !contrats.has(categorieContrat(o.contrat)) && !sources.has(o.source));
  const visibles = apresFiltres.filter((o) => !texte || normaliser(`${o.titre} ${o.entreprise} ${o.lieu}`).includes(texte));
  etat.derniereListe = toutes;
  dessinerFiltres(toutes);

  if (!visibles.length) {
    const aucunSite = !planDeLecture().length;
    zone.innerHTML =
      etat.enCours && !toutes.length ? '<div class="squelette"></div>'.repeat(4) :
      aucunSite ? `<div class="vide"><p class="vide-titre">Aucun site actif pour ce secteur</p><p>Activez des sites ou des familles de sites dans Réglages.</p></div>` :
      toutes.length && apresFiltres.length === 0 ? `<div class="vide"><p class="vide-titre">Vos filtres masquent les ${toutes.length} offres</p><p>Ouvrez Filtres et touchez une étiquette barrée pour la réafficher.</p></div>` :
      toutes.length ? `<div class="vide"><p class="vide-titre">Aucune offre ne correspond à « ${echappe($("#filtre-texte").value)} »</p><p>Essayez un autre mot, ou videz le champ de recherche.</p></div>` :
      `<div class="vide"><p class="vide-titre">Aucune offre pour le moment</p><p>Actualisez plus tard, ou élargissez vos mots-clés dans Réglages.</p></div>`;
    return;
  }
  etat.index = new Map();
  const masquees = toutes.length - apresFiltres.length;
  zone.innerHTML = visibles.map(carteOffre).join("") +
    (masquees ? `<p class="aide">${masquees} offre${masquees > 1 ? "s masquées" : " masquée"} par vos filtres.</p>` : "");
}

$("#filtre-texte").addEventListener("input", () => dessinerOffres());

// boutons des cartes (offres et favoris)
document.addEventListener("click", (e) => {
  const fav = e.target.closest(".btn-favori");
  const suivre = e.target.closest(".btn-suivre");
  if (!fav && !suivre) return;
  const h = (fav || suivre).dataset.h;
  const o = etat.index.get(h) || etat.favoris.get(h)?.offre;
  if (!o) return;
  if (fav) basculerFavori(h, o);
  else suivreOffre(h, o);
});

function offreMinimale(o) {
  return { id: o.id, titre: o.titre, entreprise: o.entreprise, lieu: o.lieu, url: o.url, source: o.source, date: o.date || null, contrat: o.contrat || "" };
}

function basculerFavori(h, o) {
  const uid = etat.user.uid;
  if (etat.favoris.has(h)) {
    FB.supprimerDoc(uid, "favoris", h);
    toast("Retirée des favoris.");
  } else {
    FB.ecrireDoc(uid, "favoris", h, { offre: offreMinimale(o), ajoute_le: new Date().toISOString() });
    toast("Ajoutée aux favoris.");
  }
}

function suivreOffre(h, o) {
  if (etat.candidatures.has(h)) { montrerVue("candidatures"); return; }
  const maintenant = new Date().toISOString();
  FB.ecrireDoc(etat.user.uid, "candidatures", h, {
    offre: offreMinimale(o), statut: "a_postuler", note: "",
    creee_le: maintenant, maj_le: maintenant, historique: [{ statut: "a_postuler", date: maintenant }],
  });
  toast("Ajoutée à vos candidatures, statut « À postuler ».");
}

/* ════════════════════════════════════════════════════════════════
   Filtres : type de contrat et provenance
   ════════════════════════════════════════════════════════════════ */
function dessinerFiltres(toutes = etat.derniereListe || []) {
  if (!etat.profil) return;
  const { contrats, sources } = filtres();
  const parContrat = {}, parSource = {};
  for (const o of toutes) {
    const c = categorieContrat(o.contrat);
    parContrat[c] = (parContrat[c] || 0) + 1;
    parSource[o.source] = (parSource[o.source] || 0) + 1;
  }
  // une étiquette masquée reste visible même si aucune offre ne la porte en ce moment
  contrats.forEach((c) => { parContrat[c] ??= 0; });
  sources.forEach((s) => { parSource[s] ??= 0; });

  const puce = (attr, valeur, libelle, n, exclue) =>
    `<button class="puce ${exclue ? "exclue" : ""}" type="button" ${attr}="${echappe(valeur)}" aria-pressed="${!exclue}">${echappe(libelle)}<span class="nb">${n}</span></button>`;
  $("#filtres-contrat").innerHTML = Object.keys(CONTRATS).filter((c) => c in parContrat)
    .map((c) => puce("data-contrat", c, CONTRATS[c], parContrat[c], contrats.has(c))).join("") || '<span class="aide">Aucune offre affichée.</span>';
  $("#filtres-sources").innerHTML = Object.keys(parSource).sort()
    .map((s) => puce("data-source", s, s, parSource[s], sources.has(s))).join("") || '<span class="aide">Aucune offre affichée.</span>';

  const nb = contrats.size + sources.size;
  $("#nb-filtres").textContent = nb;
  $("#nb-filtres").hidden = !nb;
}

$("#btn-filtres").addEventListener("click", (e) => {
  const ouvert = e.currentTarget.getAttribute("aria-expanded") !== "true";
  e.currentTarget.setAttribute("aria-expanded", String(ouvert));
  $("#panneau-filtres").hidden = !ouvert;
});

$("#panneau-filtres").addEventListener("click", (e) => {
  const b = e.target.closest(".puce");
  if (!b) return;
  const f = filtres();
  const [ensemble, valeur] = b.dataset.contrat !== undefined ? [f.contrats, b.dataset.contrat] : [f.sources, b.dataset.source];
  ensemble.has(valeur) ? ensemble.delete(valeur) : ensemble.add(valeur);
  const nouveaux = { contrats: [...f.contrats], sources: [...f.sources] };
  etat.profil.filtres = nouveaux;
  etat.profilJson = JSON.stringify(etat.profil);
  FB.ecrireProfil(etat.user.uid, { filtres: nouveaux });
  dessinerOffres();
});

/* ════════════════════════════════════════════════════════════════
   Liens directs vers les sites
   ════════════════════════════════════════════════════════════════ */
function dessinerLiensDirects() {
  const groupes = GROUPES_PROFIL[etat.profil.profil] || [];
  const eteints = new Set(etat.profil.sources_off || []);
  const liens = Object.values(etat.catalogue).filter((c) => c.lien && groupes.includes(c.groupe) && !eteints.has(c.id));
  $("#liens-directs").hidden = !liens.length;
  $("#liens-directs-liste").innerHTML = liens.map((c) =>
    `<a href="${echappe(c.lien)}" target="_blank" rel="noopener">${echappe(c.nom)}</a>`).join("");
}

/* ════════════════════════════════════════════════════════════════
   Favoris
   ════════════════════════════════════════════════════════════════ */
function dessinerFavoris() {
  const zone = $("#liste-favoris");
  const favoris = [...etat.favoris.entries()]
    .sort(([, a], [, b]) => String(b.ajoute_le).localeCompare(String(a.ajoute_le)));
  if (!favoris.length) {
    zone.innerHTML = `<div class="vide"><p class="vide-titre">Aucun favori pour le moment</p><p>Touchez l'étoile d'une offre pour la garder ici, même après sa disparition des résultats.</p></div>`;
    return;
  }
  zone.innerHTML = favoris.map(([h, f]) => carteOffre({ ...f.offre, h, vu: etat.vues[h] || 1, nouveau: false })).join("");
}

/* ════════════════════════════════════════════════════════════════
   Candidatures
   ════════════════════════════════════════════════════════════════ */
function majPastille() {
  const enCours = [...etat.candidatures.values()].filter((c) => !["acceptee", "refusee"].includes(c.statut)).length;
  $("#pastille-candidatures").textContent = enCours;
  $("#pastille-candidatures").hidden = !enCours;
}

function dessinerCandidatures() {
  if (document.activeElement?.classList.contains("cand-note")) {
    etat.renduCandidaturesEnAttente = true; // on ne coupe pas une saisie en cours
    return;
  }
  etat.renduCandidaturesEnAttente = false;
  const zone = $("#liste-candidatures");
  if (!etat.candidatures.size) {
    zone.innerHTML = `<div class="vide"><p class="vide-titre">Aucune candidature suivie</p><p>Touchez « Suivre » sous une offre qui vous intéresse. Vous noterez ici où vous en êtes, et Vigie vous signalera les candidatures à relancer.</p></div>`;
    return;
  }
  const html = [];
  for (const [statut, libelle] of Object.entries(STATUTS)) {
    const groupe = [...etat.candidatures.entries()]
      .filter(([, c]) => c.statut === statut)
      .sort(([, a], [, b]) => String(b.maj_le).localeCompare(String(a.maj_le)));
    if (!groupe.length) continue;
    html.push(`<h2 class="groupe-titre">${libelle} <span class="nb">${groupe.length}</span></h2>`);
    for (const [h, c] of groupe) {
      const o = c.offre || {};
      const maj = Date.parse(c.maj_le);
      const jours = Number.isFinite(maj) ? joursDepuis(maj) : 0;
      const aRelancer = ["postulee", "relance"].includes(statut) && jours >= JOURS_AVANT_RELANCE;
      const options = Object.entries(STATUTS).map(([s, l]) => `<option value="${s}" ${s === c.statut ? "selected" : ""}>${l}</option>`).join("");
      html.push(`
      <article class="candidature ${aRelancer ? "a-relancer" : ""}" data-h="${h}">
        <a class="cand-titre" href="${echappe(o.url)}" target="_blank" rel="noopener">${echappe(o.titre)}</a>
        <p class="cand-entreprise">${echappe(o.entreprise)}</p>
        <p class="cand-date">${libelle} ${Number.isFinite(maj) ? relatif(maj) : ""}, ${echappe(o.lieu)}</p>
        ${aRelancer ? `<span class="badge-relance">Sans nouvelles depuis ${jours} jours : à relancer ?</span>` : ""}
        <div class="cand-controles">
          <select class="cand-statut" aria-label="Statut de la candidature">${options}</select>
          <button class="cand-retirer" type="button" aria-label="Retirer du suivi">×</button>
        </div>
        <textarea class="cand-note" rows="2" placeholder="Note : contact, référence, suite de l'entretien…">${echappe(c.note || "")}</textarea>
      </article>`);
    }
  }
  zone.innerHTML = html.join("");
}

$("#liste-candidatures").addEventListener("change", (e) => {
  const carte = e.target.closest(".candidature");
  if (!carte) return;
  const h = carte.dataset.h;
  const c = etat.candidatures.get(h);
  if (!c) return;
  if (e.target.classList.contains("cand-statut")) {
    const statut = e.target.value;
    if (statut === c.statut) return;
    const maintenant = new Date().toISOString();
    FB.ecrireDoc(etat.user.uid, "candidatures", h, {
      statut, maj_le: maintenant, historique: [...(c.historique || []), { statut, date: maintenant }],
    });
    toast(`Statut passé à « ${STATUTS[statut]} ».`);
  }
  if (e.target.classList.contains("cand-note") && e.target.value !== (c.note || "")) {
    FB.ecrireDoc(etat.user.uid, "candidatures", h, { note: e.target.value });
  }
});
$("#liste-candidatures").addEventListener("focusout", (e) => {
  if (!e.target.classList.contains("cand-note")) return;
  setTimeout(() => { if (etat.renduCandidaturesEnAttente) dessinerCandidatures(); }, 0);
});
$("#liste-candidatures").addEventListener("click", (e) => {
  const b = e.target.closest(".cand-retirer");
  if (!b) return;
  const h = b.closest(".candidature").dataset.h;
  if (confirm("Retirer cette candidature du suivi ? Sa note sera effacée.")) {
    FB.supprimerDoc(etat.user.uid, "candidatures", h);
    toast("Candidature retirée du suivi.");
  }
});

/* ════════════════════════════════════════════════════════════════
   Réglages
   ════════════════════════════════════════════════════════════════ */
function dessinerReglages() {
  etat.reglagesModifies = false;
  const groupesDispo = GROUPES_PROFIL[etat.profil.profil] || [];
  const noms = etat.config.groupes || {};
  $("#editeur-secteurs").innerHTML = etat.profil.secteurs.map((s) => blocSecteur(s, groupesDispo, noms)).join("");

  const eteints = new Set(etat.profil.sources_off || []);
  $("#editeur-sites").innerHTML = groupesDispo.map((g) => {
    const sites = Object.values(etat.catalogue).filter((c) => c.groupe === g);
    if (!sites.length) return "";
    return `<p class="famille-sites">${echappe(noms[g] || g)}</p><div>` + sites.map((c) => `
      <label class="site-ligne">
        <span>${echappe(c.nom)}
          <span class="note">${c.cle_manquante ? "Clé à ajouter dans Vercel (voir le guide)" : c.mots ? "Recherche par vos mots-clés" : "Toutes ses offres à Paris"}</span>
        </span>
        <input class="interrupteur" type="checkbox" data-site="${c.id}" ${eteints.has(c.id) ? "" : "checked"}>
      </label>`).join("") + "</div>";
  }).join("");
}

function blocSecteur(s, groupesDispo, noms) {
  return `
  <div class="bloc-secteur">
    <div class="bloc-entete">
      <input type="text" class="secteur-nom" value="${echappe(s.nom)}" placeholder="Nom du secteur" aria-label="Nom du secteur">
      <button class="cand-retirer secteur-retirer" type="button" aria-label="Supprimer ce secteur">×</button>
    </div>
    <textarea class="secteur-mots" placeholder="mots-clés séparés par des virgules" aria-label="Mots-clés">${echappe((s.mots || []).join(", "))}</textarea>
    <div class="groupes-secteur">
      ${groupesDispo.map((g) => `<label class="case"><input type="checkbox" value="${g}" ${(s.groupes || []).includes(g) ? "checked" : ""}> ${echappe(noms[g] || g)}</label>`).join("")}
    </div>
  </div>`;
}

$("#editeur-secteurs").addEventListener("input", () => { etat.reglagesModifies = true; });
$("#editeur-secteurs").addEventListener("change", () => { etat.reglagesModifies = true; });
$("#editeur-secteurs").addEventListener("click", (e) => {
  if (!e.target.closest(".secteur-retirer")) return;
  e.target.closest(".bloc-secteur").remove();
  etat.reglagesModifies = true;
});
$("#btn-ajout-secteur").addEventListener("click", () => {
  const groupesDispo = GROUPES_PROFIL[etat.profil.profil] || [];
  $("#editeur-secteurs").insertAdjacentHTML("beforeend",
    blocSecteur({ nom: "", mots: [], groupes: [groupesDispo[0]] }, groupesDispo, etat.config.groupes || {}));
  etat.reglagesModifies = true;
  $("#editeur-secteurs .bloc-secteur:last-child .secteur-nom").focus();
});

$("#btn-enregistrer-secteurs").addEventListener("click", () => {
  const secteurs = [];
  const noms = new Set();
  for (const bloc of $$("#editeur-secteurs .bloc-secteur")) {
    const nom = $(".secteur-nom", bloc).value.trim();
    const mots = $(".secteur-mots", bloc).value.split(",").map((m) => m.trim()).filter(Boolean);
    const groupes = $$(".groupes-secteur input:checked", bloc).map((c) => c.value);
    if (!nom && !mots.length) continue;
    if (!nom) return toast("Donnez un nom à chaque secteur.");
    if (noms.has(nom)) return toast(`Deux secteurs portent le nom « ${nom} ».`);
    if (!groupes.length) return toast(`Cochez au moins une famille de sites pour « ${nom} ».`);
    noms.add(nom);
    secteurs.push({ nom, mots, groupes });
  }
  if (!secteurs.length) return toast("Gardez au moins un secteur.");
  etat.profil.secteurs = secteurs;
  etat.profilJson = JSON.stringify(etat.profil);
  FB.ecrireProfil(etat.user.uid, { secteurs });
  etat.reglagesModifies = false;
  if (!secteurs.some((s) => s.nom === etat.secteur)) etat.secteur = "";
  dessinerSecteurs();
  toast("Secteurs enregistrés.");
  chargerCache();
  actualiser();
});

$("#editeur-sites").addEventListener("change", (e) => {
  const c = e.target.closest("[data-site]");
  if (!c) return;
  const eteints = new Set(etat.profil.sources_off || []);
  c.checked ? eteints.delete(c.dataset.site) : eteints.add(c.dataset.site);
  etat.profil.sources_off = [...eteints];
  etat.profilJson = JSON.stringify(etat.profil);
  FB.ecrireProfil(etat.user.uid, { sources_off: etat.profil.sources_off });
  dessinerLiensDirects();
  toast(`${etat.catalogue[c.dataset.site]?.nom} ${c.checked ? "activé" : "désactivé"}.`);
});

$("#btn-deconnexion").addEventListener("click", () => {
  if (confirm("Se déconnecter de Vigie sur ce téléphone ?")) FB.deconnecter();
});

$("#btn-changer-profil").addEventListener("click", () => {
  const autre = etat.profil.profil === "droit" ? "tech" : "droit";
  const d = DEFAUTS[autre];
  if (!confirm(`Passer au domaine « ${d.nom} » ? Vos secteurs seront remplacés par ceux de ce domaine. Favoris et candidatures sont conservés.`)) return;
  FB.ecrireProfil(etat.user.uid, { profil: autre, nom: d.nom, secteurs: d.secteurs, sources_off: [], filtres: { contrats: [], sources: [] } });
});

/* ════════════════════════════════════════════════════════════════
   Lancement
   ════════════════════════════════════════════════════════════════ */
if ("serviceWorker" in navigator) {
  navigator.serviceWorker.register("/sw.js").catch(() => {});
}
demarrer();
