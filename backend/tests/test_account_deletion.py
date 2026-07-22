"""Suppression de compte (DELETE /auth/me) et cascade de suppression.

Deux choses sont vérifiées ici, et elles sont indissociables :

1. Le CONTRÔLE D'ACCÈS : le mot de passe courant est exigé en plus du JWT. Une
   régression sur ce point transformerait un token volé en droit de destruction.
2. L'EFFACEMENT RÉEL : plus aucune ligne rattachée à l'utilisateur ne subsiste.
   C'est le test qui donne sa valeur à la cascade déclarée dans le schéma — un
   `ondelete="CASCADE"` non appliqué (PRAGMA SQLite oublié, par exemple) laisse
   des orphelins en silence, sans la moindre erreur visible côté API.

Les assertions portent sur l'ÉTAT STOCKÉ (db_session), pas sur des réponses
d'API : après suppression du compte, plus aucun appel authentifié n'est possible,
et c'est justement la base qu'on veut interroger.
"""

from sqlalchemy import func, select

from app.models import Application, Board, SecurityToken, User


def _count(db_session, model, **filters) -> int:
    """Compte les lignes d'une table, avec filtres d'égalité optionnels."""
    statement = select(func.count()).select_from(model)
    for column, value in filters.items():
        statement = statement.where(getattr(model, column) == value)
    return db_session.scalar(statement)


def test_delete_account_removes_user_and_all_owned_data(
    client, db_session, make_user, make_board, make_application
):
    """Le compte supprimé emporte tableaux, candidatures et jetons de sécurité."""
    user = make_user()
    second_board = make_board(user, name="Alternance")
    make_application(user)  # dans le tableau par défaut
    make_application(user, board_id=second_board)

    # L'inscription a créé un jeton de vérification d'email : il doit disparaître
    # aussi. On le vérifie présent AVANT, sans quoi le test passerait à vide.
    user_row = db_session.scalar(select(User).where(User.email == user.email))
    assert user_row is not None
    user_id = user_row.id
    assert _count(db_session, SecurityToken, user_id=user_id) >= 1
    assert _count(db_session, Board, user_id=user_id) == 2

    response = client.request(
        "DELETE",
        "/auth/me",
        json={"password": user.password},
        headers=user.headers,
    )
    assert response.status_code == 204, response.text

    # La session de test a pu mettre en cache les objets lus plus haut : on la
    # vide pour relire l'état réellement commité par la requête.
    db_session.expire_all()

    assert _count(db_session, User, id=user_id) == 0
    assert _count(db_session, Board, user_id=user_id) == 0
    assert _count(db_session, SecurityToken, user_id=user_id) == 0
    # Les candidatures ne portent pas user_id : la cascade les atteint en CHAÎNE
    # (users → boards → applications). On vérifie donc qu'il n'en reste aucune.
    assert _count(db_session, Application) == 0


def test_delete_account_with_wrong_password_is_refused(
    client, db_session, make_user, make_application
):
    """Mauvais mot de passe → 403, et RIEN n'est supprimé."""
    user = make_user()
    make_application(user)

    response = client.request(
        "DELETE",
        "/auth/me",
        json={"password": "mauvais-mot-de-passe"},
        headers=user.headers,
    )
    assert response.status_code == 403

    # Le message reste sobre et ne divulgue rien d'autre que la cause.
    assert "incorrect" in response.json()["detail"].lower()

    db_session.expire_all()
    user_row = db_session.scalar(select(User).where(User.email == user.email))
    assert user_row is not None
    assert _count(db_session, Board, user_id=user_row.id) == 1
    assert _count(db_session, Application) == 1

    # Le compte reste pleinement utilisable : le refus n'a pas cassé la session.
    assert client.get("/auth/me", headers=user.headers).status_code == 200


def test_delete_account_requires_authentication(client, make_user):
    """Sans token, l'endpoint est inaccessible — même avec le bon mot de passe."""
    user = make_user()

    response = client.request(
        "DELETE", "/auth/me", json={"password": user.password}
    )
    assert response.status_code == 401


def test_delete_account_leaves_other_users_untouched(
    client, db_session, make_user, make_board, make_application
):
    """La suppression est strictement cloisonnée : l'autre utilisateur est intact.

    C'est le pendant des tests d'ownership : une cascade trop large (ou une
    clause WHERE manquante) détruirait les données d'un tiers, sans que le
    compte supprimé, lui, ne montre quoi que ce soit d'anormal.
    """
    alice = make_user()
    bob = make_user()
    make_board(bob, name="Stage")
    make_application(bob)
    make_application(bob)

    bob_row = db_session.scalar(select(User).where(User.email == bob.email))
    bob_id = bob_row.id

    response = client.request(
        "DELETE",
        "/auth/me",
        json={"password": alice.password},
        headers=alice.headers,
    )
    assert response.status_code == 204

    db_session.expire_all()

    # Bob : compte, tableaux (défaut + Stage), candidatures et jeton intacts.
    assert _count(db_session, User, id=bob_id) == 1
    assert _count(db_session, Board, user_id=bob_id) == 2
    assert _count(db_session, Application) == 2
    assert _count(db_session, SecurityToken, user_id=bob_id) >= 1

    # Et il continue d'accéder normalement à ses données.
    assert client.get("/auth/me", headers=bob.headers).status_code == 200
    assert len(client.get("/boards", headers=bob.headers).json()) == 2


def test_deleting_board_still_removes_its_applications(
    client, db_session, make_user, make_board, make_application
):
    """Garde-fou de non-régression : la cascade tableau → candidatures tient.

    `passive_deletes=True` a changé le SQL émis (plus de DELETE individuels sur
    les candidatures, c'est la base qui propage). Le comportement observable, lui,
    doit être rigoureusement identique à avant.
    """
    user = make_user()
    board = make_board(user, name="À supprimer")
    make_application(user, board_id=board)
    make_application(user, board_id=board)
    kept = make_application(user)  # dans le tableau par défaut, doit survivre

    assert _count(db_session, Application) == 3

    assert client.delete(f"/boards/{board}", headers=user.headers).status_code == 204

    db_session.expire_all()
    assert _count(db_session, Board, id=board) == 0
    assert _count(db_session, Application) == 1
    assert _count(db_session, Application, id=kept["id"]) == 1
