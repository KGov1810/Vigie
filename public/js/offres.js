// Onglet Offres : secteurs, cartes, filtres, favoris et suivi depuis une carte, liens directs.
import * as FB from "../firebase.js";
import { actualiser, chargerCache, planDeLecture } from "./actualisation.js";
import { CONTRATS, GROUPES_PROFIL, JOUR, STATUTS } from "./constantes.js";
import { etat } from "./etat.js";
import { montrerVue } from "./navigation.js";
import { $, $$, categorieContrat, echappe, hachage, normaliser, toast } from "./outils.js";

/* ════════════════════════════════════════════════════════════════
   Secteurs et plan de lecture des sites
   ════════════════════════════════════════════════════════════════ */
export function dessinerSecteurs() {
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

export function carteOffre(o) {
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

export function dessinerOffres() {
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
export function dessinerFiltres(toutes = etat.derniereListe || []) {
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
export function dessinerLiensDirects() {
  const groupes = GROUPES_PROFIL[etat.profil.profil] || [];
  const eteints = new Set(etat.profil.sources_off || []);
  const liens = Object.values(etat.catalogue).filter((c) => c.lien && groupes.includes(c.groupe) && !eteints.has(c.id));
  $("#liens-directs").hidden = !liens.length;
  $("#liens-directs-liste").innerHTML = liens.map((c) =>
    `<a href="${echappe(c.lien)}" target="_blank" rel="noopener">${echappe(c.nom)}</a>`).join("");
}
