"""Tests d'ownership et de règle métier sur les tableaux (Board).

Le point sensible : le cloisonnement doit renvoyer 404 (et jamais 403) quand un
utilisateur touche au tableau d'un autre — un 403 confirmerait que l'id existe,
ce qui suffit à énumérer les tableaux d'autrui.
"""


def test_new_user_has_one_default_board(client, make_user):
    """À l'inscription, l'utilisateur a exactement un tableau par défaut."""
    user = make_user()

    boards = client.get("/boards", headers=user.headers).json()
    assert len(boards) == 1
    assert boards[0]["name"] == "Mes candidatures"


def test_user_cannot_read_others_board(client, make_user, make_board):
    """A ne peut pas lire le tableau de B.

    Il n'existe pas d'endpoint GET /boards/{id} : la lecture passe par la liste,
    qui est cloisonnée par propriétaire. On vérifie donc que le tableau de B
    n'apparaît JAMAIS dans la liste d'A."""
    alice = make_user()
    bob = make_user()
    bob_board = make_board(bob)

    alice_board_ids = [b["id"] for b in client.get("/boards", headers=alice.headers).json()]
    assert bob_board not in alice_board_ids


def test_user_cannot_update_others_board(client, make_user, make_board):
    """A ne peut pas modifier (PATCH) un tableau de B : 404."""
    alice = make_user()
    bob = make_user()
    bob_board = make_board(bob)

    response = client.patch(
        f"/boards/{bob_board}",
        json={"name": "Piraté"},
        headers=alice.headers,
    )
    assert response.status_code == 404


def test_user_cannot_delete_others_board(client, make_user, make_board):
    """A ne peut pas supprimer (DELETE) un tableau de B : 404.

    On vérifie aussi que le tableau existe toujours côté B après coup."""
    alice = make_user()
    bob = make_user()
    bob_board = make_board(bob)

    response = client.delete(f"/boards/{bob_board}", headers=alice.headers)
    assert response.status_code == 404

    # Le tableau de B est intact (toujours présent dans SA liste).
    bob_board_ids = [b["id"] for b in client.get("/boards", headers=bob.headers).json()]
    assert bob_board in bob_board_ids


def test_ownership_violations_never_return_403(client, make_user, make_board):
    """Sur les endpoints mutables (PATCH, DELETE), toute violation d'ownership est
    en 404, jamais 403 : un 403 confirmerait que l'id existe."""
    alice = make_user()
    bob = make_user()
    bob_board = make_board(bob)

    responses = [
        client.patch(f"/boards/{bob_board}", json={"name": "x"}, headers=alice.headers),
        client.delete(f"/boards/{bob_board}", headers=alice.headers),
    ]
    assert all(r.status_code == 404 for r in responses)
    assert all(r.status_code != 403 for r in responses)


def test_cannot_delete_last_board(client, make_user):
    """Règle métier : supprimer le DERNIER tableau est refusé (409)."""
    user = make_user()

    response = client.delete(f"/boards/{user.default_board_id}", headers=user.headers)
    assert response.status_code == 409

    # Le tableau est toujours là.
    boards = client.get("/boards", headers=user.headers).json()
    assert len(boards) == 1


def test_can_delete_board_when_another_remains(client, make_user, make_board):
    """Suppression autorisée (204) tant qu'il reste au moins un autre tableau."""
    user = make_user()
    second_board = make_board(user)

    response = client.delete(f"/boards/{second_board}", headers=user.headers)
    assert response.status_code == 204

    # Il reste le tableau par défaut.
    boards = client.get("/boards", headers=user.headers).json()
    assert len(boards) == 1
    assert boards[0]["id"] == user.default_board_id
