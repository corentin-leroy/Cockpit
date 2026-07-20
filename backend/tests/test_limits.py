"""Tests des limites de quantité (garde-fous anti-abus).

Les plafonds sont vérifiés CÔTÉ SERVEUR à la création : ces tests tapent l'API
directement, sans passer par le front, pour prouver qu'un client qui contourne
l'interface reste plafonné.

Pour rester rapide, les candidatures de remplissage sont insérées directement en
base (300 requêtes HTTP seraient lentes et n'ajouteraient rien) : c'est l'état
STOCKÉ qui compte pour la limite, et c'est bien lui qu'on met en place.
"""

from app.limits import (
    MAX_APPLICATIONS_PER_USER,
    MAX_BOARDS_PER_USER,
    MAX_REQUEST_BODY_BYTES,
)
from app.models import Application


def _seed_applications(db_session, board_id: int, count: int) -> None:
    """Insère `count` candidatures dans un tableau, sans passer par l'API."""
    db_session.add_all(
        [
            Application(board_id=board_id, title=f"Offre {i}", company="ACME")
            for i in range(count)
        ]
    )
    db_session.commit()


# --- Limite de tableaux ---


def test_cannot_create_board_beyond_limit(client, make_user):
    """Au-delà de MAX_BOARDS_PER_USER : 409, message clair, et rien n'est créé."""
    user = make_user()

    # L'utilisateur a déjà son tableau par défaut : on complète jusqu'au plafond.
    for i in range(MAX_BOARDS_PER_USER - 1):
        created = client.post(
            "/boards", json={"name": f"Tableau {i}"}, headers=user.headers
        )
        assert created.status_code == 201

    boards = client.get("/boards", headers=user.headers).json()
    assert len(boards) == MAX_BOARDS_PER_USER

    # Le suivant est refusé.
    refused = client.post(
        "/boards", json={"name": "Un de trop"}, headers=user.headers
    )
    assert refused.status_code == 409
    assert refused.json()["detail"] == f"Limite de {MAX_BOARDS_PER_USER} tableaux atteinte."

    # Aucun tableau n'a été créé.
    boards_after = client.get("/boards", headers=user.headers).json()
    assert len(boards_after) == MAX_BOARDS_PER_USER


def test_board_limit_is_per_user(client, make_user):
    """Le plafond d'un utilisateur n'affecte pas les autres."""
    alice = make_user()
    bob = make_user()

    for i in range(MAX_BOARDS_PER_USER - 1):
        client.post("/boards", json={"name": f"T{i}"}, headers=alice.headers)
    assert (
        client.post("/boards", json={"name": "x"}, headers=alice.headers).status_code
        == 409
    )

    # Bob, lui, crée sans problème.
    assert (
        client.post("/boards", json={"name": "Le mien"}, headers=bob.headers).status_code
        == 201
    )


# --- Limite de candidatures (globale par utilisateur) ---


def test_cannot_create_application_beyond_limit(client, make_user, db_session):
    """Au-delà de MAX_APPLICATIONS_PER_USER : 409, message clair, rien n'est créé."""
    user = make_user()
    _seed_applications(db_session, user.default_board_id, MAX_APPLICATIONS_PER_USER)

    refused = client.post(
        "/applications",
        json={
            "board_id": user.default_board_id,
            "title": "Une de trop",
            "company": "ACME",
        },
        headers=user.headers,
    )

    assert refused.status_code == 409
    assert (
        refused.json()["detail"]
        == f"Limite de {MAX_APPLICATIONS_PER_USER} candidatures atteinte."
    )

    # Rien n'a été créé : le total est inchangé.
    listed = client.get("/applications", headers=user.headers).json()
    assert len(listed) == MAX_APPLICATIONS_PER_USER


def test_application_limit_is_global_not_per_board(
    client, make_user, make_board, db_session
):
    """La limite est GLOBALE : répartir les candidatures sur plusieurs tableaux ne
    permet pas d'en créer davantage.

    On atteint le plafond en répartissant le total sur deux tableaux, puis on
    tente une création dans le SECOND (qui, seul, est loin du plafond) : refusée."""
    user = make_user()
    second_board = make_board(user)

    half = MAX_APPLICATIONS_PER_USER // 2
    _seed_applications(db_session, user.default_board_id, half)
    _seed_applications(db_session, second_board, MAX_APPLICATIONS_PER_USER - half)

    refused = client.post(
        "/applications",
        json={"board_id": second_board, "title": "Une de trop", "company": "ACME"},
        headers=user.headers,
    )
    assert refused.status_code == 409


def test_application_limit_is_per_user(client, make_user, db_session):
    """Les candidatures d'un autre utilisateur ne comptent pas dans le total."""
    alice = make_user()
    bob = make_user()
    _seed_applications(db_session, alice.default_board_id, MAX_APPLICATIONS_PER_USER)

    # Alice est au plafond...
    assert (
        client.post(
            "/applications",
            json={"board_id": alice.default_board_id, "title": "x", "company": "ACME"},
            headers=alice.headers,
        ).status_code
        == 409
    )

    # ...mais Bob crée normalement.
    assert (
        client.post(
            "/applications",
            json={"board_id": bob.default_board_id, "title": "x", "company": "ACME"},
            headers=bob.headers,
        ).status_code
        == 201
    )


def test_moving_application_is_allowed_at_limit(
    client, make_user, make_board, make_application, db_session
):
    """Étape 4 : déplacer une candidature (PATCH board_id) ne change pas le total,
    donc aucun contrôle de limite ne s'applique au déplacement — même au plafond.

    C'est bien le cas : seule la CRÉATION compte. Et la limite globale ne peut pas
    être contournée par un déplacement, puisque le total reste identique."""
    user = make_user()
    second_board = make_board(user)

    # Une vraie candidature déplaçable + du remplissage pour atteindre le plafond.
    application = make_application(user)
    _seed_applications(
        db_session, user.default_board_id, MAX_APPLICATIONS_PER_USER - 1
    )

    # Au plafond : la création est refusée...
    assert (
        client.post(
            "/applications",
            json={"board_id": second_board, "title": "x", "company": "ACME"},
            headers=user.headers,
        ).status_code
        == 409
    )

    # ...mais le déplacement reste autorisé (le total ne bouge pas).
    moved = client.patch(
        f"/applications/{application['id']}",
        json={"board_id": second_board},
        headers=user.headers,
    )
    assert moved.status_code == 200
    assert moved.json()["board_id"] == second_board


# --- Limite de taille du corps de requête ---


def test_oversized_request_body_is_rejected(client, make_user):
    """Un corps de requête au-delà de MAX_REQUEST_BODY_BYTES est refusé (413),
    avant même d'atteindre l'endpoint."""
    user = make_user()

    response = client.post(
        "/applications",
        json={
            "board_id": user.default_board_id,
            "title": "Offre",
            "company": "ACME",
            "notes": "x" * (MAX_REQUEST_BODY_BYTES + 1),
        },
        headers=user.headers,
    )

    assert response.status_code == 413

    # Rien n'a été créé.
    assert client.get("/applications", headers=user.headers).json() == []


def test_normal_request_body_passes(client, make_user):
    """Garde-fou du garde-fou : une charge utile normale n'est pas bloquée."""
    user = make_user()

    response = client.post(
        "/applications",
        json={
            "board_id": user.default_board_id,
            "title": "Offre",
            "company": "ACME",
            "notes": "Des notes raisonnables.",
        },
        headers=user.headers,
    )

    assert response.status_code == 201
