"""Point d'entrée de l'API Cockpit.

Lance le serveur avec :  py -m uvicorn app.main:app --reload
"""
from dotenv import load_dotenv
load_dotenv()

import logging
import os

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from app.error_messages import GENERIC_SERVER_ERROR_DETAIL, build_validation_error_body
from app.limits import MAX_REQUEST_BODY_BYTES
from app.routers import applications, auth, boards

logger = logging.getLogger("app.errors")

# Aucun create_all() ici : le schéma est géré par Alembic, en dev comme en prod
# (`.venv\Scripts\python.exe -m alembic upgrade head`, exécuté par Railway en
# pre-deploy). Les tests créent leur propre schéma (tests/conftest.py).


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

@app.exception_handler(RequestValidationError)
async def validation_error_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Réponse 422 en FRANÇAIS, directement affichable (cf. app/error_messages.py).

    `detail` est une CHAÎNE (jamais le tableau brut de Pydantic — c'était la
    cause du « [object Object] » côté client) ; `errors` liste chaque champ en
    cause, pour un affichage sous le champ concerné.

    Cette reconstruction ignore aussi la valeur soumise (`input`) ET le `ctx` brut
    de Pydantic : pour nos validateurs personnalisés, `ctx` contient l'OBJET
    EXCEPTION Python lui-même (vérifié par exécution), non sérialisable
    proprement en JSON ; pour un mot de passe refusé, le `msg` par défaut de
    Pydantic recopierait la valeur en clair. build_validation_error_body ne lit
    que `type`/`loc`/`ctx` pour CHOISIR un message dans le catalogue — jamais
    pour le construire à partir de la donnée soumise."""
    body = build_validation_error_body(exc.errors())
    return JSONResponse(status_code=422, content=body)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Toute exception NON prévue (bug) renvoie un JSON français générique.

    Par défaut, Starlette renvoie un corps VIDE ou non-JSON (« Internal Server
    Error ») : `response.json()` échoue côté client, qui retombe sur
    `response.statusText` — du texte anglais, sans rapport avec l'erreur réelle.

    Le texte et la trace de l'exception ne sont JAMAIS renvoyés au client (fuite
    de détail technique) ; ils restent visibles côté serveur via `logger.exception`
    (logs locaux et Railway). Ce gestionnaire ne modifie PAS le comportement des
    exceptions déjà gérées ailleurs (HTTPException, RequestValidationError) :
    FastAPI/Starlette dispatchent toujours au gestionnaire le plus spécifique
    enregistré pour le type réel de l'exception."""
    logger.exception("Exception non gérée sur %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500, content={"detail": GENERIC_SERVER_ERROR_DETAIL}
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
    # Sans cela, un navigateur n'expose pas Retry-After au JavaScript d'une autre
    # origine : le front ne pourrait pas afficher le temps d'attente d'un 429.
    expose_headers=["Retry-After"],
)

app.include_router(applications.router)
app.include_router(auth.router)
app.include_router(boards.router)


@app.get("/health", tags=["system"])
def health_check():
    """Permet de vérifier que l'API tourne (utile pour le monitoring)."""
    return {"status": "ok"}
