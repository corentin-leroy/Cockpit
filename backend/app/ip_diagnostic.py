"""DIAGNOSTIC TEMPORAIRE : à supprimer après lecture des journaux (revert du commit).

But : savoir, EMPIRIQUEMENT et sans hypothèse sur Railway, ce qui arrive réellement à
l'application derrière le proxy : l'IP vue par l'app après uvicorn, et les en-têtes de
transfert (X-Forwarded-For, etc.) tels que le proxy les transmet, y compris face à un
en-tête falsifié par le client.

Rien n'est renvoyé au client : la route répond 204 sans corps, et la mesure n'est
journalisée que côté serveur (WARNING : aucun handler n'est configuré, donc Python
n'imprime sur stderr que WARNING et plus, ce que Railway collecte).

Sans la variable IP_DIAG_TOKEN, ou avec un mauvais jeton dans l'URL, la route répond
404 : elle n'existe pas pour qui ne connaît pas le secret.
"""

import json
import logging
import os
import secrets

from fastapi import APIRouter, HTTPException, Request, Response

router = APIRouter()
logger = logging.getLogger("app.ipdiag")

# Jamais journalisés : ce sont des secrets de session.
_SENSITIVE_HEADERS = {"authorization", "cookie", "proxy-authorization"}


@router.get("/_diag/ip/{token}", include_in_schema=False)
def ip_diagnostic(token: str, request: Request) -> Response:
    expected = os.getenv("IP_DIAG_TOKEN", "")
    if not expected or not secrets.compare_digest(token, expected):
        raise HTTPException(status_code=404)

    # En-têtes BRUTS (scope), pas request.headers : les doublons et l'ordre sont
    # conservés, ce qui compte pour un en-tête comme X-Forwarded-For.
    headers = [
        [name.decode("latin1"), value.decode("latin1")]
        for name, value in request.scope["headers"]
        if name.decode("latin1").lower() not in _SENSITIVE_HEADERS
    ]
    logger.warning(
        "IPDIAG %s",
        json.dumps(
            {
                # Ce que l'application voit APRÈS le traitement éventuel d'uvicorn.
                "scope_client": request.scope.get("client"),
                "scheme": request.url.scheme,
                "forwarded_allow_ips_env": os.getenv("FORWARDED_ALLOW_IPS"),
                # Ce que le proxy a réellement transmis.
                "headers": headers,
            }
        ),
    )
    return Response(status_code=204)
