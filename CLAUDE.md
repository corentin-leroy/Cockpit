# Cockpit

SaaS de suivi de candidatures, tous types de contrats : CRM kanban (cœur du
produit) + extension navigateur pour l'ajout d'offres depuis n'importe quel site.
Agrégation via API officielles (La Bonne Alternance, France Travail) reportée
en V1.5. AUCUN scraping serveur, AUCUN stockage de credentials de sites tiers.

# Stack
- Backend : FastAPI + SQLAlchemy 2.0 + SQLite (dev/tests) ou PostgreSQL (prod)
- Frontend : React 19 + Vite + React Router 7 (dossier frontend/)
- Extension : Chrome Manifest V3 (dossier extension/)
- Environnement : Windows/PowerShell, Python invoqué avec `py`

# Commandes
Backend (depuis backend/, venv activé) :
- Installer : `.venv\Scripts\python.exe -m pip install -r requirements-dev.txt`
  (requirements-dev.txt inclut requirements.txt + pytest/httpx ; la PRODUCTION
  n'installe que requirements.txt)
- Lancer l'API : `py -m uvicorn app.main:app --reload`
- Tests : `py -m pytest` (depuis backend/) — suite ciblée sécurité (auth,
  ownership). Base SQLite EN MÉMOIRE isolée, recréée à chaque test ; ne touche
  jamais cockpit.db et n'envoie aucun email (Brevo forcé en mode DEV dans
  tests/conftest.py). Voir « Tests backend » plus bas.
Frontend (depuis frontend/) :
- Installer : `npm install`
- Lancer : `npm run dev` (http://localhost:5173)
- Build : `npm run build` ; Lint : `npm run lint`

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
  au current_user (sinon 404). GET /applications filtre par ?board_id= et/ou
  ?status_filter=.
- Le statut d'une candidature n'est PAS modifiable à la création (démarre
  toujours en "saved"/Repérée) ; il évolue via PATCH (drag & drop côté front).

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
- ⚠ CHANGEMENT DE SCHÉMA : `create_all()` ne MODIFIE JAMAIS une table existante.
  Ces contraintes ONLY apparaissent sur des tables CRÉÉES après ce changement.
  Sur une base déjà en place (dev : backend/cockpit.db ; prod : PostgreSQL
  Railway), les tables gardent leurs anciennes FK sans cascade, et rien ne le
  signale. En dev, supprimer cockpit.db suffit (elle est recréée au démarrage).
  En prod, il faut recréer les tables — ou, mieux, passer à Alembic : c'est
  exactement la première modification de schéma qui justifie de l'installer.

# Limites de quantité (garde-fous anti-abus)
- Toutes les constantes sont dans `app/limits.py` (source unique, importée par
  les routers et par main.py) :
  - MAX_BOARDS_PER_USER = 10
  - MAX_APPLICATIONS_PER_USER = 300
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

# Tests backend (backend/tests/, `py -m pytest`)
- Portée VOLONTAIREMENT ciblée : la matrice sécurité déjà validée manuellement
  (auth + ownership) et les garde-fous anti-abus, pas une couverture exhaustive.
  On teste les points où une régression serait silencieuse et coûteuse (fuite du
  mot de passe, perte de l'anti-énumération, cloisonnement par user, plafonds).
- Fichiers : `test_auth.py`, `test_boards_ownership.py`,
  `test_applications_ownership.py`, `test_limits.py`,
  `test_account_deletion.py`.
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
  jetable pour que le create_all à l'import ne touche pas cockpit.db, (b)
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
  l'identité. Un token peut fuiter et vit 60 min ; il autorise des actions
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
- `Base.metadata.create_all()` (main.py) crée les tables manquantes mais ne
  MIGRE rien : il ignore les tables déjà présentes dont le schéma a changé.
  Suffisant pour un premier déploiement, à remplacer par Alembic dès la
  première modification de schéma en prod.

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
  2. `py -m pytest` — la suite doit rester au vert
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
  - healthcheckPath `/health` : Railway attend que l'app réponde avant de
    basculer le trafic — pas de fenêtre d'erreurs au redémarrage.
- `backend/.python-version` épingle Python 3.13 (version de dev). Si le log de
  build montre une autre version, le repli est `runtime.txt` ou la variable
  NIXPACKS_PYTHON_VERSION.
- La base PostgreSQL est un service Railway séparé ; référencer
  `DATABASE_URL=${{Postgres.DATABASE_URL}}` plutôt que copier l'URL en dur.
- `Base.metadata.create_all()` crée les tables au premier démarrage, mais ne
  MIGRE rien (cf. section base de données) : Alembic dès le premier changement
  de schéma en prod.

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
- `constants/applicationStatuses.js` = source unique des 6 statuts
  (clé technique + libellé français + ordre des colonnes).
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
  (chemin explicite, ne jamais utiliser `py` ni `pip` nus pour installer).
  Une dépendance nécessaire EN PRODUCTION va dans requirements.txt ; une
  dépendance de test uniquement va dans requirements-dev.txt. Toute nouvelle
  dépendance s'ajoute avec une version EXACTE (==), cf. section ci-dessous.
- Style backend : type hints partout, docstrings en français, code en anglais.
- Commits en anglais, format conventional commits (feat:, fix:, docs:...).
- Ne pas ajouter de dépendance sans la justifier dans le message de commit.

# Roadmap V1
1. [fait] CRUD candidatures + extension navigateur (extraction générique + JSON-LD)
2. [fait] Auth JWT multi-utilisateurs (inscription, login, protection, ownership)
3. Front React (en cours)
   - [fait] Setup Vite + structure
   - [fait] Couche API + contexte d'auth
   - [fait] Écrans Login/Register + routes protégées
   - [fait] Kanban en lecture seule
   - [fait] Création / édition / suppression de candidatures (modale)
   - [fait] Drag & drop des cartes entre colonnes
4. Reconnecter l'extension à l'auth (elle ne peut plus créer sans token)
5. Multi-tableaux (Boards)
   - [fait] Backend : modèle Board, CRUD, ownership en chaîne, board par défaut,
     dernier tableau non supprimable, cascade
   - [fait] Front : sélection/gestion des tableaux, board_id à la création
6. Faire le design du site 
7. Mot de passe oublié + vérification d'email (Brevo)
   - [fait] Backend : app/email.py, SecurityToken, 4 endpoints, rate limiting
   - [fait] Front : écrans /forgot-password, /reset-password, /verify-email
     (routes PUBLIQUES, sans garde) + bandeau "confirmez votre adresse"
     (is_verified via GET /auth/me) avec renvoi de l'email
8. Déploiement

# Hors périmètre V1 (ne pas implémenter sans demande explicite)
- Agrégation API officielles (La Bonne Alternance, France Travail) → V1.5
- Formulaire de correction dans l'extension → V2
- Alertes email, statistiques, paiement, publication Web Store → V2
- Connexion Google, refresh tokens, UUID → V3