// Point d'entrée de Vigie : charge les modules, enregistre le service worker et démarre.
import { demarrer } from "./js/compte.js";
// modules qui enregistrent leurs écouteurs (boutons, onglets, formulaires) au chargement
import "./js/navigation.js";
import "./js/offres.js";
import "./js/actualisation.js";
import "./js/candidatures.js";
import "./js/reglages.js";

/* ════════════════════════════════════════════════════════════════
   Lancement
   ════════════════════════════════════════════════════════════════ */
if ("serviceWorker" in navigator) {
  navigator.serviceWorker.register("/sw.js").catch(() => {});
}

demarrer();
