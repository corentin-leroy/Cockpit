"""Endpoints CRUD des candidatures — le cœur du cockpit.

Tous les endpoints exigent un utilisateur authentifié (`get_current_user`) et
sont cloisonnés par propriétaire : un utilisateur ne voit et ne manipule que
ses propres candidatures.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import IdPath, IdQuery, get_current_user
from app.limits import MAX_APPLICATIONS_PER_USER, MAX_ARCHIVED_APPLICATIONS_PER_USER
from app.models import Application, ApplicationStatus, Board, User
from app.routers.boards import get_owned_board
from app.schemas import ApplicationCreate, ApplicationRead, ApplicationUpdate
from app.security import utcnow

router = APIRouter(prefix="/applications", tags=["applications"])


def _visible_applications_query(current_user: User, db: Session, *, archived: bool):
    """Requête de base pour LISTER les candidatures d'un utilisateur.

    `archived` est un paramètre SANS valeur par défaut : tout futur endpoint de
    liste qui réutiliserait cette fonction doit choisir explicitement, il ne
    peut pas oublier de le faire (contrairement à un défaut sur le paramètre de
    requête, qui protège seulement CET endpoint-ci)."""
    query = (
        select(Application)
        .join(Board, Application.board_id == Board.id)
        .where(Board.user_id == current_user.id)
    )
    return query.where(
        Application.archived_at.isnot(None) if archived else Application.archived_at.is_(None)
    )


def _count_applications(current_user: User, db: Session, *, archived: bool) -> int:
    """Nombre de candidatures (actives ou archivées) de l'utilisateur, TOUS
    tableaux confondus — même chaîne d'ownership que _visible_applications_query,
    en comptage plutôt qu'en liste."""
    query = (
        select(func.count())
        .select_from(Application)
        .join(Board, Application.board_id == Board.id)
        .where(Board.user_id == current_user.id)
    )
    query = query.where(
        Application.archived_at.isnot(None) if archived else Application.archived_at.is_(None)
    )
    return db.scalar(query)


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
    board_id: IdQuery = None,
    status_filter: ApplicationStatus | None = None,
    archived: bool = False,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Liste les candidatures de l'utilisateur courant (tous tableaux confondus).

    Filtres optionnels par tableau et/ou statut :
      GET /applications?board_id=3&status_filter=applied

    `archived` vaut FALSE quand il est absent : un client qui ignore
    l'archivage (extension, ancien frontend) reçoit le comportement sûr — les
    archivées n'apparaissent jamais dans une liste par défaut. `?archived=true`
    n'affiche QUE les archivées (pas un mélange des deux).

    Le cloisonnement passe par la jointure sur board.user_id : seules les
    candidatures des tableaux de l'utilisateur remontent. Un board_id qui ne lui
    appartient pas ne « fuit » rien — il donne simplement une liste vide.
    """
    query = _visible_applications_query(current_user, db, archived=archived).order_by(
        Application.updated_at.desc()
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

    Plafonné à MAX_APPLICATIONS_PER_USER, limite GLOBALE (tous tableaux confondus,
    comptée via la chaîne d'ownership) : au-delà, 409 et rien n'est créé.

    ⚠ Compte seulement les candidatures ACTIVES (archived_at IS NULL) : sans ce
    filtre, archiver ne libérerait aucune place pour en créer de nouvelles, et
    l'archivage n'aurait aucun intérêt (corrigé lors de l'introduction de
    l'archivage — voir CLAUDE.md, section Archivage).
    """
    # Vérifie que le tableau cible appartient bien à l'utilisateur (sinon 404).
    get_owned_board(payload.board_id, current_user, db)

    # Total des candidatures ACTIVES de l'utilisateur, TOUS tableaux confondus.
    # La limite est globale, pas par tableau.
    application_count = _count_applications(current_user, db, archived=False)
    if application_count >= MAX_APPLICATIONS_PER_USER:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Limite de {MAX_APPLICATIONS_PER_USER} candidatures atteinte.",
        )

    application = Application(**payload.model_dump())
    db.add(application)
    db.commit()
    db.refresh(application)
    return application


@router.get("/{application_id}", response_model=ApplicationRead)
def get_application(
    application_id: IdPath,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return _get_owned_application(application_id, current_user, db)


@router.patch("/{application_id}", response_model=ApplicationRead)
def update_application(
    application_id: IdPath,
    payload: ApplicationUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Met à jour une candidature — sert notamment au drag & drop du kanban
    (changement de statut)."""
    application = _get_owned_application(application_id, current_user, db)

    # exclude_unset=True : on n'applique que les champs réellement envoyés
    data = payload.model_dump(exclude_unset=True)

    # Déplacement vers un autre tableau : vérifier que le tableau cible appartient
    # bien à l'utilisateur (sinon 404), même garde qu'à la création. Sans ce
    # contrôle, un client pourrait « pousser » sa candidature dans le tableau
    # d'autrui via un board_id arbitraire.
    if "board_id" in data:
        get_owned_board(data["board_id"], current_user, db)

    for field, value in data.items():
        setattr(application, field, value)

    db.commit()
    db.refresh(application)
    return application


@router.post("/{application_id}/archive", response_model=ApplicationRead)
def archive_application(
    application_id: IdPath,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Archive une candidature : pose `archived_at`, laisse le STATUT inchangé.

    409 explicite (pas d'idempotence silencieuse) si elle est déjà archivée : un
    succès sur une action qui n'a rien fait masquerait un bug côté client.
    409 aussi au-delà de MAX_ARCHIVED_APPLICATIONS_PER_USER, plafond GLOBAL
    distinct de celui des actives (une candidature ne compte jamais dans les
    deux à la fois)."""
    application = _get_owned_application(application_id, current_user, db)

    if application.archived_at is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cette candidature est déjà archivée.",
        )

    archived_count = _count_applications(current_user, db, archived=True)
    if archived_count >= MAX_ARCHIVED_APPLICATIONS_PER_USER:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Limite de {MAX_ARCHIVED_APPLICATIONS_PER_USER} candidatures "
                "archivées atteinte. Supprimez d'anciennes archives pour en "
                "archiver de nouvelles."
            ),
        )

    application.archived_at = utcnow()
    db.commit()
    db.refresh(application)
    return application


@router.post("/{application_id}/unarchive", response_model=ApplicationRead)
def unarchive_application(
    application_id: IdPath,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Désarchive une candidature : remet `archived_at` à null, statut inchangé.

    409 explicite si elle n'est pas archivée (même principe que archive_application
    : pas d'idempotence silencieuse).
    409 si l'utilisateur a déjà MAX_APPLICATIONS_PER_USER candidatures ACTIVES :
    sans ce contrôle, la limite de 300 se contournerait en archivant puis
    désarchivant. La candidature visée est encore archivée à cet instant, donc
    jamais comptée par erreur parmi les actives qu'on compare au plafond."""
    application = _get_owned_application(application_id, current_user, db)

    if application.archived_at is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cette candidature n'est pas archivée.",
        )

    active_count = _count_applications(current_user, db, archived=False)
    if active_count >= MAX_APPLICATIONS_PER_USER:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Limite de {MAX_APPLICATIONS_PER_USER} candidatures actives "
                "atteinte. Supprimez ou archivez une candidature active pour "
                "faire de la place."
            ),
        )

    application.archived_at = None
    db.commit()
    db.refresh(application)
    return application


@router.delete("/{application_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_application(
    application_id: IdPath,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    application = _get_owned_application(application_id, current_user, db)
    db.delete(application)
    db.commit()
