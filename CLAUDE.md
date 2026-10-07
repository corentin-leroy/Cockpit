# Cockpit

SaaS de suivi de candidatures, tous types de contrats : CRM kanban (cœur du
produit) + extension navigateur pour l'ajout d'offres depuis n'importe quel site.
AUCUN scraping serveur, AUCUN stockage de credentials de sites tiers.

# Où trouver quoi
- Ce fichier est chargé à CHAQUE session : il ne garde que ce qui vaut pour toute
  tâche. Les règles d'une partie du code sont dans `backend/CLAUDE.md`,
  `frontend/CLAUDE.md` et `extension/CLAUDE.md`. Claude Code les charge quand un
  fichier de leur dossier est lu ou modifié (Read, Write, Edit), PAS sur une
  simple recherche (Grep, Glob, `cat`) : avant de modifier un dossier, en lire un
  fichier suffit à charger ses règles.
- `dev-docs/` : justifications, mesures, diagnostics, listes de mutations,
  historique. JAMAIS chargé automatiquement : l'ouvrir quand une règle y renvoie,
  et TOUJOURS avant de modifier le mécanisme qu'il décrit. Si une règle courte et
  son document divergent, le document fait foi.
- Les renvois « cf. « Titre » » des documents citent un titre de section
  d'origine : l'index plus bas donne le fichier correspondant.
- ⚠ Jamais de documentation interne dans `docs/` : ce dossier est publié par
  GitHub Pages (politique de confidentialité), tout ce qui y entre devient public.

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
  mode DEV dans tests/conftest.py). Voir « Tests » dans `backend/CLAUDE.md`.
Frontend (depuis frontend/) :
- Installer : `npm install`
- Lancer : `npm run dev` (http://localhost:5173)
- Build : `npm run build` ; Lint : `npm run lint`

# Conventions
- Toujours valider les entrées API avec des modèles Pydantic.
- Jamais de secrets en dur : tout passe par les variables d'environnement
  (.env backend, VITE_ pour le front).
- Installer les dépendances Python UNIQUEMENT via
  `.venv\Scripts\python.exe -m pip install -r requirements-dev.txt`
  (chemin explicite, ne jamais utiliser `py` ni `pip` nus).
  Une dépendance nécessaire EN PRODUCTION va dans requirements.txt ; une
  dépendance de test uniquement va dans requirements-dev.txt. Toute nouvelle
  dépendance s'ajoute avec une version EXACTE (==), cf. `dev-docs/dependencies.md`.
- Style backend : type hints partout, docstrings en français, code en anglais.
- Commits en anglais, format conventional commits (feat:, fix:, docs:...).
- Ne pas ajouter de dépendance sans la justifier dans le message de commit.
- Toute modification de style suit DESIGN.md (cf. « Direction visuelle »).

# Hiérarchie des données
- Hiérarchie des données : User → Boards → Applications.
  - Un Board (tableau kanban) appartient à un User (board.user_id).
  - Une Application appartient à un Board (application.board_id). Elle ne porte
    PLUS de user_id : le propriétaire se déduit en chaîne (application → board →
    user), pour éviter toute redondance.

# Règles critiques
Une ligne par règle, sa raison en quelques mots ; le détail est dans le renvoi.
Données et sécurité :
- Ressource d'autrui → 404, jamais 403 (ne pas confirmer un id) ; une candidature
  appartient à son user par la chaîne application → board → user. → `backend/CLAUDE.md`
- Jamais de modèle ORM dans une réponse API : toujours un schéma Pydantic. → `backend/CLAUDE.md`
- Aucune entrée client ne doit produire un 500 : refus en 422 AVANT la base
  (SQLite laisse passer ce que PostgreSQL refuse). → `dev-docs/input-validation.md`
- Schéma d'entrée = `InputModel` ; champ email = `NormalizedEmail` (des tests
  gardent l'oubli). → `dev-docs/input-validation.md`
- Anti-énumération : login, mot de passe oublié et 429 répondent pareil, que le
  compte existe ou non. → `dev-docs/rate-limiting.md`
- IP du client : jamais la valeur de GAUCHE de X-Forwarded-For (falsifiable) ;
  ne JAMAIS poser FORWARDED_ALLOW_IPS. → `dev-docs/rate-limiting.md`
- Compteurs de débit en mémoire : UNE seule instance (ni `--workers`, ni
  réplicas), sinon les seuils sont multipliés. → `dev-docs/rate-limiting.md`
- Plafonds (10 tableaux, 300 actives, 2000 archivées, corps de 1 Mo) vérifiés
  côté SERVEUR ; dépassement → 409, rien n'est créé. → `dev-docs/quantity-limits.md`
- Jetons de sécurité : SHA-256 en base, consommés par UN UPDATE conditionnel
  (usage unique même en concurrence). → `dev-docs/emails-and-tokens.md`
- Session JWT de 12 h, irrévocable : ne pas l'allonger sans refresh tokens. → `dev-docs/jwt-session.md`
- Supprimer un compte exige le mot de passe (le JWT ne prouve que la session) ;
  faux → 403, pas 401. → `dev-docs/account-deletion.md`
- Jamais de secret en dur ; tout `VITE_*` est public. → `frontend/CLAUDE.md`
Schéma, base, déploiement :
- Toute modification de models.py : migration Alembic dans le même lot ;
  `alembic check` ne voit PAS les libellés d'enum. → `dev-docs/migrations.md`
- Une migration reste compatible avec la version précédente du code (elle sert
  encore pendant le déploiement). → `dev-docs/migrations.md`
- Même code sur SQLite et PostgreSQL : ce qui dépend du moteur reste dans
  `app/database.py`. → `dev-docs/database.md`
- DateTime naïfs en UTC via `utcnow()`, jamais « aware » (les deux moteurs
  écriraient des heures différentes). → `dev-docs/database.md`
- Viser la prod depuis le poste : `$env:DATABASE_URL` dans la session seulement,
  jamais dans .env ; lire `[alembic] cible` avant d'écrire. → `dev-docs/migrations.md`
- Versions épinglées en `==` ; jamais de `pip freeze` collé (extras perdus) ;
  ne pas relever bcrypt 4.0.1. → `dev-docs/dependencies.md`
Kanban :
- Positions écrites UNIQUEMENT par routers/applications.py, après le verrou
  `_lock_positions_of` ; hors /move, une carte arrive EN HAUT. → `dev-docs/kanban-order.md`
- L'archivage ne change jamais le statut ; les listes excluent les archivées
  par défaut. → `dev-docs/archiving.md`
Frontend, style, extension :
- Lire DESIGN.md avant tout CSS ; une modification de `tokens.css` se répercute
  dans `extension/popup.html` (sauf `--color-surface-band` et
  `--color-surface-column`). → `frontend/CLAUDE.md`
- Appels API via `apiFetch` uniquement ; localStorage via son module dédié
  uniquement. → `frontend/CLAUDE.md`
- Statuts : `constants/applicationStatuses.js` = miroir exact de l'enum backend ;
  pour en retirer un, le front passe en premier. → `dev-docs/migrations.md`
- Extension : URL de l'API figée, jamais configurable (canal d'exfiltration du
  token). → `extension/CLAUDE.md`

# Index de la documentation
CLAUDE.md par dossier (chargés automatiquement, cf. « Où trouver quoi ») :
- `backend/CLAUDE.md` : architecture backend et règles opérationnelles (ordre des
  cartes, cascade, plafonds, archivage, validation, messages d'erreur, limites de
  débit, emails et jetons, session, base, migrations, variables
  d'environnement, dépendances, déploiement, tests).
- `frontend/CLAUDE.md` : direction visuelle, architecture frontend, glisser-déposer,
  landing, blocage après un 429, suppression de compte, variables Vite.
- `extension/CLAUDE.md` : extension Chrome (URL figée, tokens de la popup,
  bornes, adaptateurs France Travail et Indeed).
`dev-docs/` (à la demande ; entre guillemets, le titre d'origine cité par les
renvois « cf. ») :
- `kanban-order.md` : « Ordre des cartes du kanban »
- `deletion-cascade.md` : « Cascade de suppression »
- `quantity-limits.md` : « Limites de quantité »
- `rate-limiting.md` : « Limites de débit »
- `archiving.md` : « Archivage des candidatures »
- `input-validation.md` : « Validation des entrées » (dont « Saturation du pool »)
- `error-messages.md` : messages d'erreur, extraits de « Validation des entrées »
- `backend-tests.md` : « Tests backend »
- `emails-and-tokens.md` : « Emails, reset de mot de passe et vérification »
- `jwt-session.md` : « Session JWT »
- `account-deletion.md` : « Suppression de compte »
- `database.md` : « Base de données »
- `migrations.md` : « Migrations »
- `environment-variables.md` : « Variables d'environnement »
- `dependencies.md` : « Versions des dépendances »
- `deployment-railway.md` : « Déploiement (Railway) »
- `frontend-kanban-dnd.md` : glisser-déposer, extrait de « Architecture frontend »
- `landing-page.md` : landing, extraite de « Architecture frontend »
- `rate-limit-cooldown.md` : « Blocage après un 429 », extrait de « Architecture frontend »
- `vite-build-variables.md` : « Variables Vite »
- `roadmap.md` : historique de la feuille de route (« Roadmap V1 »)
« Direction visuelle » et « Architecture frontend » (hors extraits ci-dessus) :
`frontend/CLAUDE.md`. « Architecture backend » : `backend/CLAUDE.md`.

# Feuille de route : en cours et à faire
Seuls les points OUVERTS figurent ici ; l'historique des lots terminés (dates,
commits, vérifications) est dans `dev-docs/roadmap.md`. Un point terminé quitte
cette liste et rejoint l'historique : jamais de statut tenu aux deux endroits.
- Extension : republication sur le Chrome Web Store en attente. La version
  publiée (manifest 1.0.0) est antérieure à trois lots committés : le lot 3d
  (bornes alignées sur le backend), l'adaptateur France Travail et l'adaptateur
  Indeed, ces deux derniers vérifiés à la main dans l'extension chargée.

# Hors périmètre V1 (ne pas implémenter sans demande explicite)
- Formulaire de correction dans l'extension → V2
- Alertes email, statistiques, paiement → V2
- Connexion Google, refresh tokens, UUID → V3
