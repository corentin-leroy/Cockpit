# Extension Chrome (Manifest V3)

## Sécurité — non négociable
- L'URL de l'API est figée dans `api.js` et dans `host_permissions`.
  N'ajoute jamais de page d'options ni de champ permettant de la configurer :
  une URL modifiable serait un canal d'exfiltration du token d'authentification.
- Pour le dev local, la bascule d'URL est manuelle et ne doit jamais être committée.

## Design tokens — synchronisation manuelle
- Le bloc `<style>` de `popup.html` duplique volontairement les tokens de `tokens.css`
  (couleurs des deux thèmes, espacements, rayons, typo).
- Deux sélecteurs seulement : `:root` pour le thème clair, et une media query
  `prefers-color-scheme: dark`. La popup n'a pas de bascule de thème manuelle.
- Toute modification de la palette dans `tokens.css` doit être reportée ici dans la même
  passe. Signale-le-moi explicitement quand tu touches aux couleurs.

## Messages de la popup
- Un seul conteneur, `<p id="message">`, présent dans le HTML initial et partagé entre
  succès, erreur et messages neutres. Le type est porté par `className`.
- Il porte `role="status"` et `aria-atomic="true"` : ne les retire pas, ne crée pas de
  second conteneur.
- Aucun emoji dans les chaînes de `popup.js` : le pictogramme d'état vient uniquement
  du CSS (`::before`).

## Bornes de validation — miroir du backend
- `limits.js` reprend les bornes de `backend/app/limits.py` (titre, entreprise,
  lieu : 255 ; url : 2048), posées par code sur les champs de la popup
  (`titleEl.maxLength = ...`) plutôt qu'en dur dans popup.html.
- N'inclut PAS la troncature appliquée à l'extraction (title/company/location
  coupés à 255 dans `extractOffer`, background.js, et dans chaque adaptateur de
  `adapters/`) : ces fonctions sont sérialisées et exécutées dans la page
  visitée, elles ne peuvent importer aucun module — ces valeurs y restent
  dupliquées en dur.
- Toute modification des bornes backend doit être répercutée dans CE fichier ET
  dans le corps d'`extractOffer` ET dans chaque adaptateur (`adapters/*.js`,
  constante `FIELD_MAX_LENGTH`) : trois endroits, pour la raison ci-dessus.

## Adaptateurs d'extraction par site (`adapters/`)
- `extractOffer` (background.js) est l'extraction GÉNÉRIQUE (JSON-LD JobPosting,
  repli sur le titre de la page). Elle reste inchangée et sert sur tout site sans
  adaptateur. Un adaptateur est une fonction autonome (même contrainte de
  sérialisation : aucun import, aucune variable extérieure) injectée À LA PLACE
  d'`extractOffer`.
- Le choix se fait dans le service worker, d'après le nom d'hôte EXACT de l'onglet
  actif (`adapters/index.js`, `findAdapter(tab.url)` ; `tab.url` vient du droit
  `activeTab`). Hôte inconnu ou URL absente → générique. Aucune permission à
  ajouter, aucune régression possible sur les autres sites par construction.
  Indeed reste volontairement exclu (raisons légales).
- Un adaptateur renvoie le même objet qu'`extractOffer` ; il peut ajouter un champ
  `notice` quand il n'y a rien à lire. La popup l'affiche puis le RETIRE
  (`currentOffer` est fusionné dans ce qui part vers l'API) : ne jamais le laisser
  atteindre le POST.
- Ajouter un site : un fichier dans `adapters/`, son entrée dans `ADAPTERS`
  (hôtes exacts), puis la procédure de test à la main (pas de lanceur de tests).

### France Travail (`adapters/francetravail.js`, hôte `candidat.francetravail.fr`)
- Pourquoi la générique échoue (diagnostiqué sur de vraies offres, 2026-10-02) :
  aucun JSON-LD ; `document.title` = « Offre d'emploi <intitulé> - 59 - Lille -
  214NYCN | France Travail » en page seule, titre de la LISTE en mode panneau ;
  le bloc de l'offre est dans le Shadow DOM OUVERT d'un élément
  `<descriptif-offre id-offre="…">`, rendu APRÈS le chargement de la page.
- Deux modes, même bloc : page de détail seule, ou panneau ouvert sur la liste (l'URL
  devient `/offres/recherche/detail/<numéro>`, sans paramètres de recherche). On ne
  lit QUE le bloc de l'offre ouverte, jamais la page entière (la liste contient
  d'autres offres). Sélecteurs : attributs `data-cy` du composant (`intituleOffre`,
  `lieuTravail_entete`, `nom-etablissement`, `numeroOffre`), plus stables que les
  classes. Si le site les renomme, l'adaptateur expire (message neutre) au lieu de
  lire autre chose : refaire le relevé sur une vraie offre.
- ⚠ GARDE ANTI-OFFRE-PÉRIMÉE, ne jamais l'assouplir : l'élément est REMPLACÉ à
  chaque ouverture et RESTE dans le DOM, avec la dernière offre, quand on ferme le
  panneau ; pendant le chargement d'une nouvelle offre, l'URL a déjà changé mais
  l'élément porte encore l'ancienne. On ne lit donc que si TROIS numéros concordent :
  celui de l'URL, l'attribut `id-offre` et le « Offre n° … » affiché. Sans cela,
  l'extension enregistrerait silencieusement la mauvaise offre. Vérifié sur de
  vraies pages en falsifiant chacun des trois numéros : l'extraction expire.
- Attente : le contenu arrive de façon asynchrone ; l'adaptateur interroge la page
  toutes les 100 ms, 10 s au plus (`TIMEOUT_MS`). La popup affiche « Lecture de
  l'offre… » pendant ce temps. Passé le délai : champs vides + lien canonique + message
  neutre (`notice: "timeout"`). Mesuré dans un onglet MASQUÉ : 3 à 5 s en mode
  panneau, jusqu'à ~10,8 s en page seule fraîchement chargée (probablement un artefact
  de l'onglet masqué, non prouvé) : à mesurer en onglet visible, et à ajuster si les
  expirations sont fréquentes.
- Pas une page d'offre (liste sans panneau ouvert, accueil…) : champs vides, AUCUN lien,
  `notice: "not-an-offer"` (« Ouvrez une offre pour l'ajouter. »). Préremplir avec le
  titre de la liste et l'URL de recherche reviendrait à enregistrer de fausses données.
- Offre anonyme : la carte « L'employeur » existe sans nom (ni `nom-etablissement`).
  Entreprise préremplie à « Entreprise non communiquée » (le backend exige une
  entreprise non vide), modifiable dans la popup.
- Lien enregistré : `https://candidat.francetravail.fr/offres/recherche/detail/<numéro>`
  construit depuis le numéro, jamais `location.href`. Format vérifié : c'est l'URL du
  site lui-même en mode panneau, et la page s'ouvre seule à cette adresse (aucun
  `rel=canonical` ni `og:url`). 40 numéros observés, tous `\d{3}[A-Z]{4}` ; le garde
  accepte 5 à 12 caractères alphanumériques.
- ⚠ N'APPELER JAMAIS l'API interne du site (`/api-descriptifoffre/…`) : ni documentée
  ni prévue pour un usage externe. L'adaptateur ne lit que la page.
- Point à confirmer à la main : l'adaptateur s'exécute dans le monde ISOLÉ de
  l'extension (défaut d'`executeScript`) ; un Shadow DOM OUVERT y reste lisible, mais
  ce n'est pas vérifiable hors extension chargée. Si la procédure de test montre un
  `shadowRoot` nul, utiliser `chrome.dom.openOrClosedShadowRoot(element)` (dans
  l'adaptateur) ou injecter avec `world: "MAIN"`.

## Comportements volontaires — ne pas « corriger »
- La popup se ferme automatiquement 900 ms après un ajout réussi. C'est un choix assumé :
  la fermeture fait elle-même office de confirmation.
- Les messages d'erreur n'ont pas de timer et restent affichés sans limite de temps.