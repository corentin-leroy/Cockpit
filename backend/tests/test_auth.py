"""Tests d'authentification : inscription, connexion, anti-énumération.

On cible les points où une régression serait silencieuse et coûteuse : fuite du
mot de passe, oubli du contrôle de doublon, et surtout perte de l'anti-énumération
(un login qui distinguerait « email inconnu » de « mot de passe faux »).
"""

from app.models import User


def test_register_success_hashes_password(client, db_session):
    """Inscription réussie : 201, réponse sans hash, et mot de passe JAMAIS stocké
    en clair (on relit la base pour le prouver)."""
    response = client.post(
        "/auth/register",
        json={"email": "alice@example.com", "password": "supersecret"},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "alice@example.com"
    assert body["is_verified"] is False
    # Le contrat de sortie n'expose aucun champ de mot de passe.
    assert "password" not in body
    assert "hashed_password" not in body

    # Preuve directe côté stockage : la valeur en base n'est pas le clair, et
    # c'est bien une empreinte qui vérifie le mot de passe.
    stored = db_session.query(User).filter_by(email="alice@example.com").one()
    assert stored.hashed_password != "supersecret"
    from app.security import verify_password

    assert verify_password("supersecret", stored.hashed_password) is True


def test_register_duplicate_email_conflict(client):
    """Un email déjà pris renvoie 409 Conflict."""
    payload = {"email": "bob@example.com", "password": "password123"}
    first = client.post("/auth/register", json=payload)
    assert first.status_code == 201

    second = client.post("/auth/register", json=payload)
    assert second.status_code == 409


def test_login_success_returns_token(client):
    """Bons identifiants : 200 + un token bearer non vide."""
    client.post(
        "/auth/register",
        json={"email": "carol@example.com", "password": "password123"},
    )

    response = client.post(
        "/auth/login",
        json={"email": "carol@example.com", "password": "password123"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]


def test_login_wrong_password_is_401(client):
    """Mauvais mot de passe : 401."""
    client.post(
        "/auth/register",
        json={"email": "dave@example.com", "password": "password123"},
    )

    response = client.post(
        "/auth/login",
        json={"email": "dave@example.com", "password": "wrong-password"},
    )

    assert response.status_code == 401


def test_login_unknown_email_is_401(client):
    """Email inexistant : 401 (et non 404, qui trahirait l'absence de compte)."""
    response = client.post(
        "/auth/login",
        json={"email": "nobody@example.com", "password": "password123"},
    )

    assert response.status_code == 401


def test_login_failures_are_indistinguishable(client):
    """Anti-énumération : « mauvais mot de passe » et « email inconnu » renvoient
    EXACTEMENT la même réponse (même status, même corps). Sans ça, on pourrait
    savoir quels emails ont un compte."""
    client.post(
        "/auth/register",
        json={"email": "erin@example.com", "password": "password123"},
    )

    wrong_password = client.post(
        "/auth/login",
        json={"email": "erin@example.com", "password": "wrong-password"},
    )
    unknown_email = client.post(
        "/auth/login",
        json={"email": "ghost@example.com", "password": "wrong-password"},
    )

    assert wrong_password.status_code == unknown_email.status_code == 401
    assert wrong_password.json() == unknown_email.json()
