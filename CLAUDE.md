# Cockpit

SaaS de suivi de candidatures, tous types de contrats : CRM kanban (cœur du
produit) + extension navigateur pour l'ajout d'offres depuis n'importe quel site.
Agrégation via API officielles (La Bonne Alternance, France Travail) reportée
en V1.5. AUCUN scraping serveur, AUCUN stockage de credentials de sites tiers.

# Stack
- Backend : FastAPI + SQLAlchemy 2.0 + SQLite (dev/tests) ou PostgreSQL (prod)
- Frontend : React 19 + Vite + React Router 7 (dossier frontend/)
- Extension : Chrome Manifest V3 (dossier extension/)

# Commandes
Backend (depuis backend/, venv activé) :
- Installer : `.venv\Scripts\python.exe -m pip install -r requirements-dev.txt`
  (requirements-dev.txt inclut requirements.txt + pytest/httpx ; la PRODUCTION
  n'installe que requirements.txt)
- Créer/mettre à jour la base : `.venv\Scripts\python.exe -m alembic upgrade head`
  (l'API ne crée PLUS aucune table au démarrage : un cockpit.db neuf, ou en
  retard sur le schéma, s'obtient par cette commande. Cf. « Migrations »).
- Lancer l'API : `.venv\Scripts\python.exe -m uvicorn app.main:app --reload`
- Tests : `.venv\Scripts\python.exe -m pytest` (depuis backend/) — suite ciblée
  sécurité (auth, ownership). Base SQLite EN MÉMOIRE isolée, recréée à chaque
  test ; ne touche jamais cockpit.db et n'envoie aucun email (Brevo forcé en
  mode DEV dans tests/conftest.py). Voir « Tests backend » plus bas.
Frontend (depuis frontend/) :
- Installer : `npm install`
- Lancer : `npm run dev` (http://localhost:5173)
- Build : `npm run build` ; Lint : `npm run lint`

# Direction visuelle
- `DESIGN.md` à la racine est la référence unique pour tout ce qui touche au
  style : densité, échelle typographique, espacements, usage de la couleur,
  interdits. Le lire AVANT toute modification de CSS ou de rendu.
- Cockpit est un outil dense, consulté plusieurs fois par jour (référence de
  densité : Notion). La couleur et l'espace signalent, ils ne décorent pas.
- Les tokens (couleurs, espacements, typo) sont dupliqués dans le bloc `<style>`
  de `extension/popup.html` : toute modification de `tokens.css` doit y être
  répercutée dans la même passe.

# Architecture backend
- `app/models.py` = tables SQLAlchemy ; `app/schemas.py` = contrats Pydantic.
  Ne jamais exposer un modèle ORM directement dans une réponse API.
- Un router par ressource dans `app/routers/` (auth, boards, applications).
- Hiérarchie des données : User → Boards → Applications.
  - Un Board (tableau kanban) appartient à un User (board.user_id).
  - Une Application appartient à un Board (application.board_id). Elle ne porte
    PLUS de user_id : le propriétaire se déduit en chaîne (application → board →
    user), pour éviter toute redondance.
- Ownership : cloisonné par user. Pour un board, filtre direct sur board.user_id
  (helper `get_owned_board` dans routers/boards.py, réutilisé par applications).
  Pour une candidature, jointure application → board et filtre sur board.user_id.
  Accès à la ressource d'autrui → 404 (pas 403), pour ne pas confirmer un id.
- À l'inscription, un board par défaut "Mes candidatures" est créé : un user a
  TOUJOURS au moins un tableau. Corollaire : la suppression du DERNIER tableau
  d'un user est refusée (409). Supprimer un board supprime ses candidatures.
- Créer une candidature exige un board_id ; le serveur vérifie qu'il appartient
  au current_user (sinon 404). GET /applications filtre par ?board_id=,
  ?status_filter= et/ou ?archived= (cf. « Archivage des candidatures »).
- Le statut d'une candidature n'est PAS modifiable à la création (démarre
  toujours en "saved"/Repérée). Il évolue ensuite par PATCH, via deux chemins :
  le drag & drop entre colonnes, et le champ « statut » du formulaire, affiché
  UNIQUEMENT en mode édition (jamais à la création).

# Cascade de suppression (schéma + ORM)
- Déclarée à DEUX niveaux, complémentaires et non redondants :
  - SCHÉMA : `ondelete="CASCADE"` sur chaque ForeignKey (board.user_id →
    users.id, application.board_id → boards.id, security_token.user_id →
    users.id). C'est la BASE qui garantit qu'aucune ligne ne survit à son parent,
    quel que soit le chemin : ORM, script de maintenance, psql, migration. Sans
    cela, toute suppression contournant l'ORM échouait en PostgreSQL sur une
    violation de contrainte (le défaut d'une FK est NO ACTION, qui REFUSE de
    supprimer un parent encore référencé).
  - ORM : `cascade="all, delete-orphan"` sur les relations parentes. Toujours
    nécessaire — il porte la sémantique ORPHELIN (retirer un enfant de la
    collection de son parent le supprime), que la base ne connaît pas.
- `passive_deletes=True` sur ces mêmes relations articule les deux : SQLAlchemy
  ne charge plus les enfants pour les supprimer un par un, il émet UN SEUL DELETE
  sur le parent et laisse la base propager. Supprimer un user passait de
  1 SELECT par board + 1 DELETE par ligne à un unique `DELETE FROM users`.
  Comportement observable inchangé (test de non-régression dans
  test_account_deletion.py).
- SQLite n'applique PAS les clés étrangères par défaut, et le réglage est propre
  à CHAQUE CONNEXION. `app/database.py` pose donc un écouteur `connect` qui
  exécute `PRAGMA foreign_keys=ON` sur toute connexion SQLite. Sans lui, la
  cascade serait purement décorative en dev et dans les tests : supprimer un user
  laisserait des orphelins EN SILENCE, alors que la prod (PostgreSQL) irait bien.
  L'écouteur est posé sur la CLASSE `Engine`, pas sur l'instance : le moteur de
  test créé par tests/conftest.py en bénéficie sans le savoir.
- ⚠ CHANGEMENT DE SCHÉMA : toute modification de models.py exige une migration
  Alembic (cf. « Migrations »). Un changement de contrainte ou de colonne ne
  s'applique JAMAIS tout seul à une table existante, et rien ne le signale.
  Vérifié le 2026-09-25 : la prod PostgreSQL porte bien les `ON DELETE CASCADE`
  ci-dessus (les 3 FK), au même titre que cockpit.db.

# Limites de quantité (garde-fous anti-abus)
- Toutes les constantes sont dans `app/limits.py` (source unique, importée par
  les routers et par main.py) :
  - MAX_BOARDS_PER_USER = 10
  - MAX_APPLICATIONS_PER_USER = 300 (candidatures ACTIVES seulement, cf.
    « Archivage des candidatures »)
  - MAX_ARCHIVED_APPLICATIONS_PER_USER = 2000 (cf. même section)
  - MAX_REQUEST_BODY_BYTES = 1 Mo
- Vérifiées CÔTÉ SERVEUR à la création, jamais côté front : le front peut les
  afficher pour l'UX mais ne fait pas autorité (extension, curl… restent
  plafonnés). Dépassement → 409, et RIEN n'est créé.
- La limite de candidatures est GLOBALE par utilisateur, tous tableaux confondus
  (comptée via la chaîne d'ownership : jointure application → board, filtre sur
  board.user_id). Ce n'est PAS une limite par tableau : l'utilisateur répartit
  ses 300 candidatures librement. Répartir sur plusieurs tableaux ne permet donc
  pas d'en créer davantage.
- Le DÉPLACEMENT d'une candidature (PATCH board_id) ne fait AUCUN contrôle de
  limite, et c'est volontaire : déplacer ne change pas le total de l'utilisateur,
  donc la limite globale ne peut pas être contournée ainsi. Seule la création
  compte. Le PATCH garde évidemment son contrôle d'ownership sur le board cible.
- Taille des corps de requête : middleware ASGI `BodySizeLimitMiddleware`
  (main.py), qui refuse en 413 sur la foi de l'en-tête Content-Length, avant que
  l'endpoint ne bufferise le corps. Défense en profondeur applicative (utile en
  dev, sans proxy) ; en production le garde-fou AUTORITAIRE reste le reverse
  proxy (nginx `client_max_body_size`), seul capable de couper un client qui ment
  sur Content-Length ou l'omet (chunked). On n'implémente pas de comptage à la
  volée côté ASGI : renvoyer un 413 au milieu d'un flux déjà pris en charge par
  l'app provoque un double envoi de réponse.

# Archivage des candidatures
- `Application.archived_at` (DateTime nullable, migration 0003) : NULL = active,
  renseignée = archivée à cette date. Le SERVEUR pose la date (`utcnow()`),
  jamais le client : `archived_at` n'est PAS exposé en écriture dans
  `ApplicationUpdate`, seulement en lecture dans `ApplicationRead`. Deux
  endpoints dédiés, `POST /applications/{id}/archive` et `/unarchive` — pas de
  PATCH générique sur ce champ.
- Le STATUT (ApplicationStatus) n'est JAMAIS modifié par l'archivage ou le
  désarchivage : il reste celui qu'il était au moment d'archiver.
- 409 EXPLICITE (pas d'idempotence silencieuse) sur une action redondante :
  archiver une candidature déjà archivée, ou désarchiver une candidature déjà
  active. Un succès sur une action qui n'a rien fait masquerait un bug côté
  client — cohérent avec le reste du projet (ex. le 409 du dernier tableau).
- Deux plafonds DISTINCTS, comptés GLOBALEMENT par utilisateur (même chaîne
  d'ownership que les autres limites), une candidature ne comptant jamais dans
  les deux à la fois :
  - MAX_APPLICATIONS_PER_USER (300) sur les ACTIVES, à la CRÉATION.
  - MAX_ARCHIVED_APPLICATIONS_PER_USER (2000) sur les ARCHIVÉES, à
    l'ARCHIVAGE. 409 : « Limite de 2000 candidatures archivées atteinte.
    Supprimez d'anciennes archives pour en archiver de nouvelles. »
  - Le DÉSARCHIVAGE est lui aussi plafonné par les 300 actives — sans ce
    contrôle, la limite se contournerait en archivant puis désarchivant. 409 :
    « Limite de 300 candidatures actives atteinte. Supprimez ou archivez une
    candidature active pour faire de la place. » La candidature visée est
    encore archivée au moment du contrôle, donc jamais comptée par erreur
    parmi les 300 actives comparées au plafond.
- ⚠ CORRECTION DE COMPORTEMENT (pas un simple ajout) : le comptage des 300
  actives à la CRÉATION (`create_application`) filtrait auparavant TOUTES les
  candidatures, archivées comprises. Sans le filtre `archived_at IS NULL`,
  archiver ne libérait AUCUNE place — l'archivage n'aurait eu aucun intérêt.
  Test de non-régression : `test_creating_application_counts_only_active_towards_the_cap`
  (tests/test_archiving.py), qui aurait échoué avant cette correction.
- Toutes les LECTURES DE LISTE excluent les archivées par défaut, via
  `?archived=` sur `GET /applications` (`bool`, PAS optionnel : vaut `false`
  quand il est absent — un client qui ignore l'archivage, extension comprise,
  reçoit le comportement sûr). `?archived=true` n'affiche QUE les archivées,
  jamais un mélange.
  Le garde-fou vit dans `_visible_applications_query` (routers/applications.py),
  dont le paramètre `archived` n'a PAS de valeur par défaut : tout futur
  endpoint de liste qui la réutiliserait doit choisir explicitement — l'oubli
  lève une `TypeError` immédiate, pas un bug silencieux. Ce n'est PAS la valeur
  par défaut du paramètre de requête qui protège (elle ne protège que CET
  endpoint), c'est celle-ci.
- L'ACCÈS PAR IDENTIFIANT (`_get_owned_application`, donc `GET`/`PATCH`/`DELETE
  /applications/{id}`) N'EST PAS filtré par `archived_at`, décision
  DÉLIBÉRÉE : la correction d'une candidature depuis la future page d'archives
  en dépend (un PATCH doit rester possible sur une archivée, sans la
  désarchiver au passage).
- La cascade de suppression d'un tableau (cf. « Cascade de suppression »)
  emporte les candidatures ARCHIVÉES comme les actives — `ON DELETE CASCADE` ne
  distingue pas `archived_at`, aucune logique possible à ce niveau.
- `BoardRead` expose `active_applications_count` et `archived_applications_count`
  (routers/boards.py, `_to_board_read`), pour que le frontend puisse annoncer
  le nombre d'archives concernées avant de confirmer la suppression d'un
  tableau (lot frontend séparé). Calculés par DEUX requêtes COUNT par tableau
  (pas une agrégation), donc jusqu'à 2×MAX_BOARDS_PER_USER (20) requêtes
  supplémentaires sur `GET /boards`. MESURÉ (pas supposé), le 2026-09-28, sur
  PostgreSQL 18 jetable, 10 tableaux et ~200 candidatures chacun (2000 lignes,
  mélange actif/archivé) : 34 ms médiane sur 20 appels — négligeable à cette
  échelle (MAX_BOARDS_PER_USER = 10). À reconsidérer seulement si ce plafond
  changeait significativement.

# Validation des entrées (schémas Pydantic)
- RÈGLE : aucune entrée d'un client ne doit produire un 500. Une valeur invalide
  est refusée en 422 AVANT la base. SQLite n'applique pas les longueurs de
  VARCHAR(n) et accepte les NUL : un écart entre borne et colonne, ou un caractère
  non enregistrable, n'échoue qu'en PostgreSQL (prod) — d'où des tests qui portent
  sur la validation, indépendants du moteur (tests/test_input_validation.py).
- Constantes dans `app/limits.py`, à côté des plafonds de quantité : longueurs de
  champs (titre, entreprise, lieu 255 ; url 2048 ; notes 5000 ; nom de tableau
  100 ; mot de passe choisi 128), `MAX_PASSWORD_INPUT_BYTES` (4096), `MAX_ID`.
  Une borne ne doit JAMAIS dépasser la colonne de `models.py` (un test le vérifie).
- Tous les schémas d'ENTRÉE héritent de `InputModel` (schemas.py) : un validateur
  `'*'` refuse, dans tout champ texte, le NUL (U+0000 : PostgreSQL et bcrypt le
  rejettent) et le surrogate isolé (`\ud800` : pas d'encodage UTF-8). REFUSÉS en
  422, jamais nettoyés en silence (dans un mot de passe, retirer un caractère
  changerait l'identifiant). Les schémas de SORTIE (`*Read`, Token,
  MessageResponse) n'en héritent pas. Deux tests gardent l'oubli : tout schéma de
  `schemas.py` est classé entrée/sortie, et tout corps de requête réel des routes
  est un `InputModel`. Un nouveau schéma d'entrée doit donc en hériter.
- Création et modification d'une candidature partagent les MÊMES types (alias
  Title, Company, Location, Url, Notes, RowId) : une valeur acceptée à la création
  l'est à la modification. L'écart entre les deux causait des 500 (location et url
  non bornés en PATCH).
- `notes` : 5000 caractères. La colonne reste `Text` (sans limite en base) jusqu'à
  la migration prévue vers String(5000) (lot 3e) ; le test de cohérence
  s'activera alors tout seul.
- `source` : liste fermée `manual` | `extension` (Literal dans schemas.py,
  colonne String(50) inchangée). Les sources d'API (V1.5) s'ajouteront à cette
  liste le jour où elles existeront. `ApplicationRead.source` reste un `str` pour
  qu'une valeur ancienne quelconque se lise toujours.
- PATCH : un `null` EXPLICITE est refusé (422) sur les champs NOT NULL (title,
  company, status, board_id) et reste permis sur location, url, notes, applied_at
  (c'est le moyen de les vider). Pour ne pas modifier un champ, on l'OMET.
- Identifiants : entiers >= 1 et <= 2147483647 (type `integer` de PostgreSQL).
  `IdPath` / `IdQuery` (dependencies.py) pour l'URL et la requête, `RowId`
  (schemas.py) pour le corps. 0 et les négatifs sont MALFORMÉS : 422, pas 404. Un
  test refuse tout paramètre entier de route non borné.
- Mot de passe CHOISI (inscription, réinitialisation) : 8 à 128 caractères. Mot de
  passe PRÉSENTÉ (login, suppression de compte) : au plus 4096 OCTETS UTF-8, en
  octets car passlib compte les octets (2049 « é » suffisent à le faire lever
  PasswordSizeError). Borne haute technique, jamais un minimum : au-delà, 422 ; le
  401 reste réservé à un mot de passe bien formé mais incorrect. La validation
  précède la recherche du compte : la réponse ne dépend pas de l'existence de
  l'email (anti-énumération préservée).
- Messages d'erreur, RÉDIGÉS PAR LE BACKEND (décision produit, lot 3b) : pas
  traduits par chaque client (frontend, extension) — une table de correspondance
  dupliquée dans les deux aurait divergé avec le temps. Catalogue UNIQUE :
  `app/error_messages.py`, importé seulement par les gestionnaires d'exception
  de `main.py`. `schemas.py` décide QUOI a échoué (un type d'erreur stable + un
  contexte minimal) ; `error_messages.py` décide COMMENT le dire en français.
  Changer un texte ne touche jamais la logique de validation.
- Format de réponse d'erreur, UNIQUE pour tous les codes (422 compris) :
  `detail` est TOUJOURS une CHAÎNE française directement affichable (avant le
  lot 3b, un 422 avait `detail` en TABLEAU brut de Pydantic — cause du
  « [object Object] » côté client ; réparé sans qu'aucun client n'ait dû
  changer, `data?.detail` était déjà ce qu'ils lisaient). Sur un 422 seulement,
  une clé `errors` additive liste chaque erreur : `{"field": "title", "message":
  "..."}`. `field` n'apparaît QUE pour un champ réellement soumis dans le corps
  (`loc == ("body", "<nom>")`) — jamais pour un paramètre de chemin/requête, ni
  pour un corps illisible dans son ensemble (JSON invalide, pas un objet) : ces
  cas n'ont rien à colorer dans un formulaire. `detail` reprend le message de
  la PREMIÈRE erreur (un message actionnable plutôt qu'un décompte).
- Validateurs personnalisés (schemas.py) : PydanticCustomError avec un CODE
  STABLE, JAMAIS un ValueError nu. Sans code stable, les 5 validateurs
  personnalisés (NUL, surrogate isolé, mot de passe trop long, null interdit,
  date hors plage) partageraient tous le type générique `value_error` de
  Pydantic — impossible de choisir le bon message français sans deviner d'après
  le texte de l'exception (fragile). Effet de bord utile, vérifié par
  exécution : un ValueError nu place l'OBJET EXCEPTION Python dans `ctx`, non
  sérialisable proprement ; PydanticCustomError n'y met que le contexte explicite
  passé à l'appel. Tout NOUVEAU validateur personnalisé doit suivre ce patron.
- Libellés de champs (`error_messages.FIELD_LABELS`) : UNE forme, toujours au
  SINGULIER (« Le contenu des notes », jamais « Les notes ») — élimine l'accord
  du verbe, un seul gabarit de phrase sert alors tous les champs. GARDE
  (tests/test_error_messages.py) : tout champ d'un schéma d'entrée, et tout
  paramètre de chemin/requête entier, doit y avoir une entrée. Un type d'erreur
  non catalogué retombe sur `FALLBACK_MESSAGE`, jamais sur le texte brut de
  Pydantic. Une AUTRE garde vérifie que toute entrée du catalogue (générique ou
  dédiée) est exercée par au moins un test réel : un type ajouté sans cas de
  test correspondant fait échouer la suite.
- Deux trous corrigés au lot 3b, tous deux plus souvent vus que les 422 :
  - 401 ANONYME (aucun `Authorization`) : `OAuth2PasswordBearer` lève LUI-MÊME
    un 401 « Not authenticated », EN ANGLAIS, codé en dur dans FastAPI, avant
    même d'atteindre notre code — le message le plus souvent vu par un
    utilisateur réel (une session expirée). Fixé avec `auto_error=False`
    (dependencies.py) : le schéma renvoie `None` au lieu de lever, et
    `get_current_user` décide du message (le même 401 générique que pour un
    token invalide). Attention si ce fichier est retouché : `decode_access_token
    (None)` lèverait une exception NON gérée (500) sans le contrôle explicite
    `if token is None` AVANT l'appel.
  - 500 NON PRÉVU : Starlette renvoyait par défaut un corps VIDE ou non-JSON
    (« Internal Server Error ») ; `response.json()` échouait côté client, qui
    retombait sur `response.statusText` (anglais, sans rapport avec l'erreur).
    `unhandled_exception_handler` (main.py, `@app.exception_handler(Exception)`)
    renvoie désormais un JSON français générique
    (`error_messages.GENERIC_SERVER_ERROR_DETAIL`) ; le texte et la trace de
    l'exception ne sont JAMAIS renvoyés au client, seulement journalisés
    (`logger.exception`, logs locaux et Railway). Ne modifie PAS le
    comportement des exceptions déjà gérées ailleurs (HTTPException,
    RequestValidationError) : FastAPI dispatche toujours au gestionnaire le
    plus spécifique. N'intercepte PAS non plus le comportement de test :
    `TestClient(app, raise_server_exceptions=True)` (le défaut, utilisé par la
    fixture `client`) continue de faire remonter l'exception dans le PROCESSUS
    DE TEST même quand ce gestionnaire produit une réponse — c'est le
    comportement réel d'un serveur déployé qu'il faut simuler avec
    `raise_server_exceptions=False` pour l'observer en test (voir
    test_error_messages.py).
- Avant de changer ces règles ou d'ajouter un champ : sonder l'API contre un
  PostgreSQL 18 jetable (Docker), pas seulement SQLite.
- `applied_at` (PATCH) : ramené en UTC NAÏF puis borné à 1900-01-01 .. 2100-12-31
  (`MIN_APPLIED_AT` / `MAX_APPLIED_AT`, limits.py), hors plage → 422. POURQUOI :
  PostgreSQL accepte des dates de 4713 av. J.-C. à l'an 294276, mais psycopg ne
  relit que les années 1 à 9999. Un fuseau converti en UTC pouvait sortir de cette
  plage (`0001-01-01T00:00:00+02:00`, `9999-12-31T23:59:59-12:00`) : la date était
  ÉCRITE ET COMMITÉE, puis sa relecture (`db.refresh`, juste après le commit)
  échouait. La requête donnait 500 alors que l'écriture avait eu lieu, et la ligne
  restait illisible pour toujours : la LISTE des candidatures du compte (le
  kanban) donnait 500, et même DELETE (il charge la ligne d'abord). Seul un UPDATE
  en base réparait. C'est un empoisonnement de DONNÉES, pas de session. La
  normalisation règle aussi une divergence entre moteurs : `10:00+02:00` était
  écrit 08:00 par PostgreSQL mais 10:00 par SQLite (qui ignore le fuseau).
  Vérification avant déploiement : une requête en lecture seule compte les
  `applied_at` hors plage (cast en TEXTE : un timestamp hors plage ferait échouer
  la lecture elle-même).
- Inscription concurrente de la même adresse : le contrôle de doublon lit puis
  insère, donc plusieurs requêtes passent le contrôle avant qu'aucune n'ait commité.
  C'est le `flush()` (l'INSERT dans users) qui lève la violation de la contrainte
  unique, pas le commit : le `try/except IntegrityError` de `register` couvre les
  deux. Sur violation : rollback, puis RELECTURE de l'email (pas d'analyse du
  message d'erreur : les noms de contraintes diffèrent entre PostgreSQL et SQLite).
  Le compte existe → le MÊME 409 que le contrôle préalable (constante
  `EMAIL_TAKEN_DETAIL`, corps identique par construction) ; il n'existe pas → autre
  violation d'intégrité, elle remonte en 500 visible et n'est jamais déguisée en
  « email déjà pris ». Le contrôle préalable est conservé. Le nombre de perdantes
  n'est pas aléatoire : 14 = 15 (pool 5 + 10) − 1. Avant correction : 14 x 500 /
  25 x 409 / 1 x 201 par manche de 40 requêtes, sous PostgreSQL comme SQLite.
- Connus et NON traités : durcissements de fond prévus dans un lot séparé : casse
  des emails (deux comptes `Case@` et `case@`), bcrypt tronque à 72 octets, schéma
  d'URL (`javascript:` accepté), espaces seuls acceptés côté backend, limites de
  débit. Saturation du pool : inscription et login gardent leur connexion pendant
  le hachage bcrypt (~0,2 s) ; environ 15 requêtes simultanées saturent le pool par
  défaut (5 + 10) et, au-delà de 30 s d'attente, `QueuePool timeout` donne un 500.

# Tests backend (backend/tests/, `.venv\Scripts\python.exe -m pytest`)
- Portée VOLONTAIREMENT ciblée : la matrice sécurité déjà validée manuellement
  (auth + ownership) et les garde-fous anti-abus, pas une couverture exhaustive.
  On teste les points où une régression serait silencieuse et coûteuse (fuite du
  mot de passe, perte de l'anti-énumération, cloisonnement par user, plafonds).
- Fichiers : `test_auth.py`, `test_boards_ownership.py`,
  `test_applications_ownership.py`, `test_limits.py`,
  `test_account_deletion.py`, `test_migrations.py`, `test_input_validation.py`,
  `test_registration_race.py`, `test_error_messages.py`, `test_archiving.py`.
- `test_input_validation.py` : pour chaque champ borné, la valeur maximale passe
  et la valeur maximale + 1 donne 422 (création ET modification) ; NUL et
  surrogate isolé refusés dans chaque champ texte de chaque schéma d'entrée ;
  mot de passe borné en octets au login et à la suppression ; `null` en PATCH ;
  identifiants hors plage ; gardes contre l'oubli (héritage d'`InputModel`,
  paramètres entiers bornés) ; cohérence borne/colonne ; corps 422 sans la valeur
  soumise ; `applied_at` (bornes 1900/2100 acceptées et refusées, fuseau converti
  en UTC naïf, débordements à la conversion, liste toujours lisible ensuite). Le
  client de test LÈVE les exceptions non gérées : un 500 fait échouer le test
  bruyamment. Limite : l'assertion « la liste reste lisible » ne peut pas échouer
  sous SQLite (qui relit l'an 1 sans problème) ; ce qui protège en test, c'est le
  422 et « rien n'est écrit ». Le vrai empoisonnement ne se prouve que sur
  PostgreSQL (sondes HTTP contre un PostgreSQL jetable).
- `test_error_messages.py` : format de réponse d'erreur (app/error_messages.py).
  Les deux trous du 401 anonyme et du 500 catch-all ; un cas HTTP réel par type
  d'erreur du catalogue (bornes, identifiants hors plage, enum/liste fermée,
  email, NUL/surrogate, mot de passe trop long, null interdit, date hors plage,
  JSON invalide, corps pas un objet) ; garde de couverture (tout type du
  catalogue est exercé par un cas de test) ; garde des libellés (tout champ a
  une entrée dans FIELD_LABELS) ; repli générique jamais un plantage ; jamais la
  valeur soumise dans la réponse. Trouvé et corrigé PENDANT l'écriture de ces
  tests (pas seulement supposé) : `int_from_float` absent du catalogue (un
  identifiant flottant, ex. 1.5) ; `is_body_field` confondait un décalage
  d'octet JSON («loc == ("body", 0)») avec un vrai nom de champ, exposant
  `"field": "0"` sur un JSON syntaxiquement invalide ; `bool_parsing`/
  `bool_type` retirés du catalogue (aucun champ booléen dans les schémas
  actuels, donc invérifiables — à réintroduire avec le premier champ booléen).
- `test_archiving.py` : archiver pose `archived_at` et conserve le statut,
  désarchiver l'inverse ; 409 explicite sur une action redondante (archiver une
  archivée, désarchiver une active) ; ownership ; filtre `?archived=` (exclusion
  par défaut, combinaison avec `board_id`/`status_filter`) ; accès par
  identifiant qui reste possible sur une archivée (GET/PATCH/DELETE) ; les deux
  plafonds (2000 archivées, 300 actives au désarchivage) ; LE test de la
  correction du comptage des 300 (archiver doit réellement libérer une place) ;
  cascade de suppression d'un tableau sur une candidature archivée, assertion
  sur l'état stocké (comme test_account_deletion.py) ; compteurs de `BoardRead`.
  Seedé DIRECTEMENT en base pour les plafonds (comme test_limits.py), pas par
  2000 requêtes HTTP.
- `test_registration_race.py` : 40 inscriptions simultanées de la même adresse,
  5 manches, sur une base SQLite FICHIER (une connexion par requête, pool par
  défaut) et non la base en mémoire à connexion unique des autres tests, qui ne
  permettrait pas de vraie concurrence. Exige exactement une 201, le reste en 409,
  zéro exception, un seul compte et un seul tableau par manche (~2 s au total).
  Plus un test déterministe (contrôle préalable rendu aveugle) et un test de garde
  (une autre `IntegrityError` reste un 500, jamais déguisée en 409).
- `test_migrations.py` migre sa PROPRE base SQLite en mémoire (connexion injectée
  via `config.attributes["connection"]`, cf. alembic/env.py) et vérifie : une
  seule tête de migration ; `upgrade head` depuis le vide produit EXACTEMENT le
  schéma des modèles (`alembic check`) ; `downgrade base` ne laisse aucune table.
  C'est lui qui fait échouer la suite quand models.py change SANS migration,
  et il couvre aussi le garde-fou de la migration 0002 (une ligne REJECTED
  interrompt l'upgrade, sans rien modifier) et la conservation des lignes dans
  les deux sens.
  Limites : SQLite uniquement, les types enum natifs de PostgreSQL n'y sont pas
  exercés. ⚠ POINT AVEUGLE : `alembic check` ne compare PAS les libellés d'un
  enum (vérifié sur SQLite ET sur PostgreSQL : aucun écart signalé alors que le
  type en base avait une valeur de moins que le modèle). Un changement de
  valeurs d'enum n'est donc protégé par AUCUN test automatique : il se teste à
  la main sur un PostgreSQL jetable (Docker, `postgres:18`, même version majeure
  que la prod) et se vérifie en prod en lisant les libellés (`pg_enum`).
- `test_account_deletion.py` couvre DELETE /auth/me (mot de passe exigé, refus en
  403, cloisonnement vis-à-vis des autres comptes) ET la cascade elle-même : ses
  assertions portent sur l'ÉTAT STOCKÉ, seul moyen de détecter des orphelins —
  une cascade non appliquée ne produit aucune erreur d'API.
- Dans `test_limits.py`, les candidatures de remplissage sont insérées DIRECTEMENT
  en base (300 POST seraient lents et n'apporteraient rien) : c'est l'état stocké
  qui détermine la limite, et c'est bien lui qu'on met en place.
- Isolation de la base : `tests/conftest.py` pose les variables d'environnement
  AVANT d'importer l'app (l'import de app.main appelle load_dotenv, qui n'écrase
  pas une variable déjà définie). On force ainsi (a) DATABASE_URL=sqlite://
  jetable, filet de sécurité pour qu'aucun test ne puisse viser cockpit.db, (b)
  BREVO_API_KEY/SENDER vides → mode DEV, aucun email réel, (c) un JWT_SECRET_KEY
  de test. La vraie base de test est un SQLite EN MÉMOIRE dédié (StaticPool, pour
  qu'une seule base soit partagée entre connexions), injecté en surchargeant la
  dépendance get_db. Schéma recréé puis détruit à CHAQUE test (fixture `client`) :
  tests indépendants, exécutables seuls et dans n'importe quel ordre.
- Fixtures réutilisables (conftest) : `client` (TestClient sur base vierge),
  `db_session` (assertions directes sur le stockage), et les factories
  `make_user` (inscrit + connecte, renvoie token/headers/board par défaut),
  `make_board`, `make_application`.

# Emails, reset de mot de passe et vérification
- `app/email.py` est la SEULE frontière avec Brevo (API transactionnelle). Le
  reste du code n'appelle que `send_password_reset_email` /
  `send_verification_email`. Mode DEV : sans BREVO_API_KEY (ou sans
  BREVO_SENDER_EMAIL), rien n'est envoyé et le lien est logué dans la console.
- Les liens envoyés par email sont des `SecurityToken` : UNE table pour les deux
  usages, discriminés par `purpose` (password_reset | email_verification).
  Stockage du SHA-256 du token (jamais du clair) ; `secrets.token_urlsafe(32)` à
  la génération ; expiration 60 min (reset) / 24 h (vérification) ; usage unique
  via `consumed_at`. La vérification filtre TOUJOURS sur `purpose` : un lien de
  vérification ne doit jamais pouvoir réinitialiser un mot de passe.
- Vérification d'email NON BLOQUANTE (décision produit) : un compte non vérifié
  se connecte et utilise l'app normalement. `User.is_verified` est exposé dans
  UserRead pour que le front affiche un bandeau d'invitation.
- Un reset de mot de passe réussi passe `is_verified` à True : cliquer sur un
  lien reçu à cette adresse prouve qu'on y a accès, soit exactement ce que
  démontre la vérification d'email.
- Endpoints : POST /auth/forgot-password (public), /auth/reset-password (public,
  token), /auth/verify-email (public, token), /auth/resend-verification
  (authentifié). GET /auth/me (authentifié) renvoie l'utilisateur courant
  (UserRead) : le JWT ne portant que l'id, c'est le SEUL canal qui dit au front
  si l'adresse est vérifiée — et il reste à jour, contrairement à un état qui
  serait figé dans le token à la connexion.

# Session JWT : durée de vie et révocation
- 12 HEURES (720 minutes), pour couvrir une journée d'utilisation sans
  reconnexion. Réglable par ACCESS_TOKEN_EXPIRE_MINUTES sans redéploiement ;
  `ACCESS_TOKEN_EXPIRE_MINUTES` (app/security.py) est la seule source.
- Les jetons sont SANS ÉTAT : rien n'est stocké côté serveur, la signature suffit
  à les valider. Conséquence directe, ils sont IRRÉVOCABLES — se déconnecter
  efface le jeton du navigateur, mais une copie dérobée reste valable jusqu'à son
  expiration, et aucune action serveur ne peut l'annuler. L'EXPIRATION EST DONC
  LA SEULE BORNE à l'exploitation d'un jeton volé : 12 h, c'est douze fois la
  fenêtre d'attaque de l'ancienne heure. Compromis accepté en connaissance de
  cause, contre le confort d'une journée sans reconnexion.
- Seul levier de révocation existant : changer JWT_SECRET_KEY, qui invalide les
  jetons de TOUS les utilisateurs d'un coup. Mesure d'incident, pas de gestion
  courante.
- Baisser la valeur ne raccourcit PAS les sessions en cours : l'expiration est
  inscrite dans chaque jeton à l'émission. Le changement ne vaut que pour les
  connexions suivantes.
- ⚠ NE PAS ALLONGER DAVANTAGE sans introduire des REFRESH TOKENS (déjà en V3,
  cf. hors périmètre). C'est la réponse propre au dilemme confort/sécurité, et
  elle ne consiste pas à étirer la durée : un jeton d'accès COURT (15-30 min,
  donc fenêtre de vol réduite) accompagné d'un refresh token long, stocké EN BASE
  et donc révocable individuellement. On récupère alors ce que le sans-état
  interdit aujourd'hui — déconnecter un appareil, invalider une session
  compromise, sans toucher aux autres utilisateurs. Prolonger encore la durée
  actuelle ne ferait qu'aggraver le problème que les refresh tokens résolvent.
- L'expiration est couverte par test_auth.py (jeton expiré rejeté en 401 sur
  /auth/me et sur les endpoints de données, `exp` conforme à la durée
  configurée, jeton signé d'une autre clé rejeté). Ces tests n'existaient pas
  avant l'allongement : une régression sur la validation de `exp` serait
  parfaitement silencieuse — tout continuerait de marcher, les jetons ne
  cesseraient simplement jamais d'être valables.

# Suppression de compte (droit à l'effacement, RGPD)
- DELETE /auth/me (authentifié) supprime définitivement le compte courant et,
  par cascade, ses tableaux, leurs candidatures et ses jetons de sécurité. C'est
  un EFFACEMENT, pas une désactivation : aucune donnée personnelle ne subsiste.
- Le corps de la requête porte le MOT DE PASSE courant, vérifié avant toute
  suppression. Le JWT ne suffit délibérément pas : il prouve la session, pas
  l'identité. Un token peut fuiter et vit 12 h ; il autorise des actions
  réversibles, jamais la destruction définitive du compte. C'est une
  ré-authentification, pas une case à cocher.
- Mot de passe faux → 403, et non 401. L'appelant est DÉJÀ authentifié comme cet
  utilisateur : on ne lui apprend rien sur l'existence du compte (pas de sujet
  d'énumération ici). Un 401 signifierait « session invalide » et ferait purger
  le token côté front alors que la session est parfaitement valide.
- Front : page /account (protégée, atteignable depuis la navbar), avec une zone
  de suppression nettement séparée et une modale de confirmation exigeant le mot
  de passe. Ni window.confirm ni window.alert : une boîte native ne peut pas
  porter de champ de saisie, ignore les tokens et le thème, et son bouton « OK »
  ne nomme pas l'action. Après succès : purge du token local puis redirection
  vers /login (replace).
- Anti-énumération : /auth/forgot-password renvoie TOUJOURS le même message, que
  le compte existe ou non — y compris quand le plafond d'envois est atteint (pas
  de 429, qui trahirait l'existence du compte). Même principe que le 401
  générique du login.
- Rate limiting des emails sortants : 3 par heure et par (utilisateur, usage),
  compté sur `security_tokens.created_at` — pas de compteur dédié, pas de Redis,
  et le plafond survit à un redémarrage. /auth/resend-verification, lui, est
  authentifié : il peut répondre explicitement 429.

# Base de données : SQLite (dev) et PostgreSQL (prod)
- Le MÊME code tourne sur les deux : seule DATABASE_URL change. Tout ce qui
  dépend du moteur est concentré dans `app/database.py`, nulle part ailleurs.
  - dev/tests : `sqlite:///./cockpit.db` (défaut si la variable est absente)
  - prod : `postgresql+psycopg://user:mdp@hote:5432/base`
- Driver PostgreSQL : psycopg v3 (`psycopg[binary]`), pas psycopg2. C'est le
  driver maintenu, supporté nativement par SQLAlchemy 2.0 via le dialecte
  `postgresql+psycopg`. L'extra [binary] évite toute compilation C.
- `normalize_database_url()` réécrit l'URL au démarrage :
  - `postgres://` (fourni tel quel par Railway, Heroku, Render…) est un alias
    que SQLAlchemy REFUSE depuis la 1.4 → réécrit en `postgresql+psycopg://`.
  - `postgresql://` nu est aussi réécrit, sinon SQLAlchemy chercherait psycopg2,
    qui n'est pas installé.
  - Une URL déjà explicite n'est jamais touchée.
- Options de connexion branchées sur le moteur : `check_same_thread=False` est
  une option du module sqlite3 et ferait ÉCHOUER psycopg → SQLite uniquement.
  `pool_pre_ping=True` ne sert qu'en PostgreSQL (les hébergeurs managés coupent
  les connexions inactives ; sans ping, la première requête après une période
  creuse échoue sur une connexion morte).
- Convention datetime : toutes les colonnes DateTime sont NAIVES en UTC, via le
  helper `utcnow()` (security.py) — y compris les `default`/`onupdate` des
  modèles. Ne JAMAIS y mettre un `datetime.now(timezone.utc)` « aware » : SQLite
  laisse tomber le fuseau en silence, PostgreSQL le convertit vers le fuseau de
  la session avant stockage. Le même code écrirait des heures différentes selon
  le moteur, et fausserait le rate limiting des emails (comparaison sur
  created_at).
- Les tests restent sur SQLite en mémoire (cf. conftest.py) : rapides, isolés,
  aucune dépendance à un PostgreSQL local.
- Session SQLAlchemy par requête (`get_db`, database.py) : ouverte, puis fermée
  dans un `finally` (`db.close()`) ; aucun `rollback` explicite dans l'application,
  et il n'en faut pas : `Session.close()` termine la transaction en cours. Un
  EMPOISONNEMENT DE SESSION (une transaction non annulée qui ferait échouer les
  requêtes suivantes sur la même connexion) a été soupçonné après une DataError et
  ÉCARTÉ, preuve à l'appui, le 2026-09-26 : sur un vrai uvicorn et un PostgreSQL 18
  jetable, pool réduit à UNE connexion, la même connexion (un seul pid, 56
  emprunts) a servi toutes les requêtes ; juste après l'erreur, lectures et
  écritures du même compte et d'un autre compte réussissent, et aucune connexion
  n'est restée `idle in transaction`. Témoin : un `get_db` qui ne ferme jamais la
  session épuise le pool (`QueuePool ... timed out`, 500 en 6 s), donc le test sait
  détecter une session qui fuit. Ce qui ressemblait à un empoisonnement était un
  empoisonnement de DONNÉES (cf. `applied_at`, section « Validation des entrées »).
  Ne pas refaire ce diagnostic ; le pool n'est pas configurable dans l'app
  (database.py : `create_engine` sans `pool_size`), le montage d'essai remplaçait
  `sqlalchemy.create_engine` avant l'import de l'app.

# Migrations (Alembic)
- Le schéma est géré par Alembic (`alembic==1.20.0`, backend/alembic/), en dev
  comme en prod. `main.py` n'appelle PLUS `create_all()` : un `create_all`
  ne modifie jamais une table existante, c'est ce qui l'a fait remplacer.
  Les tests créent leur propre schéma (fixture `client`).
- Commandes (depuis backend/, toujours via le venv) :
  - `.venv\Scripts\python.exe -m alembic upgrade head` : applique les migrations
    (crée une base neuve).
  - `... -m alembic revision --autogenerate -m "description"` : génère une
    migration d'après models.py. TOUJOURS la relire : l'autogénération ne voit
    pas tout (renommage = drop + create, enums PostgreSQL, données).
  - `... -m alembic check` : liste les écarts modèles/base (code de sortie ≠ 0).
  - `... -m alembic current` / `history` : état et historique.
- Changer models.py exige une migration DANS LE MÊME lot : test_migrations.py
  échoue sinon.
- `alembic/env.py` prend l'URL dans `app.database.DATABASE_URL` (jamais dans
  alembic.ini, qui n'en contient aucune), donc normalisée comme celle de l'app.
  Il charge le .env, puis DATABASE_URL posée dans le shell PRIME. Il affiche
  `[alembic] cible : ...` à chaque commande : LIRE cette ligne avant d'écrire.
- Viser la PROD depuis le poste : poser `$env:DATABASE_URL` (valeur de
  `DATABASE_PUBLIC_URL` de Railway, l'URL interne n'est pas joignable) dans la
  SESSION shell uniquement, jamais dans .env, puis la retirer
  (`Remove-Item Env:DATABASE_URL`) ou fermer la fenêtre. Une session restée
  configurée vise la prod à la commande suivante.
- Historique : la révision 0001 (« baseline ») décrit le schéma tel que créé par
  l'ancien create_all. Elle a été marquée appliquée en prod et sur cockpit.db
  par `alembic stamp 0001` (2026-09-25), après comparaison en lecture seule
  (0 écart, `ON DELETE CASCADE` présents, libellés d'enum identiques). Elle ne
  s'exécute que pour bâtir une base neuve.
- Révision 0002 (« remove rejected status ») : retire `REJECTED` de l'enum
  `applicationstatus`. Voir la procédure ci-dessous, qui sert de modèle pour tout
  retrait de valeur d'enum.
- Révision 0003 (« archive applications ») : ajoute `applications.archived_at`
  (DateTime nullable, sans valeur par défaut). À l'opposé de 0002 : une SEULE
  instruction `ADD COLUMN`, aucun ajustement manuel du fichier généré. Mesuré
  (pas supposé), PostgreSQL 18, table de 50 000 lignes : 68 ms — une opération
  de métadonnées, pas une réécriture de table. Toutes les lignes existantes
  valent NULL après la migration (donc actives) : aucune donnée réinterprétée.
- Enums : SQLAlchemy stocke les NOMS des membres (`APPLIED`), pas les valeurs
  (`applied`) — à retenir pour toute requête SQL manuelle. Sous PostgreSQL ce
  sont des types natifs (`applicationstatus`, `tokenpurpose`) : on n'y retire
  pas une valeur (pas de `DROP VALUE`), il faut recréer le type, et l'opération
  échoue s'il reste une ligne portant la valeur retirée.
- Procédure de retrait d'une valeur d'enum (celle de 0002), dans UNE transaction :
  `LOCK TABLE ... ACCESS EXCLUSIVE` (aucune écriture concurrente entre contrôle
  et DDL), garde-fou qui échoue explicitement s'il reste une ligne portant la
  valeur, `ALTER TYPE ... RENAME TO ..._old`, `CREATE TYPE` à la nouvelle liste,
  `ALTER COLUMN ... TYPE ... USING col::text::type`, `DROP TYPE ..._old`. Un
  échec annule tout (vérifié : aucun type `_old` orphelin). Les valeurs sont
  écrites EN DUR dans la migration, jamais importées de app.models (une migration
  décrit un état figé du schéma). Le downgrade fait l'inverse et ne perd aucune
  ligne.
- ORDRE de déploiement pour RETIRER une valeur de statut : (1) le FRONT d'abord
  (retirer une colonne est compatible avec l'ancien backend, l'inverse ne l'est
  pas) ; vérifier en prod qu'aucune ligne ne porte la valeur (comptage en
  MAJUSCULES) et recharger tous les onglets ouverts (un ancien bundle peut encore
  écrire la valeur) ; (2) ensuite migration + backend. Une ligne restée avec la
  valeur retirée deviendrait invisible dans l'interface (BoardPage ignore un
  statut inconnu) et ne se corrigerait que par SQL ou par l'API.
- Migrations 0001 et 0002 testées sur un PostgreSQL 18.6 jetable (Docker) :
  upgrade/downgrade/upgrade, contenu des lignes identique (md5), libellés du type
  lus, cas d'échec, verrou face à une transaction concurrente, et
  `downgrade base` puis remontée depuis le vide (le `downgrade` de la baseline,
  qui supprime les types enum, fonctionne sur PostgreSQL).
- Une migration doit rester COMPATIBLE AVEC LA VERSION PRÉCÉDENTE DU CODE : si le
  nouveau code échoue son healthcheck, l'ancienne version continue de servir sur
  le schéma déjà migré (ajout de colonne nullable : oui ; renommage ou
  suppression : en deux déploiements).

# Variables d'environnement (backend/.env, cf. .env.example)
- DATABASE_URL (SQLite ou PostgreSQL, cf. section ci-dessus)
- ACCESS_TOKEN_EXPIRE_MINUTES : FACULTATIVE, défaut 720 (12 h). Durée de vie du
  jeton de session (cf. section « Session JWT »). Valeur non entière ou négative
  → échec explicite au démarrage, jamais de repli silencieux sur le défaut.
- JWT_SECRET_KEY : obligatoire en dev ET en prod (clé DIFFÉRENTE en prod).
  Absente, l'app démarre mais toute connexion échoue (RuntimeError explicite).
- CORS_ORIGINS : origines autorisées, séparées par des virgules, SANS slash
  final. Défaut http://localhost:5173.
- FRONTEND_URL : base des liens emails (défaut http://localhost:5173)
- BREVO_API_KEY, BREVO_SENDER_EMAIL (adresse validée dans Brevo),
  BREVO_SENDER_NAME (optionnel) — absentes = mode DEV, aucun envoi.
- OBLIGATOIRES en production : DATABASE_URL, JWT_SECRET_KEY, CORS_ORIGINS,
  FRONTEND_URL, BREVO_API_KEY, BREVO_SENDER_EMAIL. Les défauts des trois
  variables d'URL pointent sur localhost : oubliées, l'app démarre SANS erreur
  mais le front est bloqué par CORS et les liens emails sont inutilisables.

# Versions des dépendances (figées volontairement)
- requirements.txt et requirements-dev.txt épinglent des versions EXACTES (`==`),
  pas des minimums (`>=`). Figées le 2026-07-21 à partir des versions réellement
  installées et testées. Objectif : STABILITÉ DE DÉPLOIEMENT — un rebuild Railway
  dans six mois installe exactement la même chose qu'aujourd'hui. Avec des `>=`,
  un rebuild sans le moindre commit pouvait tirer une version majeure
  incompatible (FastAPI 1.0, SQLAlchemy 2.1…) et casser la prod sans prévenir.
- CONTREPARTIE ASSUMÉE : plus aucun correctif de sécurité n'arrive tout seul.
  Ces versions doivent être relevées À LA MAIN de temps en temps (tous les 2-3
  mois, ou dès qu'une CVE touche une de ces briques). Ce n'est pas optionnel :
  un pin oublié pendant deux ans est un risque de sécurité, pas une garantie.
- Procédure de mise à jour :
  1. `.venv\Scripts\python.exe -m pip install --upgrade <paquet>`
  2. `.venv\Scripts\python.exe -m pytest` — la suite doit rester au vert
  3. reporter la nouvelle version dans le fichier concerné, et mettre à jour la
     date « figées le … » en tête de requirements.txt
  4. déployer et vérifier /health avant de considérer la mise à jour faite
- Points de vigilance sur deux pins :
  - `bcrypt==4.0.1` : passlib 1.7.4 lit `bcrypt.__about__.__version__`, attribut
    SUPPRIMÉ en bcrypt 4.1. Ne pas relever bcrypt sans vérifier ce point (c'est
    l'ancienne borne `bcrypt<4.1`, désormais exprimée par un pin exact).
  - Les extras (`uvicorn[standard]`, `pydantic[email]`, `psycopg[binary]`,
    `passlib[bcrypt]`) n'apparaissent PAS dans `pip freeze`. Ne JAMAIS écraser
    requirements.txt avec un copier-coller de `pip freeze` : les extras seraient
    perdus et le déploiement casserait (pydantic sans email-validator ne démarre
    pas, psycopg sans [binary] tente une compilation C).
- Seules les dépendances DIRECTES sont épinglées ; les dépendances transitives
  (starlette, pydantic-core, anyio…) restent résolues par pip. C'est délibéré :
  un `pip freeze` complet fait sous Windows n'est PAS portable vers le conteneur
  Linux (il omet uvloop, que uvicorn[standard] installe uniquement hors Windows,
  et inclut colorama). Un verrou transitif complet devrait être généré pour la
  plateforme cible (pip-compile/uv avec `--python-platform linux`, ou depuis le
  conteneur) — à faire si une dépendance transitive casse un jour un build.

# Déploiement (Railway)
- Le backend vit dans `backend/`, pas à la racine : le service Railway doit
  avoir son **Root Directory réglé sur `backend`**, sinon ni requirements.txt ni
  railway.json ne sont trouvés. C'est le réglage qu'on oublie en premier.
- `backend/railway.json` porte la config de déploiement (préféré au Procfile :
  il exprime aussi le healthcheck et la politique de redémarrage) :
  - startCommand : `uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}`.
    Sans `--reload` (dev uniquement : il surveille les fichiers et redémarre).
    `0.0.0.0` et non 127.0.0.1, sinon le conteneur n'accepte aucune connexion
    venue de l'extérieur. `$PORT` est injecté par Railway et doit être respecté.
  - preDeployCommand `alembic upgrade head` : migre la base avant le démarrage
    (cf. plus bas). `alembic` est appelé nu, comme `uvicorn` : trouvé sous
    Nixpacks, confirmé au premier déploiement.
  - healthcheckPath `/health` : Railway attend que l'app réponde avant de
    basculer le trafic — pas de fenêtre d'erreurs au redémarrage.
- `backend/.python-version` épingle Python 3.13 (version de dev). Si le log de
  build montre une autre version, le repli est `runtime.txt` ou la variable
  NIXPACKS_PYTHON_VERSION.
- La base PostgreSQL est un service Railway séparé ; référencer
  `DATABASE_URL=${{Postgres.DATABASE_URL}}` plutôt que copier l'URL en dur.
- Migrations : `preDeployCommand` (`alembic upgrade head`, dans railway.json)
  s'exécute UNE fois par déploiement, avant le démarrage du nouveau conteneur.
  Si elle échoue, le déploiement est en échec et l'ANCIENNE version continue de
  servir ; PostgreSQL exécute le DDL en transaction, donc une migration en échec
  est annulée en bloc (base inchangée). Pas dans startCommand : cela
  s'exécuterait à chaque redémarrage et réplica, et `restartPolicyType:
  ON_FAILURE` (10 essais) rejouerait dix fois la même erreur.
- /health reste un test de vie et n'interroge PAS la base ni alembic_version :
  le coupler ferait tomber le service pour des raisons étrangères au schéma.
- Ordre de mise en place (fait le 2026-09-25) : la prod a été marquée
  `alembic stamp 0001` AVANT le premier déploiement contenant le pre-deploy.
  Sinon `upgrade head` aurait tenté de recréer des tables existantes (échec sans
  gravité mais déploiement rouge). Une NOUVELLE base (autre environnement) n'a
  pas besoin de stamp : `upgrade head` la construit.

# Architecture frontend
- `api/` centralise les appels backend. TOUS passent par `apiFetch`
  (api/client.js), qui ajoute le Bearer et purge le token sur 401.
  Jamais de `fetch` direct dans un composant.
- Seul `auth/token.js` accède à localStorage (clé cockpit_token).
- Contexte d'auth (auth/) : état isAuthenticated, login/logout, plus `user`
  (chargé via GET /auth/me dès qu'un token existe, rechargeable par refreshUser).
  `user` peut être null même connecté (chargement, ou /auth/me en échec) : son
  absence ne bloque JAMAIS l'app, elle masque seulement le bandeau de vérification.
- Routes protégées (ProtectedRoute) et routes invité (GuestRoute). Les pages
  atteintes depuis un lien email (/forgot-password, /reset-password,
  /verify-email) n'ont AUCUNE garde : le token de l'URL fait autorité, pas la
  session — un connecté qui clique son lien de vérification ne doit pas être
  redirigé.
- `constants/applicationStatuses.js` = source unique des statuts (clé technique
  + libellé français + ordre des colonnes). Miroir exact de l'enum
  `ApplicationStatus` côté backend : toute évolution se fait des deux côtés
  (5 statuts depuis le retrait de « rejected »). Pour RETIRER un statut, le front
  passe en premier (cf. « Migrations », ordre de déploiement).
- Cartes du kanban : la carte entière est cliquable et ouvre la modale
  d'édition. Aucune action n'est affichée sur la carte. Le titre reste un lien
  vers l'offre (stopPropagation), sans style de lien. Le drag & drop
  (@dnd-kit) est pointeur uniquement : vérifier qu'un ajout d'élément
  interactif sur une carte ne le perturbe pas.
- URL du backend : `VITE_API_BASE_URL` (cf. frontend/.env.example), lue dans
  api/client.js avec repli `http://127.0.0.1:8000`. Le « / » final est retiré,
  les endpoints étant concaténés directement.

# Variables Vite : injectées au BUILD, pas au runtime
- Différence FONDAMENTALE avec le backend, qui lit `os.getenv` au démarrage et
  qu'il suffit donc de redémarrer : Vite ne lit pas d'environnement dans le
  navigateur (il n'y en a pas). `npm run build` REMPLACE textuellement chaque
  `import.meta.env.VITE_X` par sa valeur littérale dans le bundle. Le JS livré
  contient l'URL en dur ; il n'existe plus aucune variable à l'exécution.
- Conséquences pour le déploiement :
  - `VITE_API_BASE_URL` doit être définie AU MOMENT DU BUILD (variable du
    service front sur Railway, pas du service backend).
  - Changer l'URL de l'API impose de REBUILDER et redéployer le front.
    Redémarrer le conteneur ne change rien : le bundle est déjà figé.
  - Une variable ajoutée après coup dans le dashboard n'a AUCUN effet tant
    qu'aucun build n'a été relancé — symptôme classique : le front déployé
    continue d'appeler 127.0.0.1:8000 et échoue chez tous les utilisateurs.
  - Tout ce qui est préfixé VITE_ est PUBLIC (lisible dans le bundle) : jamais
    de secret. Les secrets restent côté backend.

# Règles
- Toujours valider les entrées API avec des modèles Pydantic.
- Jamais de secrets en dur : tout passe par les variables d'environnement
  (.env backend, VITE_ pour le front).
- Installer les dépendances Python UNIQUEMENT via
  `.venv\Scripts\python.exe -m pip install -r requirements-dev.txt`
  (chemin explicite, ne jamais utiliser `py` ni `pip` nus).
  Une dépendance nécessaire EN PRODUCTION va dans requirements.txt ; une
  dépendance de test uniquement va dans requirements-dev.txt. Toute nouvelle
  dépendance s'ajoute avec une version EXACTE (==), cf. section ci-dessus.
- Style backend : type hints partout, docstrings en français, code en anglais.
- Commits en anglais, format conventional commits (feat:, fix:, docs:...).
- Ne pas ajouter de dépendance sans la justifier dans le message de commit.
- Toute modification de style suit DESIGN.md (cf. « Direction visuelle »).

# Roadmap V1
1. [fait] CRUD candidatures + extension navigateur (extraction générique + JSON-LD)
2. [fait] Auth JWT multi-utilisateurs (inscription, login, protection, ownership)
3. Front React
   - [fait] Setup Vite + structure
   - [fait] Couche API + contexte d'auth
   - [fait] Écrans Login/Register + routes protégées
   - [fait] Kanban en lecture seule
   - [fait] Création / édition / suppression de candidatures (modale)
   - [fait] Drag & drop des cartes entre colonnes
   - [fait] Champ statut dans le formulaire, en mode édition uniquement
4. Reconnecter l'extension à l'auth (elle ne peut plus créer sans token)
5. Multi-tableaux (Boards)
   - [fait] Backend : modèle Board, CRUD, ownership en chaîne, board par défaut,
     dernier tableau non supprimable, cascade
   - [fait] Front : sélection/gestion des tableaux, board_id à la création
6. Design du site (en cours)
   - [fait] DESIGN.md : direction visuelle, échelle typo, espacements, couleur
   - [fait] Refonte du kanban : densité, carte cliquable, tokens, contrastes
   - [à faire] Reste de l'application (landing, formulaires, page compte)
7. Mot de passe oublié + vérification d'email (Brevo)
   - [fait] Backend : app/email.py, SecurityToken, 4 endpoints, rate limiting
   - [fait] Front : écrans /forgot-password, /reset-password, /verify-email
     (routes PUBLIQUES, sans garde) + bandeau "confirmez votre adresse"
     (is_verified via GET /auth/me) avec renvoi de l'email
8. Déploiement (backend + PostgreSQL sur Railway)
9. Archivage des candidatures (en cours)
   - [fait, backend, écrit et testé, à déployer] Champ archived_at (migration
     0003), statut conservé à l'archivage, endpoints /archive et /unarchive,
     plafond de 2000 archivées, plafond de 300 actives au désarchivage,
     correction du comptage des 300 (n'exclut plus les archivées à tort),
     filtre ?archived= par défaut sur les listes, compteurs sur BoardRead
   - [à faire] Page d'archives au niveau du compte, filtre par tableau, tri par
     date, confirmation de suppression d'un tableau annonçant le nombre
     d'archives concernées (frontend)
   - Suppression du statut "Refusée" : front (2a) [fait, déployé] ; migration
     0002 + backend (2b) [écrits et testés, à déployer]. Reste le texte
     « Refusée » de la landing, du README et de commentaires (lot 7)

# Hors périmètre V1 (ne pas implémenter sans demande explicite)
- Agrégation API officielles (La Bonne Alternance, France Travail) → V1.5
- Formulaire de correction dans l'extension → V2
- Alertes email, statistiques, paiement, publication Web Store → V2
- Connexion Google, refresh tokens, UUID → V3
