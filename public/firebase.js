// Accès Firebase : connexion et données propres à chaque compte.
// Toutes les données d'un compte vivent sous users/{uid}/… et les règles Firestore
// interdisent à un compte de lire celles de l'autre.
const VERSION = "10.12.2";
const CDN = `https://www.gstatic.com/firebasejs/${VERSION}`;

let A, S, auth, db;

export async function initialiser(config) {
  const [appMod, authMod, storeMod] = await Promise.all([
    import(`${CDN}/firebase-app.js`),
    import(`${CDN}/firebase-auth.js`),
    import(`${CDN}/firebase-firestore.js`),
  ]);
  A = authMod;
  S = storeMod;
  const app = appMod.initializeApp(config);
  auth = A.getAuth(app);
  try {
    // cache local : l'app s'ouvre et reste utilisable sans réseau (métro)
    db = S.initializeFirestore(app, { localCache: S.persistentLocalCache() });
  } catch {
    db = S.getFirestore(app);
  }
}

/* ── Compte ──────────────────────────────────────────────────── */
export const surChangementCompte = (rappel) => A.onAuthStateChanged(auth, rappel);
export const connecter = (email, mdp) => A.signInWithEmailAndPassword(auth, email, mdp);
export const deconnecter = () => A.signOut(auth);
export const reinitialiserMotDePasse = (email) => A.sendPasswordResetEmail(auth, email);
export const jeton = () => auth.currentUser.getIdToken();

/* ── Données ─────────────────────────────────────────────────── */
// Les écritures ne sont jamais attendues : hors réseau, Firestore les garde en file
// et les envoie au retour de la connexion, tandis que l'écran se met à jour tout de suite.
const silence = (p) => p.catch((e) => console.warn("Écriture Firebase :", e));

export function ecouterProfil(uid, rappel) {
  return S.onSnapshot(
    S.doc(db, "users", uid),
    { includeMetadataChanges: true },
    (s) => rappel(s.exists() ? s.data() : null, s.metadata.fromCache),
    (e) => rappel(undefined, true, e)
  );
}

export const ecrireProfil = (uid, donnees) =>
  silence(S.setDoc(S.doc(db, "users", uid), donnees, { merge: true }));

export const remplacerProfil = (uid, donnees) =>
  silence(S.setDoc(S.doc(db, "users", uid), donnees));

export function ecouterCollection(uid, nom, rappel) {
  return S.onSnapshot(
    S.collection(db, "users", uid, nom),
    (qs) => rappel(qs.docs.map((d) => ({ docId: d.id, ...d.data() }))),
    (e) => console.warn("Lecture Firebase :", e)
  );
}

export const ecrireDoc = (uid, nom, id, donnees) =>
  silence(S.setDoc(S.doc(db, "users", uid, nom, id), donnees, { merge: true }));

export const supprimerDoc = (uid, nom, id) =>
  silence(S.deleteDoc(S.doc(db, "users", uid, nom, id)));

export async function lireVues(uid) {
  try {
    const s = await S.getDoc(S.doc(db, "users", uid, "etat", "vues"));
    return (s.exists() && s.data().ids) || {};
  } catch {
    return {};
  }
}

export const ecrireVues = (uid, ids) =>
  silence(S.setDoc(S.doc(db, "users", uid, "etat", "vues"), { ids }));
