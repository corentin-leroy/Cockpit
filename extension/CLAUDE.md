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
- Deux exceptions, VOLONTAIRES, absentes de la popup : `--color-surface-band` (bandes de
  section de la landing) et `--color-surface-column` (colonnes du kanban). La popup n'a
  ni l'un ni l'autre : leur absence n'est pas un oubli de synchronisation (cf.
  DESIGN.md, « Duplication à surveiller »). À ajouter le jour où la popup en aurait
  l'usage.

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
- Vérifié à la main dans l'extension chargée : l'adaptateur s'exécute dans le monde
  ISOLÉ de l'extension (défaut d'`executeScript`) et le Shadow DOM OUVERT y est bien
  lisible. Si un relevé futur montrait un `shadowRoot` nul (le site passerait en Shadow
  DOM fermé), utiliser `chrome.dom.openOrClosedShadowRoot(element)` (dans
  l'adaptateur) ou injecter avec `world: "MAIN"`.

### Indeed (`adapters/indeed.js`, hôte `fr.indeed.com` uniquement)
- Pourquoi la générique échoue (diagnostiqué sur de vraies offres, 2026-10-05) : en
  page seule (`/viewjob?jk=<id>`), un JSON-LD JobPosting existe et la générique
  fonctionnerait ; mais en mode PANNEAU (offre ouverte à droite d'une liste,
  `/jobs?…&vjk=<id>` ou `/?vjk=<id>` sur l'accueil), aucun JSON-LD et
  `document.title` est celui de la RECHERCHE : la générique enregistrait une fausse
  donnée. Les deux modes partagent le même en-tête d'offre : UN seul chemin de
  lecture (l'en-tête), pas de JSON-LD.
- Sélecteurs : `data-testid` UNIQUEMENT (les classes CSS sont générées, `css-g5y9jx
  r-…`). Tout est lu DANS `desktop-job-header` : titre `vj-job-title` ; entreprise =
  texte du lien `a[href*="fromjk="]` de `company-info-metadata` (le nom seul, sans la
  note « · 3.7 ») ; lieu = premier texte du rang qui ne contient pas ce lien (le rang
  peut valoir « <lieu> • Télétravail partiel »). ⚠ Les testids `company-name` et
  `text-location` appartiennent aux CARTES de la liste, jamais à l'offre ouverte : ne
  jamais les lire.
- ⚠ GARDE ANTI-OFFRE-PÉRIMÉE, ne jamais l'assouplir : on ne lit que si le `fromjk` du
  lien entreprise est ÉGAL à l'identifiant de l'URL (`jk` en page seule, `vjk`
  ailleurs). Mesuré (MutationObserver) au changement d'offre : Indeed vide le panneau
  puis remplit URL et contenu dans la même mutation, aucun mélange observé ; la garde
  rend ce comportement indifférent. Vérifié sur de vraies pages : URL désignant une
  autre offre → expiration ; `fromjk` falsifié → expiration ; valeurs restaurées →
  lecture. Lien `fromjk` présent sur 19 offres sur 19 relevées (CFA, grands groupes, et
  petits employeurs : bar, restaurant) ; s'il manquait un jour, l'offre expire au lieu
  d'être lue.
- Pas d'identifiant dans l'URL → `notice: "not-an-offer"` IMMÉDIAT, même si le panneau
  montre l'offre PAR DÉFAUT (première de la liste) : au chargement de l'accueil ou
  d'une recherche, elle s'affiche sans `vjk` (sur une recherche, `vjk` arrive < 2 s
  après, onglet visible ; sur l'accueil, seulement au premier clic). DÉCISION du
  propriétaire (2026-10-05) : ne pas lire cette offre sur la foi du seul en-tête ;
  l'utilisateur clique l'offre (ce qui ajoute `vjk`) puis rouvre la popup.
- Attente : 100 ms, 10 s au plus (`TIMEOUT_MS`), comme France Travail. Passé le délai :
  champs vides + lien canonique + `notice: "timeout"`.
- Lien enregistré : `https://fr.indeed.com/viewjob?jk=<id>`, jamais `location.href`
  (en mode panneau, il rouvrirait la recherche et dépasse souvent 2048 caractères).
  Vérifié : la page s'ouvre seule à cette adresse.
- Identifiant : 16 caractères hexadécimaux (tous ceux observés).
- Autres pays Indeed (`www.indeed.com`, `be.indeed.com`…) : NON couverts, extraction
  générique. Les ajouter exige un relevé sur de vraies offres de ces domaines.
- ⚠ PIÈGE pour les relevés : un clic PROGRAMMATIQUE (`element.click()`) sur une carte
  sans lien envoie vers `viewjob?jk=abcdef0123456789` (« Page introuvable ») ; des
  navigations répétées déclenchent une vérification anti-robot (ne jamais la
  résoudre). Pour un relevé, cliquer comme un humain et naviguer peu. L'extension,
  elle, ne clique jamais : elle lit l'offre que l'utilisateur a ouverte.
- Testé d'abord par injection dans la page (même code ; la page seule `/viewjob`
  n'avait pu être relue avec la version finale, vérification anti-robot), puis
  vérifié à la main dans l'extension chargée.

## Comportements volontaires — ne pas « corriger »
- La popup se ferme automatiquement 900 ms après un ajout réussi. C'est un choix assumé :
  la fermeture fait elle-même office de confirmation.
- Les messages d'erreur n'ont pas de timer et restent affichés sans limite de temps.