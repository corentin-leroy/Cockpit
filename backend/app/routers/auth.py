"""Endpoints d'authentification : inscription et connexion.

La protection des endpoints (lecture du JWT, ownership) viendra à l'étape
suivante — ici on se contente d'émettre le token.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.schemas import Token, UserCreate, UserLogin, UserRead
from app.security import (
    DUMMY_PASSWORD_HASH,
    create_access_token,
    hash_password,
    verify_password,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def register(payload: UserCreate, db: Session = Depends(get_db)):
    """Crée un compte utilisateur.

    Refuse un email déjà pris avec un 409 Conflict. Le mot de passe est haché
    avant stockage ; la réponse (UserRead) n'expose jamais le hash.
    """
    # Contrôle applicatif du doublon : message clair pour le client.
    # La contrainte unique en base reste le garde-fou ultime (voir plus bas).
    existing = db.scalar(select(User).where(User.email == payload.email))
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Un compte existe déjà avec cet email.",
        )

    user = User(
        email=payload.email,
        hashed_password=hash_password(payload.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post("/login", response_model=Token)
def login(payload: UserLogin, db: Session = Depends(get_db)):
    """Authentifie un utilisateur et renvoie un JWT.

    En cas d'échec, renvoie un 401 avec un message **identique** que l'email
    soit inconnu ou le mot de passe faux : on ne révèle jamais si un compte
    existe. On exécute toujours verify_password (contre un hash leurre quand
    l'email est inconnu) pour ne pas trahir l'existence d'un compte par le
    temps de réponse.
    """
    user = db.scalar(select(User).where(User.email == payload.email))
    hashed = user.hashed_password if user is not None else DUMMY_PASSWORD_HASH

    if not verify_password(payload.password, hashed) or user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email ou mot de passe incorrect.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # `sub` (subject) = identité portée par le token ; chaîne par convention JWT.
    access_token = create_access_token({"sub": str(user.id)})
    return Token(access_token=access_token)
