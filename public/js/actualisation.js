// Lecture des sites en temps réel (un appel au relais par site, en parallèle), cache local, état des sites.
import * as FB from "../firebase.js";
import { DELAI_SITE, REACTUALISER_APRES } from "./constantes.js";
import { etat } from "./etat.js";
import { dessinerOffres } from "./offres.js";
import { $, $$, depuisMinutes, echappe, toast } from "./outils.js";

export function planDeLecture() {
  const secteurs = etat.secteur
    ? etat.profil.secteurs.filter((s) => s.nom === etat.secteur)
    : etat.profil.secteurs;
  const eteints = new Set(etat.profil.sources_off || []);
  const plan = new Map();
  for (const s of secteurs) {
    for (const c of Object.values(etat.catalogue)) {
      if (!(s.groupes || []).includes(c.groupe) || eteints.has(c.id) || c.lien_seul) continue;
      if (!plan.has(c.id)) plan.set(c.id, new Set());
      (s.mots || []).forEach((m) => plan.get(c.id).add(m));
    }
  }
  return [...plan].map(([id, mots]) => ({ id, mots: [...mots].slice(0, 12) }));
}

/* ════════════════════════════════════════════════════════════════
   Cache local : l'écran se remplit immédiatement, même sans réseau
   ════════════════════════════════════════════════════════════════ */
const cleCache = () => `vigie-cache-${etat.user.uid}-${etat.secteur || "*"}`;

export function chargerCache() {
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

export async function actualiser() {
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
  const tries = liste.sort(([, a], [, b]) => (a.etat === "erreur" ? -1 : 0) - (b.etat === "erreur" ? -1 : 0));
  zone.innerHTML =
    tries.map(([id, e]) => {
      const c = etat.catalogue[id] || {};
      const suffixe = e.etat === "ok" ? `${e.n}` : libelle[e.etat] || e.etat;
      return `<button class="etat ${e.etat}" type="button" data-site="${echappe(id)}" data-detail="${echappe(e.detail)}"${c.lien ? ` aria-label="Ouvrir le site ${echappe(c.nom || id)}"` : ""}>${echappe(c.nom || id)} : ${echappe(suffixe)}${c.lien ? " ↗" : ""}</button>`;
    }).join("") +
    `<p class="aide">Touchez un site pour ouvrir sa page avec vos filtres.</p>` +
    tries.filter(([, e]) => e.etat === "erreur" && e.detail)
      .map(([id, e]) => `<p class="aide"><strong>${echappe(etat.catalogue[id]?.nom || id)}</strong> : ${echappe(e.detail)}</p>`).join("");
  $$(".etat", zone).forEach((b) => b.addEventListener("click", () => {
    const lien = etat.catalogue[b.dataset.site]?.lien;
    if (lien) window.open(lien, "_blank", "noopener");
    else if (b.dataset.detail) toast(b.dataset.detail);
  }));
}

$("#etat-sites").addEventListener("click", (e) => {
  const b = e.currentTarget;
  b.setAttribute("aria-expanded", String(b.getAttribute("aria-expanded") !== "true"));
  dessinerEtatsSites();
});
