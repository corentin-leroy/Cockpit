"""Point d'entrée de l'API Alternance Cockpit.

Lance le serveur avec :  py -m uvicorn app.main:app --reload
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import Base, engine
from app.routers import applications, auth

# Crée les tables au démarrage (suffisant en dev ; on passera à Alembic plus tard)
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Alternance Cockpit",
    description="Le cockpit de ta recherche d'alternance : suivi de candidatures, "
    "agrégation d'offres et bookmarklet.",
    version="0.1.0",
)

# CORS : nécessaire pour que le futur front React (port 5173) et le bookmarklet
# puissent appeler l'API. À restreindre en production.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # TODO: restreindre avant la mise en production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(applications.router)
app.include_router(auth.router)


@app.get("/health", tags=["system"])
def health_check():
    """Permet de vérifier que l'API tourne (utile pour le monitoring)."""
    return {"status": "ok"}
