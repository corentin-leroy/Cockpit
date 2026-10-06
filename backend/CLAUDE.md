# Backend (FastAPI + SQLAlchemy 2.0)
Chargé automatiquement dès qu'un fichier de `backend/` est lu ou modifié. Une règle
par point, avec sa raison. Le document en renvoi (`dev-docs/`) n'est PAS chargé
automatiquement : le lire AVANT de modifier le mécanisme concerné ; en cas d'écart,
il fait foi. Commandes : CLAUDE.md racine (toujours `.venv\Scripts\python.exe -m
...`, jamais `py` ni `pip` nus).

# Architecture backend
- `app/models.py` = tables SQLAlchemy ; `app/schemas.py` = contrats Pydantic.
  Ne jamais exposer un modèle ORM directement dans une réponse API.
- Un router par ressource dans `app/routers/` (auth, boards, applications).
- Ownership : cloisonné par user. Pour un board, filtre direct sur board.user_id
  (helper `get_owned_board` dans routers/boards.py, réutilisé par applications).
  Pour une candidature, jointure application → board et filtre sur board.user_id.
  Accès à la ressource d'autrui → 404 (pas 403), pour ne pas confirmer un id.
- À l'inscription, un board par défaut "Mes candidatures" est créé : un user a
  TOUJOURS au moins un tableau. Corollaire : la suppression du DERNIER tableau
  d'un user est refusée (409). Supprimer un board supprime ses candidatures.
- Créer une candidature exige un board_id ; le serveur vérifie qu'il appartient
  au current_user (sinon 404). GET /applications filtre par ?board_id=,
  ?status_filter= et/ou ?archived= (cf. « Archivage des candidatures »). Les
  actives sont renvoyées dans l'ORDRE DU KANBAN (cf. « Ordre des cartes du
  kanban »), plus par date de modification.
- Le statut d'une candidature n'est PAS modifiable à la création (démarre
  toujours en "saved"/Repérée). Il évolue ensuite par deux chemins : le
  glisser-déposer (POST /applications/{id}/move, qui choisit aussi le RANG dans
  la colonne) et le champ « statut » du formulaire (PATCH, arrivée EN HAUT de la
  colonne), affiché UNIQUEMENT en mode édition (jamais à la création).

# Ordre des cartes du kanban → `dev-docs/kanban-order.md`
- `Application.position` = rang dans la colonne (actives d'un même tableau et
  statut) : 0..n-1 sans trou ni doublon, 0 = en haut, NULL si archivée. Écrite
  UNIQUEMENT par routers/applications.py, jamais reçue du client ni exposée (le
  contrat, c'est l'ordre de la liste).
- Tri des actives : `position ASC NULLS FIRST, updated_at DESC, id DESC` (NULL =
  créée par l'ancien code pendant un déploiement : arrivée, donc en haut).
- Hors POST /move, toute entrée dans une colonne arrive EN HAUT (création, PATCH
  qui change réellement statut ou tableau, désarchivage). Le PATCH compare aux
  valeurs STOCKÉES : le formulaire renvoie toujours `status` et `board_id`.
- Quitter une colonne la compacte ; un PATCH sur une archivée ne touche aucune
  position. /move : rang au-delà de la fin → fin de colonne (pas un 422),
  archivée → 409, aucun contrôle de plafond.
- Entrée ou sortie → renumérotation de TOUTE la colonne dans l'ordre affiché
  (elle se répare d'elle-même) ; les voisines gardent leur `updated_at` (les
  décaler n'est pas les modifier).
- `_lock_positions_of` AVANT toute lecture, verrou par UTILISATEUR (par tableau,
  deux requêtes s'interbloqueraient). Aucune contrainte en base sur `position`
  (décision validée : l'ancien code écrit sans position pendant un déploiement).

# Cascade de suppression → `dev-docs/deletion-cascade.md`
- Garder les DEUX niveaux : `ondelete="CASCADE"` sur chaque ForeignKey (la base
  protège tous les chemins) ET `cascade="all, delete-orphan"` +
  `passive_deletes=True` sur les relations (sémantique orphelin, un seul DELETE).
- L'écouteur `PRAGMA foreign_keys=ON` (app/database.py, sur la CLASSE `Engine`)
  est indispensable : sans lui, SQLite ignore les FK, cascade décorative en test.

# Plafonds de quantité → `dev-docs/quantity-limits.md`
- Constantes dans `app/limits.py` (source unique), vérifiées CÔTÉ SERVEUR (le
  front ne fait pas autorité) ; dépassement → 409, et rien n'est créé.
- 300 ACTIVES par utilisateur, tous tableaux confondus ; 2000 archivées, contrôlées
  à l'archivage ; désarchivage plafonné par les 300 (sinon contournement).
  Déplacer (PATCH board_id, /move) ne contrôle rien : le total ne change pas.
- Corps : 413 sur Content-Length (`BodySizeLimitMiddleware`) ; garde-fou
  autoritaire en prod = reverse proxy ; pas de comptage à la volée (double envoi).

# Archivage → `dev-docs/archiving.md`
- `archived_at` posé par le SERVEUR via POST /archive et /unarchive, jamais par
  PATCH ; le statut n'est jamais modifié. Action redondante → 409 explicite (une
  idempotence silencieuse masquerait un bug client).
- Listes : archivées exclues par défaut. `_visible_applications_query` n'a
  volontairement PAS de défaut pour `archived` : l'oubli lève une TypeError.
- Accès par identifiant (GET/PATCH/DELETE /applications/{id}) NON filtré par
  `archived_at` : la correction depuis la page d'archives en dépend.

# Validation des entrées → `dev-docs/input-validation.md`
- Aucune entrée client ne produit un 500 : 422 AVANT la base (SQLite laisse passer
  longueurs et NUL que PostgreSQL refuse). Bornes dans `app/limits.py`, jamais
  au-delà de la colonne de models.py (testé).
- Schémas d'entrée : héritent d'`InputModel` (NUL et surrogate isolé refusés,
  jamais nettoyés en silence), mêmes types en création et modification. Champs
  email : `NormalizedEmail` (`lower()`, pas `casefold()`), jamais via `'*'` (il
  toucherait les mots de passe).
- Mot de passe CHOISI : 8 caractères à 72 OCTETS (bcrypt tronque au-delà) ;
  PRÉSENTÉ (login, suppression) : 4096 octets, jamais 72 (comptes existants).
- PATCH : `null` refusé sur les champs NOT NULL (omettre pour ne pas modifier).
  Identifiants 1..2147483647 (`IdPath`, `IdQuery`, `RowId`) : 0 → 422, pas 404.
- `applied_at` : UTC naïf borné 1900..2100 (hors plage, la liste devenait
  illisible sous PostgreSQL). Inscription concurrente : sur `IntegrityError`,
  relire l'email ; 409 si le compte existe, sinon 500 visible, jamais déguisé.
- Avant de changer ces règles : sonder un PostgreSQL 18 jetable, pas seulement
  SQLite. Connus, non traités (lot séparé) : `javascript:` en URL, espaces seuls,
  saturation du pool pendant bcrypt.

# Messages d'erreur → `dev-docs/error-messages.md`
- Rédigés par le BACKEND, en français, catalogue unique `app/error_messages.py` :
  `schemas.py` dit QUOI a échoué, le catalogue COMMENT ; les clients ne traduisent pas.
- `detail` est TOUJOURS une chaîne ; sur un 422, `errors` liste `{field, message}`,
  `field` seulement pour un champ soumis. Validateur personnalisé :
  `PydanticCustomError` à code stable, jamais un `ValueError` nu.
- `FIELD_LABELS` au singulier, complet, chaque type du catalogue exercé par un
  test (gardes). `get_current_user` teste `token is None` AVANT
  `decode_access_token` (`auto_error=False`, sinon 500) ; le gestionnaire de 500
  ne renvoie jamais le texte de l'exception.

# Limites de débit → `dev-docs/rate-limiting.md`
- Login 60/min par IP et 5 échecs/15 min par couple (IP, email) ; inscription
  20/h et mot de passe oublié 10/h par IP (`limits.py`). Tout AVANT bcrypt, sinon
  le serveur n'est pas protégé.
- Couple et non l'email seul (sinon on bloquerait le compte d'autrui) ; compteur
  incrémenté pareil que le compte existe ou non (anti-énumération).
- 429 + `Retry-After` en secondes entières, qui reste dans `expose_headers`
  (CORS : sinon le front ne voit pas le délai).
- Compteurs EN MÉMOIRE : une seule instance (ni `--workers`, réplicas = 1), sinon
  compteurs partagés, même interface que `SlidingWindowCounter`. Au plafond de
  clés, oublier la moins récente, ne JAMAIS refuser une nouvelle clé (on
  bloquerait tout le monde en remplissant la table).
- IP (`client_ip.py`) : N-ième entrée de X-Forwarded-For EN PARTANT DE LA DROITE
  (`TRUSTED_PROXY_COUNT`, 2 sur Railway) ; jamais celle de gauche ni `Forwarded`
  (falsifiables) ; jamais FORWARDED_ALLOW_IPS (uvicorn lirait la gauche). Après
  un changement d'infrastructure : refaire la vérification en 6 étapes.

# Emails et jetons → `dev-docs/emails-and-tokens.md`
- `app/email.py`, SEULE frontière avec Brevo (sans BREVO_API_KEY : mode DEV, lien
  logué). `SecurityToken` : SHA-256, jamais le clair ; toujours filtrer sur
  `purpose` (un lien de vérification ne réinitialise jamais un mot de passe).
- `_consume_token` : UN UPDATE conditionnel ... RETURNING, PREMIÈRE instruction
  de la transaction ; jamais SELECT puis test en Python (plusieurs requêtes
  passaient), ni `FOR UPDATE` (ignoré par SQLite).
- Vérification d'email non bloquante ; un reset réussi passe `is_verified` à True.
  3 emails/h par (utilisateur, usage), SILENCIEUX sur /auth/forgot-password (un
  429 trahirait l'existence du compte).

# Session et suppression de compte → `dev-docs/jwt-session.md`, `dev-docs/account-deletion.md`
- JWT de 12 h (`ACCESS_TOKEN_EXPIRE_MINUTES`, seule source dans app/security.py),
  sans état donc irrévocable : ne PAS allonger sans refresh tokens (V3).
- DELETE /auth/me efface tout par cascade et exige le mot de passe courant (le JWT
  prouve la session, pas l'identité) ; faux → 403, pas 401 (un 401 ferait purger
  un token valide côté front).

# Base de données et migrations → `dev-docs/database.md`, `dev-docs/migrations.md`
- Même code SQLite et PostgreSQL : ce qui dépend du moteur reste dans
  `app/database.py`. psycopg v3 (`postgresql+psycopg`), jamais psycopg2
  (`normalize_database_url()` réécrit `postgres://` et `postgresql://`).
- DateTime naïfs en UTC via `utcnow()`, `default`/`onupdate` compris (un datetime
  « aware » donnerait des heures différentes selon le moteur). Enums stockés par
  NOM de membre (`APPLIED`) : à retenir en SQL manuel.
- Empoisonnement de session écarté (2026-09-26) : ne pas refaire ce diagnostic.
- models.py modifié → migration dans le même lot (test_migrations.py échoue
  sinon), autogénérée PUIS relue ; valeurs EN DUR (état figé), jamais importées
  de app.models ni de limits.py ; compatible avec la version précédente du code
  (renommage ou suppression : en deux déploiements).
- Retirer une valeur d'enum : procédure de la 0002, front déployé d'abord.
  `alembic check` ne voit pas les libellés : test à la main sur PostgreSQL 18.
- Viser la prod : `$env:DATABASE_URL` dans la session shell seulement, retirée
  ensuite ; lire `[alembic] cible : ...` avant toute écriture.

# Variables, dépendances, déploiement → `dev-docs/environment-variables.md`, `dev-docs/dependencies.md`, `dev-docs/deployment-railway.md`
- Obligatoires en prod : DATABASE_URL, JWT_SECRET_KEY, CORS_ORIGINS, FRONTEND_URL,
  BREVO_API_KEY, BREVO_SENDER_EMAIL, TRUSTED_PROXY_COUNT (oubliées, l'app démarre
  mais casse). Valeur invalide → échec au démarrage, jamais de repli silencieux.
- Versions EXACTES (`==`), relevées à la main tous les 2-3 mois (suite au vert,
  date « figées le » mise à jour) ; jamais de `pip freeze` collé (extras perdus,
  build cassé) ; `bcrypt==4.0.1` figé (passlib 1.7.4 lit un attribut supprimé en
  4.1 ; bcrypt 5 lève au-delà de 72 octets).
- Railway : Root Directory = `backend`, config dans `railway.json` ; migrations en
  `preDeployCommand`, jamais en `startCommand` (rejouées à chaque redémarrage et
  réplica) ; `/health` n'interroge ni la base ni alembic_version ; en prod ni
  `--reload` ni `--workers`, hôte `0.0.0.0`, port `$PORT`.

# Tests → `dev-docs/backend-tests.md`
- Portée volontairement ciblée : sécurité, ownership, garde-fous anti-abus,
  courses (là où une régression serait silencieuse).
- `tests/conftest.py` force SQLite en mémoire, Brevo en mode DEV et une clé JWT de
  test (jamais cockpit.db, jamais d'email réel), remet les compteurs de débit à
  zéro avant chaque test (fixture autouse), horloge factice `clock`. Fixtures :
  `client`, `db_session`, `make_user`, `make_board`, `make_application`.
- Courses (`*_race.py`) : SQLite FICHIER (la base en mémoire à connexion unique
  ne permet pas de vraie concurrence). Cascade, positions, plafonds : assertions
  sur l'ÉTAT STOCKÉ ; remplissage par insertion directe en base, pas par des POST.
