"""Endpoints CRUD des candidatures — le cœur du cockpit.

Tous les endpoints exigent un utilisateur authentifié (`get_current_user`) et
sont cloisonnés par propriétaire : un utilisateur ne voit et ne manipule que
ses propres candidatures.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models import Application, ApplicationStatus, User
from app.schemas import ApplicationCreate, ApplicationRead, ApplicationUpdate

router = APIRouter(prefix="/applications", tags=["applications"])


def _get_owned_application(
    application_id: int, current_user: User, db: Session
) -> Application:
    """Récupère une candidature appartenant à `current_user`, ou lève 404.

    On filtre directement sur le user_id : une candidature qui existe mais
    appartient à autrui est traitée EXACTEMENT comme une candidature
    inexistante (404). Renvoyer un 403 dans ce cas confirmerait son existence,
    ce qui est déjà une fuite d'information (énumération d'IDs). Le 404 ne
    révèle rien : du point de vue du client, la ressource n'existe pas pour lui.
    """
    application = db.scalar(
        select(Application).where(
            Application.id == application_id,
            Application.user_id == current_user.id,
        )
    )
    if application is None:
        raise HTTPException(status_code=404, detail="Candidature introuvable")
    return application


@router.get("", response_model=list[ApplicationRead])
def list_applications(
    status_filter: ApplicationStatus | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Liste les candidatures de l'utilisateur courant, filtre optionnel par statut.

    Exemple : GET /applications?status_filter=applied
    """
    query = (
        select(Application)
        .where(Application.user_id == current_user.id)
        .order_by(Application.updated_at.desc())
    )
    if status_filter is not None:
        query = query.where(Application.status == status_filter)
    return db.scalars(query).all()


@router.post("", response_model=ApplicationRead, status_code=status.HTTP_201_CREATED)
def create_application(
    payload: ApplicationCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Crée une candidature (formulaire web ou bookmarklet).

    Le propriétaire vient du token, jamais du payload : un client ne peut pas
    créer une candidature au nom d'un autre utilisateur.
    """
    application = Application(**payload.model_dump(), user_id=current_user.id)
    db.add(application)
    db.commit()
    db.refresh(application)
    return application


@router.get("/{application_id}", response_model=ApplicationRead)
def get_application(
    application_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return _get_owned_application(application_id, current_user, db)


@router.patch("/{application_id}", response_model=ApplicationRead)
def update_application(
    application_id: int,
    payload: ApplicationUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Met à jour une candidature — sert notamment au drag & drop du kanban
    (changement de statut)."""
    application = _get_owned_application(application_id, current_user, db)

    # exclude_unset=True : on n'applique que les champs réellement envoyés
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(application, field, value)

    db.commit()
    db.refresh(application)
    return application


@router.delete("/{application_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_application(
    application_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    application = _get_owned_application(application_id, current_user, db)
    db.delete(application)
    db.commit()
