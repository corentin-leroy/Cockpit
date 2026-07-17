"""Tests d'ownership sur les candidatures (Application).

L'ownership est ici EN CHAÎNE : application → board → user. Toute la logique de
cloisonnement repose sur la jointure sur board.user_id. On vérifie qu'aucun
chemin (lecture, écriture, création, déplacement) ne laisse un utilisateur
atteindre une candidature ou un tableau qui ne lui appartient pas — toujours 404.
"""


def test_user_cannot_read_others_application(client, make_user, make_application):
    """A ne peut pas lire une candidature d'un tableau de B : 404."""
    alice = make_user()
    bob = make_user()
    bob_app = make_application(bob)

    response = client.get(f"/applications/{bob_app['id']}", headers=alice.headers)
    assert response.status_code == 404


def test_user_cannot_update_others_application(client, make_user, make_application):
    """A ne peut pas modifier une candidature de B : 404."""
    alice = make_user()
    bob = make_user()
    bob_app = make_application(bob)

    response = client.patch(
        f"/applications/{bob_app['id']}",
        json={"title": "Piraté"},
        headers=alice.headers,
    )
    assert response.status_code == 404


def test_user_cannot_delete_others_application(client, make_user, make_application):
    """A ne peut pas supprimer une candidature de B : 404, et elle survit."""
    alice = make_user()
    bob = make_user()
    bob_app = make_application(bob)

    response = client.delete(f"/applications/{bob_app['id']}", headers=alice.headers)
    assert response.status_code == 404

    still_there = client.get(f"/applications/{bob_app['id']}", headers=bob.headers)
    assert still_there.status_code == 200


def test_user_cannot_create_application_in_others_board(client, make_user, make_board):
    """A ne peut pas créer une candidature dans un tableau de B : 404.

    Le board cible vient du payload, mais le serveur vérifie qu'il appartient à
    l'appelant — sinon on pourrait déposer une carte chez autrui."""
    alice = make_user()
    bob = make_user()
    bob_board = make_board(bob)

    response = client.post(
        "/applications",
        json={"board_id": bob_board, "title": "Dev", "company": "ACME"},
        headers=alice.headers,
    )
    assert response.status_code == 404


def test_user_cannot_move_own_application_to_others_board(
    client, make_user, make_board, make_application
):
    """A ne peut pas déplacer SA candidature vers un tableau de B : 404.

    C'est le pendant du contrôle à la création, appliqué au PATCH board_id : sans
    lui, un client « pousserait » sa carte dans le tableau d'un autre."""
    alice = make_user()
    bob = make_user()
    bob_board = make_board(bob)
    alice_app = make_application(alice)

    response = client.patch(
        f"/applications/{alice_app['id']}",
        json={"board_id": bob_board},
        headers=alice.headers,
    )
    assert response.status_code == 404

    # La candidature n'a pas bougé : elle est toujours dans le tableau d'Alice.
    unchanged = client.get(f"/applications/{alice_app['id']}", headers=alice.headers).json()
    assert unchanged["board_id"] == alice.default_board_id


def test_application_ownership_violations_never_return_403(
    client, make_user, make_application
):
    """Comme pour les tableaux : les violations d'ownership sont en 404, jamais 403."""
    alice = make_user()
    bob = make_user()
    bob_app = make_application(bob)

    responses = [
        client.get(f"/applications/{bob_app['id']}", headers=alice.headers),
        client.patch(
            f"/applications/{bob_app['id']}", json={"title": "x"}, headers=alice.headers
        ),
        client.delete(f"/applications/{bob_app['id']}", headers=alice.headers),
    ]
    assert all(r.status_code == 404 for r in responses)
    assert all(r.status_code != 403 for r in responses)
