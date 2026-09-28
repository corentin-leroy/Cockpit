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
from app.dependencies import IdPath, get_current_user
from app.limits import MAX_BOARDS_PER_USER
from app.models import Application, Board, User
from app.schemas import BoardCreate, BoardRead, BoardUpdate

router = APIRouter(prefix="/boards", tags=["boards"])


def _application_counts(board_id: int, db: Session) -> tuple[int, int]:
    """(actives, archivées) d'un tableau. Deux petites requêtes COUNT plutôt
    qu'une agrégation : appelée au plus MAX_BOARDS_PER_USER fois (10) par appel
    à list_boards, un coût mesuré négligeable à cette échelle (cf. CLAUDE.md,
    section Archivage) — pas d'optimisation prématurée pour un plafond aussi
    bas."""
    active = db.scalar(
        select(func.count())
        .select_from(Application)
        .where(Application.board_id == board_id, Application.archived_at.is_(None))
    )
    archived = db.scalar(
        select(func.count())
        .select_from(Application)
        .where(Application.board_id == board_id, Application.archived_at.isnot(None))
    )
    return active, archived


def _to_board_read(board: Board, db: Session) -> BoardRead:
    """Construit le BoardRead d'un tableau, compteurs de candidatures inclus.

    Les 5 champs « simples » viennent de l'attribut ORM (from_attributes), les
    2 compteurs sont calculés ici : Board ne les porte pas comme colonnes."""
    active, archived = _application_counts(board.id, db)
    return BoardRead(
        id=board.id,
        name=board.name,
        user_id=board.user_id,
        created_at=board.created_at,
        updated_at=board.updated_at,
        active_applications_count=active,
        archived_applications_count=archived,
    )


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
    boards = db.scalars(
        select(Board)
        .where(Board.user_id == current_user.id)
        .order_by(Board.created_at)
    ).all()
    return [_to_board_read(board, db) for board in boards]


@router.post("", response_model=BoardRead, status_code=status.HTTP_201_CREATED)
def create_board(
    payload: BoardCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Crée un tableau pour l'utilisateur courant.

    Le propriétaire vient du token, jamais du payload.

    Plafonné à MAX_BOARDS_PER_USER : au-delà, 409 et rien n'est créé. Le contrôle
    est côté serveur (le front ne fait pas autorité)."""
    board_count = db.scalar(
        select(func.count()).select_from(Board).where(Board.user_id == current_user.id)
    )
    if board_count >= MAX_BOARDS_PER_USER:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Limite de {MAX_BOARDS_PER_USER} tableaux atteinte.",
        )

    board = Board(name=payload.name, user_id=current_user.id)
    db.add(board)
    db.commit()
    db.refresh(board)
    return _to_board_read(board, db)


@router.patch("/{board_id}", response_model=BoardRead)
def update_board(
    board_id: IdPath,
    payload: BoardUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Renomme un tableau."""
    board = get_owned_board(board_id, current_user, db)
    board.name = payload.name
    db.commit()
    db.refresh(board)
    return _to_board_read(board, db)


@router.delete("/{board_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_board(
    board_id: IdPath,
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
