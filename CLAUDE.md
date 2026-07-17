# Cockpit

SaaS de suivi de candidatures, tous types de contrats : CRM kanban (cœur du
produit) + extension navigateur pour l'ajout d'offres depuis n'importe quel site.
Agrégation via API officielles (La Bonne Alternance, France Travail) reportée
en V1.5. AUCUN scraping serveur, AUCUN stockage de credentials de sites tiers.

# Stack
- Backend : FastAPI + SQLAlchemy 2.0 + SQLite (PostgreSQL prévu en prod)
- Frontend : React 19 + Vite + React Router 7 (dossier frontend/)
- Extension : Chrome Manifest V3 (dossier extension/)
- Environnement : Windows/PowerShell, Python invoqué avec `py`

# Commandes
Backend (depuis backend/, venv activé) :
- Installer : `.venv\Scripts\python.exe -m pip install -r requirements.txt`
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
  d'un user est refusée (409). Supprimer un board supprime ses candidatures
  (cascade ORM all, delete-orphan).
- Créer une candidature exige un board_id ; le serveur vérifie qu'il appartient
  au current_user (sinon 404). GET /applications filtre par ?board_id= et/ou
  ?status_filter=.
- Le statut d'une candidature n'est PAS modifiable à la création (démarre
  toujours en "saved"/Repérée) ; il évolue via PATCH (drag & drop côté front).

# Tests backend (backend/tests/, `py -m pytest`)
- Portée VOLONTAIREMENT ciblée : la matrice sécurité déjà validée manuellement
  (auth + ownership), pas une couverture exhaustive. On teste les points où une
  régression serait silencieuse et coûteuse (fuite du mot de passe, perte de
  l'anti-énumération, cloisonnement par user).
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
- Anti-énumération : /auth/forgot-password renvoie TOUJOURS le même message, que
  le compte existe ou non — y compris quand le plafond d'envois est atteint (pas
  de 429, qui trahirait l'existence du compte). Même principe que le 401
  générique du login.
- Rate limiting des emails sortants : 3 par heure et par (utilisateur, usage),
  compté sur `security_tokens.created_at` — pas de compteur dédié, pas de Redis,
  et le plafond survit à un redémarrage. /auth/resend-verification, lui, est
  authentifié : il peut répondre explicitement 429.

# Variables d'environnement (backend/.env, cf. .env.example)
- DATABASE_URL, JWT_SECRET_KEY (déjà en place)
- FRONTEND_URL : base des liens emails (défaut http://localhost:5173)
- BREVO_API_KEY, BREVO_SENDER_EMAIL (adresse validée dans Brevo),
  BREVO_SENDER_NAME (optionnel) — absentes = mode DEV, aucun envoi.

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

# Règles
- Toujours valider les entrées API avec des modèles Pydantic.
- Jamais de secrets en dur : tout passe par les variables d'environnement
  (.env backend, VITE_ pour le front).
- Installer les dépendances Python UNIQUEMENT via
  `.venv\Scripts\python.exe -m pip install -r requirements.txt`
  (chemin explicite, ne jamais utiliser `py` ni `pip` nus pour installer).
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