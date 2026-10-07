# Vigie mobile : installation et utilisation

Vigie lit en direct les sites d'emploi qui vous intéressent et affiche les offres d'Île-de-France sur votre téléphone. Chaque offre ouvre la vraie annonce : c'est vous qui postulez, Vigie ne le fait jamais.

Chacun a son compte. Vous voyez les offres Finance & Tech, votre compagne les offres Droit & RH, et personne ne voit les favoris ni les candidatures de l'autre.

**L'installation se fait une seule fois, sur un ordinateur, en 30 à 40 minutes.** Tout est gratuit et aucune carte bancaire n'est demandée.

---

## Comment ça marche

- **L'application** s'installe sur l'écran d'accueil de l'iPhone depuis Safari, comme une vraie app.
- **Le relais** est un petit programme en ligne qui lit les sites à la place du téléphone : Safari n'a pas le droit de lire directement les sites carrières. Il est hébergé gratuitement chez Vercel, à Paris.
- **Firebase** (Google) gère vos deux comptes et garde vos favoris, candidatures et réglages.

---

## Étape 1 : Firebase (comptes et données), environ 10 minutes

1. Allez sur **console.firebase.google.com** et connectez-vous avec un compte Google.
2. Cliquez sur **Créer un projet**, nommez-le `vigie`, **désactivez Google Analytics**, puis validez.
3. Créez les deux comptes :
   - Dans le menu de gauche, ouvrez **Authentication** puis cliquez sur **Commencer**.
   - Dans l'onglet **Sign-in method**, choisissez **E-mail/Mot de passe**, activez le premier interrupteur et enregistrez.
   - Dans l'onglet **Users**, cliquez sur **Ajouter un utilisateur** et saisissez votre e-mail et un mot de passe d'au moins 6 caractères.
   - Recommencez pour votre compagne.
   > Vigie n'a pas d'écran d'inscription : seuls les comptes créés ici peuvent se connecter.
4. Créez la base de données :
   - Dans le menu de gauche, ouvrez **Firestore Database** puis cliquez sur **Créer une base de données**.
   - Choisissez l'emplacement **eur3 (Europe)**, puis le **mode production**.
5. Dans l'onglet **Règles** de Firestore, effacez tout le texte, collez le contenu du fichier `firestore.rules` fourni, puis cliquez sur **Publier**.
   > Ces règles garantissent que chaque compte ne voit que ses propres données.
6. Récupérez la configuration :
   - Ouvrez la **roue dentée** en haut à gauche, puis **Paramètres du projet**.
   - En bas de la page, cliquez sur l'icône **`</>`** (application Web), donnez-lui le surnom `vigie`, ne cochez pas Hosting, et enregistrez.
   - Copiez tout le bloc qui commence par `const firebaseConfig = {` et gardez-le pour l'étape 3.

## Étape 2 : GitHub (stocker l'application), environ 5 minutes

1. Créez un compte gratuit sur **github.com**.
2. Cliquez sur **+** en haut à droite, puis **New repository**. Nommez-le `vigie`, choisissez **Private**, puis **Create repository**.
3. Sur la page suivante, cliquez sur le lien **uploading an existing file**.
4. Dézippez `Vigie-mobile.zip`, ouvrez le dossier `vigie-mobile`, sélectionnez **tout son contenu** et glissez-le dans la page. Il contient les dossiers `api` et `public`, ainsi que `vercel.json`, `requirements.txt`, `firestore.rules` et ce guide.
5. Cliquez sur **Commit changes**.
   > Vérifiez qu'à la racine du dépôt on voit directement `api`, `public` et `vercel.json`, et non un dossier `vigie-mobile`.

## Étape 3 : Vercel (mettre l'application en ligne), environ 5 minutes

1. Sur **vercel.com**, cliquez sur **Sign Up**, choisissez l'offre **Hobby** (gratuite), puis **Continue with GitHub**.
2. Cliquez sur **Add New…**, puis **Project**, et importez le dépôt `vigie`. Autorisez l'accès si Vercel le demande.
3. Laissez le réglage **Framework Preset : Other**, puis ouvrez **Environment Variables** et ajoutez :

   | Name | Value |
   |---|---|
   | `FIREBASE_CONFIG` | le bloc copié à l'étape 1.6, collé tel quel |
   | `EMAILS_AUTORISES` | vos deux e-mails de connexion, séparés par une virgule, par exemple `vous@mail.fr,elle@mail.fr` |

   `EMAILS_AUTORISES` est conseillée : elle réserve le relais à vos deux comptes. Les clés France Travail et Adzuna sont facultatives et peuvent être ajoutées plus tard (voir plus bas).
4. Cliquez sur **Deploy**. Au bout d'une minute environ, Vercel affiche l'adresse de votre application, du type `https://vigie-xxxx.vercel.app`.

## Étape 4 : installer sur les téléphones, 1 minute chacun

**iPhone**
1. Ouvrez l'adresse Vercel dans **Safari**.
2. Touchez le bouton **Partager**, puis **Sur l'écran d'accueil**, puis **Ajouter**.
3. Ouvrez Vigie depuis la nouvelle icône, connectez-vous et choisissez votre domaine.

**Android** : ouvrez l'adresse dans Chrome, puis menu **⋮** et **Installer l'application**.

Chacun le fait sur son propre téléphone, avec son propre compte.

---

## Ajouter France Travail et Adzuna (profil Droit & RH, facultatif)

Ces deux sources couvrent une grande partie du marché juridique : France Travail, et Indeed ou LinkedIn via Adzuna. Leurs clés sont gratuites.

- **France Travail** : créez un compte sur **francetravail.io**, puis une application. Abonnez-la à l'API **Offres d'emploi v2** et notez l'**identifiant client** et la **clé secrète**.
- **Adzuna** : inscrivez-vous sur **developer.adzuna.com** pour obtenir un **App ID** et une **App Key**.

Ajoutez ensuite ces clés dans Vercel :
1. Ouvrez votre projet, puis **Settings** et **Environment Variables**.
2. Ajoutez `FRANCE_TRAVAIL_ID`, `FRANCE_TRAVAIL_SECRET`, `ADZUNA_ID` et `ADZUNA_KEY`.
3. Dans **Deployments**, ouvrez le menu **⋯** du dernier déploiement et choisissez **Redeploy**.
   > Une variable ajoutée ne compte qu'après ce redéploiement.

Les clés restent sur le relais et ne sont jamais envoyées au téléphone.

---

## Utilisation au quotidien

**Offres**
- À l'ouverture, la dernière liste s'affiche aussitôt, puis se met à jour en direct. La barre sous l'en-tête avance à mesure que les sites répondent.
- Touchez une offre pour ouvrir la vraie annonce sur le site d'origine et y postuler.
- Les **secteurs** en haut de l'écran changent les mots-clés et les sites interrogés.
- **Nouveau** signale une offre apparue ces dernières 24 heures. Au tout premier usage, rien n'est marqué, puisque tout est nouveau.
- Les offres sans date de publication affichent en gris le jour où Vigie les a repérées.
- **Filtres** masque des types de contrat (CDI, CDD, alternance, stage) ou des provenances (par exemple Welcome to the Jungle). Ces filtres sont mémorisés.
- La ligne « 17 sites sur 19 ont répondu » se touche pour afficher le détail : touchez un site indisponible pour en voir la raison.
- En bas de la liste, **Ouvrir les sites directement** donne accès aux pages déjà filtrées sur Paris.

**Favoris** : l'étoile garde une offre, même après sa disparition des résultats.

**Candidatures** : **Suivre** ajoute une offre à votre suivi.
- Faites évoluer son statut : à postuler, postulée, relancée, entretien, acceptée ou refusée.
- Ajoutez une note : contact, référence, suite de l'entretien.
- Après 8 jours sans changement, une candidature postulée ou relancée est signalée **à relancer**.

**Réglages**
- Modifiez vos secteurs, leurs mots-clés (séparés par des virgules) et les familles de sites interrogées, puis touchez **Enregistrer**.
- Activez ou désactivez chaque site individuellement.

**Bien écrire ses mots-clés (profil Droit & RH).** Vigie juge chaque offre sur son intitulé, pas sur sa description, où trop de mots apparaissent par hasard.
- Sur les sites généralistes (France Travail, Adzuna, Cadremploi), l'intitulé doit contenir le métier et la spécialité d'un mot-clé : « juriste » et « travail » pour « juriste droit du travail ». Le mot « droit » est facultatif, et « RH » vaut « ressources humaines ».
- Sur les sites juridiques, où toutes les annonces sont déjà juridiques, la spécialité suffit : « Avocat collaborateur droit social » apparaît pour « juriste droit social ».
- Pour voir un autre type de poste, ajoutez son mot-clé, par exemple « chargé de recrutement » ou « gestionnaire paie ».

**Sites carrières (profil Finance & Tech).** OpenAI, Google, Qube RT, JPMorgan et les autres publient tous leurs postes parisiens, y compris RH, commercial ou marketing.
- Vigie n'en garde que les postes techniques et quantitatifs : ingénieur, développeur, data, recherche, quant, trader, risque…
- Les fonctions non techniques sont écartées, même quand leur intitulé contient « engineer » (« Technical Recruiter », « Sales Engineer »).
- Vos mots-clés priment toujours : ajoutez « product manager » ou « sales trader » à un secteur pour voir aussi ces postes.

**Dans le métro** : sans réseau, Vigie affiche les offres de la dernière actualisation et le signale. Au retour du réseau, touchez le bouton d'actualisation.

---

## Mettre à jour Vigie

Si je vous envoie une nouvelle version :
1. Dans GitHub, ouvrez le dépôt `vigie`, puis **Add file** et **Upload files**.
2. Glissez les fichiers modifiés, puis **Commit changes**.

Vercel remet l'application en ligne automatiquement en une minute environ.

## Questions fréquentes

**Un site affiche « indisponible ».**
Certains sites bloquent les lectures automatiques, notamment Meta, Goldman Sachs, Tikehau et probablement Cadremploi. D'autres changent parfois leur page. Utilisez alors son lien dans **Ouvrir les sites directement**. Si un site qui fonctionnait tombe en panne durablement, envoyez-moi le message affiché en le touchant.

**L'écran « Vigie n'est pas encore reliée à Firebase » s'affiche.**
La variable `FIREBASE_CONFIG` manque ou a été mal collée dans Vercel. Corrigez-la, puis relancez le déploiement avec **Redeploy**.

**L'écran « Données inaccessibles » s'affiche.**
Les règles Firestore de l'étape 1.5 n'ont pas été publiées.

**« Ce compte n'est pas autorisé sur le relais » s'affiche.**
L'e-mail de ce compte manque dans `EMAILS_AUTORISES` ou y est mal orthographié. Corrigez la variable dans Vercel, puis relancez le déploiement avec **Redeploy**.

**« Session expirée » s'affiche.**
Déconnectez-vous dans Réglages, puis reconnectez-vous.

**Combien ça coûte ?**
Rien. Les offres gratuites de Firebase (Spark) et de Vercel (Hobby) dépassent largement l'usage de deux personnes.

**Est-ce sûr ?**
- Le relais ne lit que les sites prévus dans l'application, jamais une adresse quelconque.
- Il ne répond qu'aux comptes connectés, et seulement aux e-mails de `EMAILS_AUTORISES` si vous l'avez renseignée. Sans cette variable, une personne qui se créerait un compte dans votre projet Firebase pourrait utiliser le relais, mais sans jamais voir vos données.
- Chaque compte n'accède qu'à ses propres données.

**Peut-on ajouter un site qui n'est pas dans la liste ?**
Oui, mais il faut modifier le relais : demandez-le-moi en donnant le lien de la page d'offres.
