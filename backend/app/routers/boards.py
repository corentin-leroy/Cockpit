"""Endpoints CRUD des tableaux (Board).

Un tableau appartient à un utilisateur. Tous les endpoints exigent un
utilisateur authentifié et sont cloisonnés par propriétaire : un utilisateur ne
voit et ne manipule que ses propres tableaux. Accès au tableau d'autrui → 404
(même politique que les candidatures : ne pas confirmer l'existence d'un id).
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models import Board, User
from app.schemas import BoardCreate, BoardRead, BoardUpdate

router = APIRouter(prefix="/boards", tags=["boards"])


def get_owned_board(board_id: int, current_user: User, db: Session) -> Board:
    """Récupère un tableau appartenant à `current_user`, ou lève 404.

    Helper partagé : utilisé ici (get/patch/delete) ET par le router des
    candidatures (vérifier le board cible à la création). On filtre directement
    sur user_id → un tableau d'autrui est indistinguable d'un tableau inexistant.
    """
    board = db.scalar(
        select(Board).where(Board.id == board_id, Board.user_id == current_user.id)
    )
    if board is None:
        raise HTTPException(status_code=404, detail="Tableau introuvable")
    return board


@router.get("", response_model=list[BoardRead])
def list_boards(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Liste les tableaux de l'utilisateur courant (du plus ancien au plus récent)."""
    return db.scalars(
        select(Board)
        .where(Board.user_id == current_user.id)
        .order_by(Board.created_at)
    ).all()


@router.post("", response_model=BoardRead, status_code=status.HTTP_201_CREATED)
def create_board(
    payload: BoardCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Crée un tableau pour l'utilisateur courant.

    Le propriétaire vient du token, jamais du payload.
    """
    board = Board(name=payload.name, user_id=current_user.id)
    db.add(board)
    db.commit()
    db.refresh(board)
    return board


@router.patch("/{board_id}", response_model=BoardRead)
def update_board(
    board_id: int,
    payload: BoardUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Renomme un tableau."""
    board = get_owned_board(board_id, current_user, db)
    board.name = payload.name
    db.commit()
    db.refresh(board)
    return board


@router.delete("/{board_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_board(
    board_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Supprime un tableau ET ses candidatures (cascade ORM).

    ATTENTION : la suppression entraîne celle de toutes les candidatures du
    tableau (relation cascade all, delete-orphan). C'est volontaire.

    Règle métier : un utilisateur doit toujours conserver au moins un tableau.
    Tenter de supprimer le dernier renvoie 409 Conflict.
    """
    board = get_owned_board(board_id, current_user, db)

    # Compte les tableaux de l'utilisateur : on refuse de supprimer le dernier.
    board_count = db.scalar(
        select(func.count()).select_from(Board).where(Board.user_id == current_user.id)
    )
    if board_count <= 1:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Impossible de supprimer votre dernier tableau.",
        )

    db.delete(board)  # cascade → supprime aussi les candidatures du tableau
    db.commit()
