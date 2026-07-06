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
from app.models import Application, ApplicationStatus, Board, User
from app.routers.boards import get_owned_board
from app.schemas import ApplicationCreate, ApplicationRead, ApplicationUpdate

router = APIRouter(prefix="/applications", tags=["applications"])


def _get_owned_application(
    application_id: int, current_user: User, db: Session
) -> Application:
    """Récupère une candidature appartenant à `current_user`, ou lève 404.

    L'ownership passe désormais par la chaîne application → board → user : on
    joint le tableau et on filtre sur board.user_id. Une candidature qui existe
    mais dont le tableau appartient à autrui est traitée EXACTEMENT comme une
    candidature inexistante (404). Renvoyer un 403 confirmerait son existence,
    ce qui est déjà une fuite d'information (énumération d'IDs). Le 404 ne
    révèle rien : du point de vue du client, la ressource n'existe pas pour lui.
    """
    application = db.scalar(
        select(Application)
        .join(Board, Application.board_id == Board.id)
        .where(
            Application.id == application_id,
            Board.user_id == current_user.id,
        )
    )
    if application is None:
        raise HTTPException(status_code=404, detail="Candidature introuvable")
    return application


@router.get("", response_model=list[ApplicationRead])
def list_applications(
    board_id: int | None = None,
    status_filter: ApplicationStatus | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Liste les candidatures de l'utilisateur courant (tous tableaux confondus).

    Filtres optionnels par tableau et/ou statut :
      GET /applications?board_id=3&status_filter=applied

    Le cloisonnement passe par la jointure sur board.user_id : seules les
    candidatures des tableaux de l'utilisateur remontent. Un board_id qui ne lui
    appartient pas ne « fuit » rien — il donne simplement une liste vide.
    """
    query = (
        select(Application)
        .join(Board, Application.board_id == Board.id)
        .where(Board.user_id == current_user.id)
        .order_by(Application.updated_at.desc())
    )
    if board_id is not None:
        query = query.where(Application.board_id == board_id)
    if status_filter is not None:
        query = query.where(Application.status == status_filter)
    return db.scalars(query).all()


@router.post("", response_model=ApplicationRead, status_code=status.HTTP_201_CREATED)
def create_application(
    payload: ApplicationCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Crée une candidature dans un tableau de l'utilisateur (formulaire ou extension).

    Le tableau cible (payload.board_id) doit appartenir au current_user : sinon
    404 (via get_owned_board). L'ownership n'est donc jamais pris dans le payload
    à l'aveugle — il est vérifié par la possession du board.
    """
    # Vérifie que le tableau cible appartient bien à l'utilisateur (sinon 404).
    get_owned_board(payload.board_id, current_user, db)

    application = Application(**payload.model_dump())
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
