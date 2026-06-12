# Alternance Cockpit

Le cockpit de la recherche d'alternance : suivi de candidatures (kanban),
agrégation d'offres via API officielles, ajout en un clic depuis n'importe
quel site d'annonces.

## Démarrage rapide (Windows/PowerShell)

```powershell
cd backend
py -m venv .venv
.venv\Scripts\Activate.ps1
py -m pip install -r requirements.txt
py -m uvicorn app.main:app --reload
```

API disponible sur http://127.0.0.1:8000 — documentation interactive
auto-générée sur http://127.0.0.1:8000/docs (tester les endpoints depuis là).

## Structure

```
backend/app/
  main.py        # point d'entrée FastAPI
  database.py    # config SQLAlchemy/SQLite
  models.py      # tables (ORM)
  schemas.py     # contrats API (Pydantic)
  routers/       # un fichier par ressource
extension/       # extension navigateur (Manifest V3), ajout en un clic
CLAUDE.md        # instructions persistantes pour Claude Code
```

Voir CLAUDE.md pour la roadmap.
