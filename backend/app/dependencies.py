"""Dépendances FastAPI partagées entre les routers.

Contient l'authentification : `get_current_user` transforme le JWT porté par
la requête en objet `User`, ou refuse la requête avec un 401.
"""

from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, Path, Query, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.database import get_db
from app.limits import MAX_ID
from app.models import User
from app.security import decode_access_token

# Identifiants reçus dans l'URL (chemin) ou la chaîne de requête. Un identifiant est
# un entier >= 1 tenant dans le type `integer` de PostgreSQL : 0 et les négatifs
# sont MALFORMÉS (422), pas « introuvables » ; au-delà de MAX_ID la base lève
# « integer out of range » (500). Les identifiants du CORPS sont bornés dans
# schemas.py (RowId, mêmes constantes).
IdPath = Annotated[int, Path(ge=1, le=MAX_ID)]
IdQuery = Annotated[int | None, Query(ge=1, le=MAX_ID)]

# OAuth2PasswordBearer lit l'en-tête `Authorization: Bearer <token>`.
# `tokenUrl` ne sert qu'à la documentation OpenAPI (bouton "Authorize" de
# /docs) : il pointe vers l'endpoint qui délivre le token.
# Si l'en-tête est absent, ce schéma renvoie lui-même un 401 (avec
# WWW-Authenticate: Bearer), ce qui couvre le cas « token manquant ».
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Renvoie l'utilisateur authentifié à partir du JWT.

    Lève 401 si le token est invalide/expiré, si le claim `sub` est absent ou
    incohérent, ou si l'utilisateur n'existe plus en base. Le message reste
    volontairement générique : on ne distingue pas les causes côté client.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Impossible de valider les identifiants.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = decode_access_token(token)
        subject = payload.get("sub")
        if subject is None:
            raise credentials_exception
        user_id = int(subject)  # `sub` est une chaîne ; on revient à l'int de la PK
    except (jwt.PyJWTError, ValueError):
        # PyJWTError : signature/expiration/format ; ValueError : `sub` non entier.
        raise credentials_exception

    user = db.get(User, user_id)
    if user is None:
        raise credentials_exception
    return user
