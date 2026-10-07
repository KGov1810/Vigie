// Onglet Réglages : secteurs, sites interrogés, compte.
import * as FB from "../firebase.js";
import { actualiser, chargerCache } from "./actualisation.js";
import { DEFAUTS, GROUPES_PROFIL } from "./constantes.js";
import { etat } from "./etat.js";
import { dessinerLiensDirects, dessinerSecteurs } from "./offres.js";
import { $, $$, echappe, toast } from "./outils.js";

/* ════════════════════════════════════════════════════════════════
   Réglages
   ════════════════════════════════════════════════════════════════ */
export function dessinerReglages() {
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
          <span class="note">${c.lien_seul ? "Lien direct uniquement (lecture automatique interdite par le site)" : c.cle_manquante ? "Clé à ajouter dans Vercel (voir le guide)" : c.mots ? "Recherche par vos mots-clés" : "Postes tech et quant à Paris, et vos mots-clés"}</span>
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
