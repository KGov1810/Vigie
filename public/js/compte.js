// Démarrage, connexion, choix du domaine au premier lancement.
import * as FB from "../firebase.js";
import { actualiser, chargerCache } from "./actualisation.js";
import { dessinerCandidatures, majPastille } from "./candidatures.js";
import { DEFAUTS } from "./constantes.js";
import { etat } from "./etat.js";
import { dessinerFavoris } from "./favoris.js";
import { montrerVue } from "./navigation.js";
import { dessinerFiltres, dessinerLiensDirects, dessinerOffres, dessinerSecteurs } from "./offres.js";
import { $, $$, afficherEcran, echappe, erreur, toast } from "./outils.js";
import { dessinerReglages } from "./reglages.js";

/* ════════════════════════════════════════════════════════════════
   Démarrage
   ════════════════════════════════════════════════════════════════ */
export async function demarrer() {
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
