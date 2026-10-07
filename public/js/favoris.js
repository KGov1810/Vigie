// Onglet Favoris.
import { etat } from "./etat.js";
import { carteOffre } from "./offres.js";
import { $ } from "./outils.js";

/* ════════════════════════════════════════════════════════════════
   Favoris
   ════════════════════════════════════════════════════════════════ */
export function dessinerFavoris() {
  const zone = $("#liste-favoris");
  const favoris = [...etat.favoris.entries()]
    .sort(([, a], [, b]) => String(b.ajoute_le).localeCompare(String(a.ajoute_le)));
  if (!favoris.length) {
    zone.innerHTML = `<div class="vide"><p class="vide-titre">Aucun favori pour le moment</p><p>Touchez l'étoile d'une offre pour la garder ici, même après sa disparition des résultats.</p></div>`;
    return;
  }
  zone.innerHTML = favoris.map(([h, f]) => carteOffre({ ...f.offre, h, vu: etat.vues[h] || 1, nouveau: false })).join("");
}
