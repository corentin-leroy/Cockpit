"""Point d'entrée de l'API Cockpit.

Lance le serveur avec :  py -m uvicorn app.main:app --reload
"""
from dotenv import load_dotenv
load_dotenv()

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from app.database import Base, engine
from app.limits import MAX_REQUEST_BODY_BYTES
from app.routers import applications, auth, boards

# Crée les tables au démarrage (suffisant en dev ; on passera à Alembic plus tard)
Base.metadata.create_all(bind=engine)


def get_allowed_origins() -> list[str]:
    """Origines autorisées par CORS, lues dans CORS_ORIGINS.

    Format : plusieurs URLs séparées par des virgules, par exemple
    `https://cockpit.app,https://www.cockpit.app`. Ajouter le front déployé se
    fait donc par variable d'environnement, sans toucher au code ni redéployer
    une image différente.

    Défaut (variable absente ou vide) : http://localhost:5173, le serveur Vite —
    le dev n'a rien à configurer.

    Les origines sont normalisées sans « / » final : le navigateur envoie un
    en-tête `Origin` sans slash terminal (`https://cockpit.app`), donc une valeur
    saisie avec slash ne correspondrait JAMAIS et le front serait bloqué en
    production, avec une erreur CORS difficile à relier à une coquille de
    configuration. Même précaution que sur FRONTEND_URL (email.py).
    """
    raw = os.getenv("CORS_ORIGINS", "")
    origins = [origin.strip().rstrip("/") for origin in raw.split(",") if origin.strip()]
    return origins or ["http://localhost:5173"]


class BodySizeLimitMiddleware:
    """Refuse (413) toute requête dont le corps dépasse `max_body_size` octets.

    Middleware ASGI pur (et non BaseHTTPMiddleware) : on inspecte la requête au
    plus tôt, avant que l'endpoint ne bufferise le corps, et on court-circuite en
    renvoyant directement la réponse 413 sans jamais toucher à l'app.

    Contrôle par l'en-tête Content-Length : un client qui envoie une charge utile
    démesurée (ex. un champ `notes` de plusieurs Mo sérialisé en JSON) annonce sa
    taille dans cet en-tête. On rejette alors sans même lire le corps.

    Limite assumée : un client pourrait mentir sur Content-Length ou l'omettre
    (transfert chunked). Le garde-fou AUTORITAIRE contre ça est le reverse proxy
    en production (ex. nginx `client_max_body_size`), qui coupe avant même
    d'atteindre l'app. Ce middleware est une défense en profondeur applicative,
    utile aussi en dev où aucun proxy n'est présent. On évite volontairement un
    comptage à la volée côté ASGI : renvoyer proprement un 413 au milieu d'un flux
    déjà pris en charge par l'app est fragile (double envoi de réponse).
    """

    def __init__(self, app: ASGIApp, max_body_size: int) -> None:
        self.app = app
        self.max_body_size = max_body_size

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        content_length = dict(scope["headers"]).get(b"content-length")
        if content_length is not None:
            try:
                too_large = int(content_length) > self.max_body_size
            except ValueError:
                too_large = False  # Content-Length illisible : on n'en tient pas compte.
            if too_large:
                response = JSONResponse(
                    {"detail": "Corps de requête trop volumineux."},
                    status_code=413,
                )
                await response(scope, receive, send)
                return

        await self.app(scope, receive, send)


app = FastAPI(
    title="Cockpit",
    description="Le poste de pilotage de votre recherche d'emploi : suivi de "
    "candidatures, agrégation d'offres et extension navigateur.",
    version="0.1.0",
)

# Plafonne la taille des corps de requête (anti-charge utile démesurée).
app.add_middleware(BodySizeLimitMiddleware, max_body_size=MAX_REQUEST_BODY_BYTES)

# CORS : nécessaire pour que le front React et l'extension puissent appeler l'API
# depuis une autre origine. La liste vient de CORS_ORIGINS (cf. get_allowed_origins) :
# plus de "*" en dur, qui autorisait N'IMPORTE QUEL site à appeler l'API au nom
# d'un utilisateur connecté et à lire la réponse.
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_allowed_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(applications.router)
app.include_router(auth.router)
app.include_router(boards.router)


@app.get("/health", tags=["system"])
def health_check():
    """Permet de vérifier que l'API tourne (utile pour le monitoring)."""
    return {"status": "ok"}
