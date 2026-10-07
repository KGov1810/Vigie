// Onglet Candidatures : statuts, notes, relances.
import * as FB from "../firebase.js";
import { JOURS_AVANT_RELANCE, STATUTS } from "./constantes.js";
import { etat } from "./etat.js";
import { $, echappe, joursDepuis, relatif, toast } from "./outils.js";

/* ════════════════════════════════════════════════════════════════
   Candidatures
   ════════════════════════════════════════════════════════════════ */
export function majPastille() {
  const enCours = [...etat.candidatures.values()].filter((c) => !["acceptee", "refusee"].includes(c.statut)).length;
  $("#pastille-candidatures").textContent = enCours;
  $("#pastille-candidatures").hidden = !enCours;
}

export function dessinerCandidatures() {
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
