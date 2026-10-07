// Barre d'onglets.
import { dessinerCandidatures } from "./candidatures.js";
import { etat } from "./etat.js";
import { dessinerFavoris } from "./favoris.js";
import { $, $$ } from "./outils.js";
import { dessinerReglages } from "./reglages.js";

/* ════════════════════════════════════════════════════════════════
   Navigation
   ════════════════════════════════════════════════════════════════ */
export function montrerVue(nom) {
  etat.vue = nom;
  for (const v of ["offres", "favoris", "candidatures", "reglages"]) $("#vue-" + v).hidden = v !== nom;
  $$(".onglet").forEach((o) => o.classList.toggle("actif", o.dataset.vue === nom));
  if (nom === "favoris") dessinerFavoris();
  if (nom === "candidatures") dessinerCandidatures();
  if (nom === "reglages" && !etat.reglagesModifies) dessinerReglages();
  window.scrollTo(0, 0);
}

$$(".onglet").forEach((o) => o.addEventListener("click", () => montrerVue(o.dataset.vue)));
