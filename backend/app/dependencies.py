"""Dépendances FastAPI partagées entre les routers.

Contient l'authentification : `get_current_user` transforme le JWT porté par
la requête en objet `User`, ou refuse la requête avec un 401.
"""

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.security import decode_access_token

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
