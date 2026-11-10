# Sessions d'arrière-plan et worktrees
Ce qu'il faut à un worktree de ce dépôt pour faire tourner les vérifications, et
ce qu'une session d'arrière-plan ne doit pas lancer (constaté lors d'un test le
2026-11-10). « Dossier principal » = le clone du propriétaire ; « worktree » = la
copie créée par Claude Code sous `.claude/worktrees/` (dossier ignoré par git,
`.claude/` dans .gitignore).

## Avant de lancer la session (propriétaire)
- Un worktree créé par Claude Code part de `origin/main`, PAS du `main` local :
  un commit non poussé n'y figure pas. Le propriétaire pousse AVANT de lancer une
  session d'arrière-plan, sinon l'agent travaille sur une version en retard.
- Ne JAMAIS lancer `claude agents` ni `claude --bg` depuis un shell où
  DATABASE_URL pointe vers la production : la session hérite des variables du
  shell qui la lance. C'est le cas d'une fenêtre restée configurée après une
  opération sur la prod (cf. `dev-docs/migrations.md`, viser la prod depuis le
  poste).

## Au début de la session : contrôle de DATABASE_URL
- Première vérification : `$env:DATABASE_URL`, héritée du shell.
  - absente, vide, ou URL commençant par `sqlite:` (base SQLite locale) → on
    continue ;
  - toute autre valeur → ne RIEN lancer qui touche une base (tests compris,
    alembic, uvicorn, scripts) et le signaler dans le rapport.
- Raison : `tests/conftest.py` remplace la variable pour pytest, mais alembic et
  l'application la lisent telle quelle (`app/database.py` ; `alembic/env.py` la
  fait primer sur le .env, cf. `dev-docs/migrations.md`). La règle ne fait pas
  d'exception pour pytest.

## Backend : préparer et lancer les tests
Depuis `backend\` du worktree :
```powershell
& "<python313>" -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.venv\Scripts\python.exe -m pytest
```
- `<python313>` : chemin ABSOLU du `python.exe` 3.13 installé sur le système,
  hors de tout venv (3.13 : version épinglée par `backend/.python-version`, cf.
  `dev-docs/deployment-railway.md`). Il n'est pas écrit ici : le dépôt est public.
- JAMAIS `python` nu dans un worktree (pas plus que `py` ou `pip` nus, cf.
  « Conventions » du CLAUDE.md racine) : dans le shell du propriétaire, le
  `python` du PATH est le `.venv` situé à la racine du dossier principal. Il
  serait utilisé sans le signaler, et la commande tournerait sur l'environnement
  d'un autre dossier.
- JAMAIS copier un venv (ni celui du dossier principal, ni celui d'un autre
  worktree) : il contient des chemins absolus (`pyvenv.cfg`, lanceurs de
  `Scripts\`) qui désignent toujours son dossier d'origine. On le recrée.
- Les tests n'ont besoin ni de `backend\.env` ni de `cockpit.db` :
  - `tests/conftest.py` pose ses variables AVANT tout import de l'application
    (`DATABASE_URL` en mémoire, `JWT_SECRET_KEY` de test, variables Brevo vides →
    mode DEV, aucun email) ; `load_dotenv()` n'écrase pas une variable déjà
    posée et ne fait rien sans fichier.
  - Les autres variables lues au démarrage ont un défaut local (`CORS_ORIGINS`,
    `FRONTEND_URL`, `TRUSTED_PROXY_COUNT`, durée de session).
  - Bases : SQLite en mémoire (conftest.py, `test_migrations.py`), fichiers
    SQLite dans le `tmp_path` de pytest pour les tests de course (`*_race.py`,
    `test_auth_rate_limit.py`).
- Donc : aucun `.env` ni aucune base copiés dans un worktree, et PAS de
  `.worktreeinclude` (liste de fichiers ignorés par git que Claude Code recopie
  dans chaque worktree) : `backend\.env` contient une vraie clé Brevo.

## Frontend : préparer et vérifier
Depuis `frontend\` du worktree :
```powershell
npm ci
npm run lint
```
- `npm ci` installe exactement `package-lock.json`, sans le réécrire.
- Il n'existe PAS de suite de tests frontend (aucun script `test` dans
  `package.json`) : le lint (`eslint .`) est la seule vérification automatique.

## Aucun serveur de dev
- Ni `uvicorn` ni `npm run dev` (Vite) dans une session d'arrière-plan ou un
  worktree :
  - API : uvicorn écoute par défaut sur le port 8000, celui qu'appelle le front
    sans `VITE_API_BASE_URL` (`http://127.0.0.1:8000`, `src/api/client.js`) :
    deux sessions se disputeraient le port.
  - Front : port 5173 déjà pris → Vite passe au suivant, 5174 (`vite.config.js`
    ne pose pas `strictPort`) ; or CORS_ORIGINS absente n'autorise que
    `http://localhost:5173` (`get_allowed_origins`, app/main.py) : ce second
    front serait bloqué par le CORS.
- Les tests dans le navigateur restent faits par le propriétaire.

## Fin de travail
- Modifications laissées NON committées (cf. « Git » du CLAUDE.md racine) ; le
  rapport indique le chemin du worktree et le nom de sa branche.
