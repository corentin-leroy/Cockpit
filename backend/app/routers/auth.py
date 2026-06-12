"""Endpoints d'authentification.

Étape 1 (ici) : inscription. Le login et l'émission de JWT viendront ensuite.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.schemas import UserCreate, UserRead
from app.security import hash_password

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
