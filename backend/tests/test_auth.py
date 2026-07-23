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


# --- Expiration du jeton de session ---------------------------------------
#
# La durée de vie est passée de 60 minutes à 12 heures (ACCESS_TOKEN_EXPIRE_MINUTES).
# Les jetons étant SANS ÉTAT, donc irrévocables, cette expiration est la seule
# borne à l'exploitation d'un jeton volé : c'est désormais le mécanisme de
# sécurité le plus important de la chaîne d'authentification, et il n'était
# couvert par aucun test. Une régression ici (validation de `exp` désactivée,
# durée mal lue) serait totalement silencieuse — tout continuerait de fonctionner,
# les jetons ne cesseraient simplement jamais d'être valables.


def _forge_token(subject: str, *, minutes_offset: int) -> str:
    """Forge un JWT valide signé, dont l'expiration est décalée de `minutes_offset`.

    On signe avec la vraie clé et le vrai algorithme : seul `exp` est manipulé.
    Le jeton est donc authentique à tout point de vue sauf sa date — c'est bien
    l'expiration qu'on teste, et rien d'autre.
    """
    from datetime import datetime, timedelta, timezone

    import jwt

    from app.security import JWT_ALGORITHM, _get_secret_key

    expire = datetime.now(timezone.utc) + timedelta(minutes=minutes_offset)
    return jwt.encode(
        {"sub": subject, "exp": expire}, _get_secret_key(), algorithm=JWT_ALGORITHM
    )


def test_expired_token_is_rejected(client, make_user):
    """Un jeton expiré est refusé en 401 sur un endpoint authentifié."""
    user = make_user()

    # Le compte est bien joignable avec son jeton courant : sans ce contrôle, un
    # 401 dû à toute autre cause ferait passer le test pour la mauvaise raison.
    assert client.get("/auth/me", headers=user.headers).status_code == 200

    me = client.get("/auth/me", headers=user.headers).json()
    expired = _forge_token(str(me["id"]), minutes_offset=-1)

    response = client.get("/auth/me", headers={"Authorization": f"Bearer {expired}"})
    assert response.status_code == 401


def test_expired_token_is_rejected_on_data_endpoints(client, make_user):
    """L'expiration vaut pour TOUTE la surface authentifiée, pas seulement /auth/me."""
    user = make_user()
    me = client.get("/auth/me", headers=user.headers).json()
    expired_headers = {
        "Authorization": f"Bearer {_forge_token(str(me['id']), minutes_offset=-1)}"
    }

    assert client.get("/boards", headers=expired_headers).status_code == 401
    assert client.get("/applications", headers=expired_headers).status_code == 401
    assert (
        client.post(
            "/boards", json={"name": "Test"}, headers=expired_headers
        ).status_code
        == 401
    )


def test_issued_token_expires_after_configured_delay(client, make_user):
    """Le jeton émis au login porte bien l'expiration configurée.

    Vérifie le CÂBLAGE de ACCESS_TOKEN_EXPIRE_MINUTES jusqu'au claim `exp` : une
    variable lue mais jamais appliquée laisserait passer tous les autres tests.
    """
    from datetime import datetime, timezone

    import jwt

    from app.security import ACCESS_TOKEN_EXPIRE_MINUTES, JWT_ALGORITHM, _get_secret_key

    user = make_user()
    payload = jwt.decode(user.token, _get_secret_key(), algorithms=[JWT_ALGORITHM])

    remaining_minutes = (
        datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
        - datetime.now(timezone.utc)
    ).total_seconds() / 60

    # Tolérance d'une minute : le jeton a été émis quelques instants plus tôt.
    assert abs(remaining_minutes - ACCESS_TOKEN_EXPIRE_MINUTES) < 1


def test_token_signed_with_another_key_is_rejected(client, make_user):
    """Un jeton non signé par le serveur est refusé, même non expiré.

    Corollaire du caractère sans état : la signature est le SEUL rempart, il n'y
    a aucune session stockée à confronter.
    """
    from datetime import datetime, timedelta, timezone

    import jwt

    from app.security import JWT_ALGORITHM

    user = make_user()
    me = client.get("/auth/me", headers=user.headers).json()

    forged = jwt.encode(
        {
            "sub": str(me["id"]),
            "exp": datetime.now(timezone.utc) + timedelta(hours=12),
        },
        "une-autre-cle-que-celle-du-serveur",
        algorithm=JWT_ALGORITHM,
    )

    response = client.get("/auth/me", headers={"Authorization": f"Bearer {forged}"})
    assert response.status_code == 401
