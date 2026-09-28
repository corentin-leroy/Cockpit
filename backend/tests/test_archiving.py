"""Archivage des candidatures : `archived_at`, les deux endpoints dédiés, le
filtre par défaut des listes, les deux plafonds, et la correction du comptage
des 300 actives.

Portée volontairement ciblée, comme le reste de la suite (cf. CLAUDE.md,
« Tests backend ») : les points où une régression serait silencieuse et
coûteuse — une archivée qui refuirait dans le kanban, un plafond contournable,
un statut modifié par erreur à l'archivage.
"""

from sqlalchemy import select

from app.limits import MAX_APPLICATIONS_PER_USER, MAX_ARCHIVED_APPLICATIONS_PER_USER
from app.models import Application, Board


def _seed_applications(db_session, board_id: int, count: int, *, archived: bool) -> None:
    """Insère `count` candidatures DIRECTEMENT en base (comme test_limits.py) :
    2000 requêtes HTTP seraient lentes et n'apporteraient rien — c'est l'état
    STOCKÉ qui détermine les plafonds, et c'est bien lui qu'on met en place."""
    from app.security import utcnow

    db_session.add_all(
        [
            Application(
                board_id=board_id,
                title=f"Offre {i}",
                company="ACME",
                archived_at=utcnow() if archived else None,
            )
            for i in range(count)
        ]
    )
    db_session.commit()


ARCHIVE_CAP_DETAIL = (
    f"Limite de {MAX_ARCHIVED_APPLICATIONS_PER_USER} candidatures archivées "
    "atteinte. Supprimez d'anciennes archives pour en archiver de nouvelles."
)
ACTIVE_CAP_DETAIL = (
    f"Limite de {MAX_APPLICATIONS_PER_USER} candidatures actives atteinte. "
    "Supprimez ou archivez une candidature active pour faire de la place."
)


# ---------------------------------------------------------------------------
# Comportement de base : archiver / désarchiver
# ---------------------------------------------------------------------------


def test_archive_sets_archived_at_and_keeps_status(client, make_user, make_application):
    """Archiver pose `archived_at`, laisse le STATUT inchangé, renvoie 200."""
    user = make_user()
    application = make_application(user)
    client.patch(
        f"/applications/{application['id']}", json={"status": "applied"}, headers=user.headers
    )

    response = client.post(f"/applications/{application['id']}/archive", headers=user.headers)

    assert response.status_code == 200
    body = response.json()
    assert body["archived_at"] is not None
    assert body["status"] == "applied"  # conservé tel quel, pas remis à "saved"


def test_unarchive_clears_archived_at_and_keeps_status(client, make_user, make_application):
    """Désarchiver remet `archived_at` à null, statut toujours inchangé."""
    user = make_user()
    application = make_application(user)
    client.patch(
        f"/applications/{application['id']}", json={"status": "interview"}, headers=user.headers
    )
    client.post(f"/applications/{application['id']}/archive", headers=user.headers)

    response = client.post(f"/applications/{application['id']}/unarchive", headers=user.headers)

    assert response.status_code == 200
    body = response.json()
    assert body["archived_at"] is None
    assert body["status"] == "interview"


def test_archiving_an_already_archived_application_is_a_conflict(client, make_user, make_application):
    """409 EXPLICITE, pas d'idempotence silencieuse : un succès sur une action
    qui n'a rien fait masquerait un bug côté client."""
    user = make_user()
    application = make_application(user)
    client.post(f"/applications/{application['id']}/archive", headers=user.headers)

    response = client.post(f"/applications/{application['id']}/archive", headers=user.headers)

    assert response.status_code == 409
    assert response.json()["detail"] == "Cette candidature est déjà archivée."


def test_unarchiving_an_active_application_is_a_conflict(client, make_user, make_application):
    """Même principe, dans l'autre sens : désarchiver une candidature déjà
    active est refusé, pas un no-op silencieux."""
    user = make_user()
    application = make_application(user)

    response = client.post(f"/applications/{application['id']}/unarchive", headers=user.headers)

    assert response.status_code == 409
    assert response.json()["detail"] == "Cette candidature n'est pas archivée."


# ---------------------------------------------------------------------------
# Ownership
# ---------------------------------------------------------------------------


def test_archive_and_unarchive_respect_ownership(client, make_user, make_application):
    """Archiver/désarchiver la candidature d'un AUTRE utilisateur → 404, comme
    partout ailleurs (ne pas confirmer l'existence de l'id à autrui)."""
    owner = make_user()
    intruder = make_user()
    application = make_application(owner)

    archive_response = client.post(
        f"/applications/{application['id']}/archive", headers=intruder.headers
    )
    assert archive_response.status_code == 404

    client.post(f"/applications/{application['id']}/archive", headers=owner.headers)
    unarchive_response = client.post(
        f"/applications/{application['id']}/unarchive", headers=intruder.headers
    )
    assert unarchive_response.status_code == 404


# ---------------------------------------------------------------------------
# Filtre par défaut des listes
# ---------------------------------------------------------------------------


def test_archived_application_is_excluded_from_default_list(client, make_user, make_application):
    """Une archivée n'apparaît JAMAIS dans une liste par défaut ; `?archived=true`
    n'affiche QUE les archivées, jamais un mélange."""
    user = make_user()
    active = make_application(user, title="Active")
    archived = make_application(user, title="À archiver")
    client.post(f"/applications/{archived['id']}/archive", headers=user.headers)

    default_ids = [a["id"] for a in client.get("/applications", headers=user.headers).json()]
    assert archived["id"] not in default_ids
    assert active["id"] in default_ids

    archived_response = client.get("/applications?archived=true", headers=user.headers).json()
    archived_ids = [a["id"] for a in archived_response]
    assert archived["id"] in archived_ids
    assert active["id"] not in archived_ids
    assert all(a["archived_at"] is not None for a in archived_response)


def test_archived_filter_combines_with_board_and_status_filters(
    client, make_user, make_board, make_application
):
    """`archived` se combine avec `board_id` et `status_filter` déjà existants,
    sans que l'un masque l'autre."""
    user = make_user()
    other_board = make_board(user)
    matching = make_application(user, board_id=other_board, title="Cherchée")
    client.patch(f"/applications/{matching['id']}", json={"status": "applied"}, headers=user.headers)
    client.post(f"/applications/{matching['id']}/archive", headers=user.headers)

    # Même tableau, même statut, mais PAS archivée : ne doit pas apparaître.
    make_application(user, board_id=other_board, title="Pas archivée")
    # Archivée mais autre tableau : ne doit pas apparaître non plus.
    elsewhere = make_application(user, title="Autre tableau")
    client.post(f"/applications/{elsewhere['id']}/archive", headers=user.headers)

    response = client.get(
        f"/applications?archived=true&board_id={other_board}&status_filter=applied",
        headers=user.headers,
    )
    ids = [a["id"] for a in response.json()]
    assert ids == [matching["id"]]


# ---------------------------------------------------------------------------
# Accès par identifiant : PAS filtré (décision explicite, confirmée)
# ---------------------------------------------------------------------------


def test_get_and_delete_still_work_on_an_archived_application(client, make_user, make_application):
    """GET et DELETE par identifiant continuent de fonctionner sur une
    candidature archivée : la correction depuis la page d'archives en dépend."""
    user = make_user()
    application = make_application(user)
    client.post(f"/applications/{application['id']}/archive", headers=user.headers)

    get_response = client.get(f"/applications/{application['id']}", headers=user.headers)
    assert get_response.status_code == 200

    patch_response = client.patch(
        f"/applications/{application['id']}", json={"notes": "corrigée"}, headers=user.headers
    )
    assert patch_response.status_code == 200
    assert patch_response.json()["archived_at"] is not None  # le PATCH ne désarchive pas

    delete_response = client.delete(f"/applications/{application['id']}", headers=user.headers)
    assert delete_response.status_code == 204


# ---------------------------------------------------------------------------
# Les deux plafonds
# ---------------------------------------------------------------------------


def test_cannot_archive_beyond_the_archived_cap(client, db_session, make_user, make_application):
    """Au-delà de MAX_ARCHIVED_APPLICATIONS_PER_USER : 409 avec le message
    EXACT attendu, et la candidature visée reste active (rien n'est modifié)."""
    user = make_user()
    _seed_applications(db_session, user.default_board_id, MAX_ARCHIVED_APPLICATIONS_PER_USER, archived=True)
    application = make_application(user)

    response = client.post(f"/applications/{application['id']}/archive", headers=user.headers)

    assert response.status_code == 409
    assert response.json()["detail"] == ARCHIVE_CAP_DETAIL
    assert client.get(f"/applications/{application['id']}", headers=user.headers).json()["archived_at"] is None


def test_cannot_unarchive_when_active_cap_is_reached(client, db_session, make_user, make_application):
    """Sans ce contrôle, la limite de 300 actives se contournerait en archivant
    puis désarchivant. La candidature reste archivée après le refus."""
    user = make_user()
    application = make_application(user)
    client.post(f"/applications/{application['id']}/archive", headers=user.headers)
    # 300 actives DE PLUS : la candidature visée est encore archivée à cet
    # instant, donc jamais comptée par erreur parmi ces 300.
    _seed_applications(db_session, user.default_board_id, MAX_APPLICATIONS_PER_USER, archived=False)

    response = client.post(f"/applications/{application['id']}/unarchive", headers=user.headers)

    assert response.status_code == 409
    assert response.json()["detail"] == ACTIVE_CAP_DETAIL
    assert client.get(f"/applications/{application['id']}", headers=user.headers).json()["archived_at"] is not None


def test_creating_application_counts_only_active_towards_the_cap(
    client, db_session, make_user, make_application
):
    """LE test de la correction : sans elle, ce test échouerait (300 actives +
    des archivées auraient bloqué la création malgré des actives sous le
    plafond). Archiver doit réellement libérer de la place."""
    user = make_user()
    # 299 actives + 50 archivées : le TOTAL (349) dépasse largement 300, mais
    # les ACTIVES (299) restent sous le plafond.
    _seed_applications(db_session, user.default_board_id, MAX_APPLICATIONS_PER_USER - 1, archived=False)
    _seed_applications(db_session, user.default_board_id, 50, archived=True)

    response = client.post(
        "/applications",
        json={"board_id": user.default_board_id, "title": "La 300e active", "company": "ACME"},
        headers=user.headers,
    )
    assert response.status_code == 201

    # Une candidature de plus : 300 actives pile atteintes, la suivante est refusée.
    over_response = client.post(
        "/applications",
        json={"board_id": user.default_board_id, "title": "La 301e", "company": "ACME"},
        headers=user.headers,
    )
    assert over_response.status_code == 409


# ---------------------------------------------------------------------------
# Cascade de suppression d'un tableau
# ---------------------------------------------------------------------------


def test_board_deletion_cascades_archived_applications(
    client, db_session, make_user, make_board, make_application
):
    """Supprimer un tableau supprime RÉELLEMENT ses candidatures archivées, pas
    seulement les actives — assertion sur l'ÉTAT STOCKÉ (comme
    test_account_deletion.py) : une cascade non appliquée ne produirait aucune
    erreur d'API."""
    user = make_user()
    other_board = make_board(user)  # 2e tableau : celui-ci n'est pas le dernier
    application = make_application(user, board_id=other_board)
    client.post(f"/applications/{application['id']}/archive", headers=user.headers)

    response = client.delete(f"/boards/{other_board}", headers=user.headers)

    assert response.status_code == 204
    assert db_session.get(Application, application["id"]) is None
    assert db_session.get(Board, other_board) is None


# ---------------------------------------------------------------------------
# GET /boards : compteurs
# ---------------------------------------------------------------------------


def test_board_read_exposes_application_counts(client, make_user, make_application):
    """active_applications_count / archived_applications_count reflètent l'état
    réel, y compris pour un tableau flambant neuf (0/0)."""
    user = make_user()
    fresh = client.get("/boards", headers=user.headers).json()[0]
    assert fresh["active_applications_count"] == 0
    assert fresh["archived_applications_count"] == 0

    active = make_application(user)
    to_archive = make_application(user)
    client.post(f"/applications/{to_archive['id']}/archive", headers=user.headers)

    updated = client.get("/boards", headers=user.headers).json()[0]
    assert updated["active_applications_count"] == 1
    assert updated["archived_applications_count"] == 1
