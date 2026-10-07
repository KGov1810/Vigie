// Petits outils : sélecteurs, échappement, normalisation, hachage, dates, message éphémère, écrans.
import { JOUR } from "./constantes.js";

/* ════════════════════════════════════════════════════════════════
   Utilitaires
   ════════════════════════════════════════════════════════════════ */
export const $ = (s, r = document) => r.querySelector(s);

export const $$ = (s, r = document) => [...r.querySelectorAll(s)];

export function echappe(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

export function normaliser(s) {
  return String(s || "").toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "").replace(/[^a-z0-9+#]+/g, " ").trim();
}

// identifiant court et sûr pour Firestore (les identifiants d'offres contiennent « / », « : »…)
export function hachage(str) {
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

export function categorieContrat(brut) {
  const t = normaliser(brut);
  if (!t) return "autre";
  if (/alternance|apprenti|professionnalisation|apprenticeship|work study/.test(t)) return "alternance";
  if (/stage|intern/.test(t)) return "stage";
  if (/indetermin|\bcdi\b|permanent/.test(t)) return "cdi";
  if (/\bcdd\b|temporaire|temporary|interim|saisonnier|determin|fixed|contractor|\bmis\b|\bsai\b|\bvie\b|freelance/.test(t)) return "cdd";
  if (/full time|collaboration|temps plein/.test(t)) return "cdi";
  return "autre";
}

export function joursDepuis(ms) {
  const debut = new Date(); debut.setHours(0, 0, 0, 0);
  const d = new Date(ms); d.setHours(0, 0, 0, 0);
  return Math.round((debut - d) / JOUR);
}

export function relatif(ms) {
  const j = joursDepuis(ms);
  if (j <= 0) return "aujourd'hui";
  if (j === 1) return "hier";
  if (j < 30) return `il y a ${j} j`;
  const m = Math.round(j / 30);
  return `il y a ${m} mois`;
}

export function depuisMinutes(ms) {
  const min = Math.round((Date.now() - ms) / 60000);
  if (min < 1) return "à l'instant";
  if (min < 60) return `il y a ${min} min`;
  const h = Math.floor(min / 60);
  if (h < 24) return `il y a ${h} h`;
  return relatif(ms);
}

let minuteurToast;

export function toast(message) {
  const t = $("#toast");
  t.textContent = message;
  t.hidden = false;
  clearTimeout(minuteurToast);
  minuteurToast = setTimeout(() => { t.hidden = true; }, 3800);
}

export function afficherEcran(nom) {
  for (const id of ["demarrage", "ecran-erreur", "ecran-connexion", "ecran-profil", "app"]) {
    $("#" + id).hidden = id !== nom;
  }
}

export function erreur(titre, html) {
  $("#erreur-titre").textContent = titre;
  $("#erreur-texte").innerHTML = html;
  afficherEcran("ecran-erreur");
}
