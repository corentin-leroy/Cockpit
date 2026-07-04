# Alternance Cockpit

SaaS de suivi de candidatures d'alternance : CRM kanban (cœur du produit) +
extension navigateur pour l'ajout d'offres depuis n'importe quel site.
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
- Tests : `py -m pytest` (à mettre en place)
Frontend (depuis frontend/) :
- Installer : `npm install`
- Lancer : `npm run dev` (http://localhost:5173)
- Build : `npm run build` ; Lint : `npm run lint`

# Architecture backend
- `app/models.py` = tables SQLAlchemy ; `app/schemas.py` = contrats Pydantic.
  Ne jamais exposer un modèle ORM directement dans une réponse API.
- Un router par ressource dans `app/routers/`.
- `user_id` (Application) est obligatoire : renseigné côté serveur depuis le
  current_user, jamais via le payload.
- Endpoints authentifiés : dépendance `get_current_user` (app/dependencies.py).
  Ownership cloisonné par user_id ; accès à la ressource d'autrui → 404 (pas 403).
- Le statut d'une candidature n'est PAS modifiable à la création (démarre
  toujours en "saved"/Repérée) ; il évolue via PATCH (drag & drop côté front).

# Architecture frontend
- `api/` centralise les appels backend. TOUS passent par `apiFetch`
  (api/client.js), qui ajoute le Bearer et purge le token sur 401.
  Jamais de `fetch` direct dans un composant.
- Seul `auth/token.js` accède à localStorage (clé cockpit_token).
- Contexte d'auth (auth/) : état isAuthenticated, login/logout.
- Routes protégées (ProtectedRoute) et routes invité (GuestRoute).
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
   - [à faire] Drag & drop des cartes entre colonnes
4. Reconnecter l'extension à l'auth (elle ne peut plus créer sans token)
5. Déploiement

# Hors périmètre V1 (ne pas implémenter sans demande explicite)
- Agrégation API officielles (La Bonne Alternance, France Travail) → V1.5
- Formulaire de correction dans l'extension → V2
- Alertes email, statistiques, paiement, publication Web Store → V2
- Connexion Google, refresh tokens, UUID → V3