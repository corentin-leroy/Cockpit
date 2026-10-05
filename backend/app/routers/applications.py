"""Endpoints CRUD des candidatures — le cœur du cockpit.

Tous les endpoints exigent un utilisateur authentifié (`get_current_user`) et
sont cloisonnés par propriétaire : un utilisateur ne voit et ne manipule que
ses propres candidatures.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import bindparam, func, select, update
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import IdPath, IdQuery, get_current_user
from app.limits import MAX_APPLICATIONS_PER_USER, MAX_ARCHIVED_APPLICATIONS_PER_USER
from app.models import Application, ApplicationStatus, Board, User
from app.routers.boards import get_owned_board
from app.schemas import ApplicationCreate, ApplicationMove, ApplicationRead, ApplicationUpdate
from app.security import utcnow

router = APIRouter(prefix="/applications", tags=["applications"])


# ---------------------------------------------------------------------------
# Ordre des cartes du kanban (colonne `position`, cf. models.py)
#
# Une COLONNE = les candidatures ACTIVES d'un tableau ayant un statut donné. Leurs
# positions valent exactement 0..n-1 (0 = en haut). Toute écriture qui fait entrer
# ou sortir une carte d'une colonne la RENUMÉROTE ENTIÈREMENT, dans l'ordre affiché
# : un NULL (ligne écrite par l'ancien code pendant un déploiement), un doublon ou
# un trou disparaissent à la prochaine écriture. Une colonne compte au plus 300
# cartes ; seules les lignes dont le rang change sont réécrites.
#
# RÈGLE D'ARRIVÉE : une carte qui entre dans une colonne autrement que par POST
# /move (création, PATCH qui change réellement le statut ou le tableau,
# désarchivage) arrive EN HAUT (rang 0).
#
# CONCURRENCE : chaque endpoint qui écrit une position appelle d'abord
# _lock_positions_of, AVANT toute lecture (cf. sa docstring).
# ---------------------------------------------------------------------------

# Ordre d'affichage d'une colonne. Les NULL d'abord (arrivées écrites par l'ancien
# code pendant un déploiement : en haut, comme toute arrivée), puis le rang ; à
# rang égal (doublon, même origine), la plus récemment modifiée d'abord, et l'id
# pour un ordre toujours déterministe.
_COLUMN_ORDER = (
    Application.position.asc().nulls_first(),
    Application.updated_at.desc(),
    Application.id.desc(),
)

# Réécriture du rang d'UNE ligne, exécutée en lot (executemany). Par la TABLE
# (Core) et non par l'ORM : les voisines ne sont pas chargées comme objets.
# `updated_at` est reposé à sa propre valeur : sinon son `onupdate` s'appliquerait,
# et décaler une voisine n'est pas la modifier.
_applications_table = Application.__table__
_SET_POSITION = (
    update(_applications_table)
    .where(_applications_table.c.id == bindparam("row_id"))
    .values(
        position=bindparam("new_position"),
        updated_at=_applications_table.c.updated_at,
    )
)


def _lock_positions_of(current_user: User, db: Session) -> None:
    """Sérialise les écritures de positions d'un utilisateur. À appeler EN PREMIER,
    avant toute lecture de candidature.

    Sans verrou, deux requêtes simultanées (deux onglets) lisent la même colonne
    avant qu'aucune n'ait écrit ; la seconde renumérote sur des données périmées et
    produit doublons et trous (tests/test_position_race.py échoue alors).

    Une instruction NEUTRE sur la ligne de l'utilisateur (`SET id = id`), le même
    SQL sur les deux moteurs, comme _consume_token (routers/auth.py) :
    - PostgreSQL : verrou de ligne tenu jusqu'au commit. La requête suivante du
      même utilisateur attend, puis ses lectures (READ COMMITTED : un instantané
      par instruction) voient ce que la précédente a écrit ;
    - SQLite : première ÉCRITURE de la transaction, qui prend le verrou d'écriture
      de la base AVANT toute lecture (lire puis écrire exposerait à un « database
      is locked » immédiat). `FOR UPDATE` serait ignoré sous SQLite : les tests
      n'exerceraient alors aucun verrou.
    Par UTILISATEUR et non par tableau : un déplacement vers un autre tableau touche
    deux tableaux, que deux requêtes pourraient verrouiller dans des ordres opposés
    (interblocage). La contention reste celle d'un seul utilisateur.

    Effet de bord : les comptages des plafonds (300 actives, 2000 archivées), faits
    après ce verrou, ne peuvent plus être dépassés par des créations simultanées."""
    db.execute(
        update(User)
        .where(User.id == current_user.id)
        .values(id=User.id)
        .execution_options(synchronize_session=False)
    )


def _column_rows(
    db: Session, board_id: int, status_: ApplicationStatus, *, excluding: int | None
) -> list[tuple[int, int | None]]:
    """(id, position) des cartes d'une colonne, dans l'ordre affiché, sans la carte
    `excluding` (celle qu'on déplace : elle est placée par l'appelant)."""
    query = select(Application.id, Application.position).where(
        Application.board_id == board_id,
        Application.status == status_,
        Application.archived_at.is_(None),
    )
    if excluding is not None:
        query = query.where(Application.id != excluding)
    return [tuple(row) for row in db.execute(query.order_by(*_COLUMN_ORDER))]


def _write_positions(db: Session, rows: list[tuple[int, int | None]], ranks: range) -> None:
    """Attribue `ranks` aux lignes `rows`, dans l'ordre ; n'écrit que les lignes dont
    le rang change."""
    changes = [
        {"row_id": row_id, "new_position": rank}
        for (row_id, current), rank in zip(rows, ranks)
        if current != rank
    ]
    if changes:
        db.execute(_SET_POSITION, changes)


def _leave_column(db: Session, application: Application) -> None:
    """Retire la carte de sa colonne ACTUELLE (board_id et status tels qu'en base) :
    les autres sont renumérotées 0..n-1. Le rang de la carte elle-même est laissé à
    l'appelant (NULL si elle est archivée, nouveau rang si elle change de colonne)."""
    rows = _column_rows(db, application.board_id, application.status, excluding=application.id)
    _write_positions(db, rows, range(len(rows)))


def _place_in_column(
    db: Session,
    application: Application,
    board_id: int,
    status_: ApplicationStatus,
    index: int,
) -> None:
    """Place la carte au rang `index` de la colonne (board_id, status_) et renumérote
    les autres autour. Un rang au-delà de la fin est ramené en fin de colonne.

    Ne la retire PAS de son ancienne colonne si elle en change : appeler
    _leave_column d'abord. Si elle était déjà dans cette colonne, elle en est
    exclue à la relecture : la renumérotation la déplace sans doublon."""
    rows = _column_rows(db, board_id, status_, excluding=application.id)
    index = min(index, len(rows))
    _write_positions(db, rows[:index], range(index))
    _write_positions(db, rows[index:], range(index + 1, len(rows) + 1))
    application.position = index


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
    # Actives : l'ordre du kanban (position). Archivées : inchangé, la page
    # d'archives trie elle-même (date d'archivage) et leur position est NULL.
    query = _visible_applications_query(current_user, db, archived=archived).order_by(
        *((Application.updated_at.desc(),) if archived else _COLUMN_ORDER)
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
    _lock_positions_of(current_user, db)

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
    # Arrivée EN HAUT de « Repérée » (toute création, formulaire comme extension).
    # Placée AVANT db.add : la carte n'est pas encore dans la colonne relue.
    _place_in_column(db, application, payload.board_id, ApplicationStatus.SAVED, 0)
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
    """Met à jour une candidature (formulaire d'édition, déplacement vers un autre
    tableau depuis la sidebar).

    Si le statut ou le tableau CHANGE RÉELLEMENT sur une candidature active, elle
    quitte sa colonne et arrive EN HAUT de la nouvelle. Comparaison aux valeurs
    STOCKÉES, pas à la présence du champ : le formulaire d'édition renvoie toujours
    `status` et `board_id`, même inchangés, et ce n'est pas une arrivée. Choisir un
    rang précis passe par POST /applications/{id}/move."""
    _lock_positions_of(current_user, db)
    application = _get_owned_application(application_id, current_user, db)

    # exclude_unset=True : on n'applique que les champs réellement envoyés
    data = payload.model_dump(exclude_unset=True)

    # Déplacement vers un autre tableau : vérifier que le tableau cible appartient
    # bien à l'utilisateur (sinon 404), même garde qu'à la création. Sans ce
    # contrôle, un client pourrait « pousser » sa candidature dans le tableau
    # d'autrui via un board_id arbitraire.
    if "board_id" in data:
        get_owned_board(data["board_id"], current_user, db)

    target_board_id = data.get("board_id", application.board_id)
    target_status = data.get("status", application.status)
    changes_column = (target_board_id, target_status) != (
        application.board_id,
        application.status,
    )
    # Une archivée n'est dans aucune colonne : rien à renuméroter, sa position reste
    # NULL ; elle arrivera en haut de sa colonne au désarchivage.
    if application.archived_at is None and changes_column:
        _leave_column(db, application)
        _place_in_column(db, application, target_board_id, target_status, 0)

    for field, value in data.items():
        setattr(application, field, value)

    db.commit()
    db.refresh(application)
    return application


@router.post("/{application_id}/move", response_model=ApplicationRead)
def move_application(
    application_id: IdPath,
    payload: ApplicationMove,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Glisser-déposer : place la candidature au rang `position` de la colonne
    `status` de SON tableau (0 = en haut), dans sa colonne comme dans une autre.
    Les autres cartes des colonnes de départ et d'arrivée sont renumérotées.

    - Rang au-delà de la fin : ramené en fin de colonne (onglet en retard), pas une
      erreur.
    - Rang déjà occupé par la carte : 200, rien ne change. Un placement est absolu
      (« mets-la ici »), pas une bascule : il n'y a pas d'action redondante.
    - Candidature archivée : 409, elle n'est dans aucune colonne.
    - Aucun contrôle de plafond : déplacer ne change aucun total."""
    _lock_positions_of(current_user, db)
    application = _get_owned_application(application_id, current_user, db)

    if application.archived_at is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Une candidature archivée ne se déplace pas dans le kanban.",
        )

    if payload.status != application.status:
        _leave_column(db, application)
    _place_in_column(db, application, application.board_id, payload.status, payload.position)
    application.status = payload.status

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
    deux à la fois).

    La carte quitte sa colonne (renumérotée) et sa position passe à NULL."""
    _lock_positions_of(current_user, db)
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

    _leave_column(db, application)
    application.position = None
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
    jamais comptée par erreur parmi les actives qu'on compare au plafond.

    Elle arrive EN HAUT de la colonne de son statut et de son tableau actuels (qui
    ont pu être corrigés pendant l'archivage)."""
    _lock_positions_of(current_user, db)
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

    _place_in_column(db, application, application.board_id, application.status, 0)
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
    """Supprime une candidature ; active, sa colonne est renumérotée."""
    _lock_positions_of(current_user, db)
    application = _get_owned_application(application_id, current_user, db)
    if application.archived_at is None:
        _leave_column(db, application)
    db.delete(application)
    db.commit()
