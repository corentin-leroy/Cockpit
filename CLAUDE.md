# Alternance Cockpit

SaaS de suivi de candidatures d'alternance : CRM kanban + agrégation d'offres
via API officielles (France Travail, La Bonne Alternance) + extension navigateur
pour l'ajout manuel depuis les autres sites. AUCUN scraping serveur.

# Stack
- Backend : FastAPI + SQLAlchemy 2.0 + SQLite (PostgreSQL prévu en prod)
- Frontend : React (Vite) — pas encore initialisé
- Environnement : Windows/PowerShell, Python invoqué avec `py`

# Commandes (depuis backend/)
- Installer : `py -m pip install -r requirements.txt`
- Lancer l'API : `py -m uvicorn app.main:app --reload`
- Tests : `py -m pytest` (à mettre en place)

# Architecture
- `app/models.py` = tables SQLAlchemy ; `app/schemas.py` = contrats Pydantic.
  Ne jamais exposer un modèle ORM directement dans une réponse API.
- Un router par ressource dans `app/routers/`.
- `user_id` est nullable temporairement : il devient obligatoire dès que
  l'auth JWT est en place.

# Règles
- Toujours valider les entrées API avec des modèles Pydantic.
- Jamais de secrets en dur : tout passe par les variables d'environnement (.env).
- Style : type hints partout, docstrings en français, code en anglais.
- Commits en anglais, format conventional commits (feat:, fix:, docs:...).
- Ne pas ajouter de dépendance sans la justifier dans le message de commit.

# Roadmap V1 (objectif : en ligne en 6 semaines)
1. [fait] CRUD candidatures + extension navigateur (extraction générique + JSON-LD)
2. [en cours] Auth JWT multi-utilisateurs (inscription, connexion, ownership)
3. Front React : kanban + formulaire d'ajout
4. Connecteur La Bonne Alternance (API officielle)
5. Déploiement

# Hors périmètre V1 (ne pas implémenter sans demande explicite)
Alertes email, statistiques, paiement, publication Web Store, connecteur
France Travail.
