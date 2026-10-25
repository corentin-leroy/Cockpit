"""Révocation des sessions par compte : `users.token_version`.

Le JWT reste vérifié par sa signature et son expiration, PLUS une comparaison : son
claim `token_version` doit être égal à la colonne `users.token_version`, relue à
chaque requête par get_current_user (l'utilisateur y est déjà chargé : aucune
requête de plus). Incrémenter la colonne révoque d'un coup TOUTES les sessions du
compte ; une réinitialisation de mot de passe réussie le fait.

Un jeton SANS ce claim (émis avant le déploiement, ou par l'ancienne version du code
pendant celui-ci) vaut 0, la valeur de départ de chaque compte : il reste valable
jusqu'à son expiration, tant qu'aucune révocation n'a eu lieu.

Le nom du claim est écrit EN DUR ici, comme les seuils ailleurs : c'est un contrat
avec les jetons déjà émis, un renommage doit faire échouer la suite.
"""

from datetime import datetime, timedelta, timezone

import jwt
import pytest
from sqlalchemy import select, update

from app.models import SecurityToken, TokenPurpose, User
from app.security import JWT_ALGORITHM, _get_secret_key, generate_url_token, hash_token, utcnow

GENERIC_401 = {"detail": "Impossible de valider les identifiants."}


def _decode(token: str) -> dict:
    return jwt.decode(token, _get_secret_key(), algorithms=[JWT_ALGORITHM])


def _forge(user_id: int, **claims) -> dict:
    """En-têtes d'un JWT authentique (vraie clé, non expiré) dont on choisit les
    claims au-delà de `sub` et `exp`."""
    expire = datetime.now(timezone.utc) + timedelta(minutes=5)
    token = jwt.encode(
        {"sub": str(user_id), "exp": expire, **claims}, _get_secret_key(), algorithm=JWT_ALGORITHM
    )
    return {"Authorization": f"Bearer {token}"}


def _user(db_session, email: str) -> User:
    db_session.expire_all()
    return db_session.scalar(select(User).where(User.email == email))


def _set_version(db_session, email: str, version: int) -> None:
    db_session.execute(update(User).where(User.email == email).values(token_version=version))
    db_session.commit()


def _seed_reset_token(db_session, user_id: int) -> str:
    """Lien de réinitialisation valide, semé en base. Renvoie le jeton EN CLAIR."""
    plain = generate_url_token()
    db_session.add(
        SecurityToken(
            token_hash=hash_token(plain),
            purpose=TokenPurpose.PASSWORD_RESET,
            user_id=user_id,
            expires_at=utcnow() + timedelta(hours=1),
        )
    )
    db_session.commit()
    return plain


def _assert_revoked(client, headers: dict) -> None:
    """401 générique, identique à celui d'un jeton invalide, sur deux endpoints
    authentifiés de natures différentes."""
    for path in ("/auth/me", "/boards"):
        response = client.get(path, headers=headers)
        assert response.status_code == 401, (path, response.text)
        assert response.json() == GENERIC_401
        assert response.headers["www-authenticate"] == "Bearer"


def test_the_issued_token_carries_the_stored_version(client, make_user, db_session):
    user = make_user()
    assert _decode(user.token)["token_version"] == 0

    _set_version(db_session, user.email, 3)
    login = client.post("/auth/login", json={"email": user.email, "password": user.password})

    assert _decode(login.json()["access_token"])["token_version"] == 3


def test_a_token_without_the_claim_is_accepted_while_the_version_is_0(
    client, make_user, db_session
):
    """Les jetons émis AVANT le déploiement n'ont pas de claim : ils restent valables."""
    user = make_user()
    user_id = _user(db_session, user.email).id

    response = client.get("/auth/me", headers=_forge(user_id))

    assert response.status_code == 200
    assert response.json()["email"] == user.email


def test_bumping_the_version_revokes_every_existing_session(client, make_user, db_session):
    user = make_user()
    other = make_user()
    user_id = _user(db_session, user.email).id
    without_claim = _forge(user_id)

    _set_version(db_session, user.email, 1)

    _assert_revoked(client, user.headers)
    _assert_revoked(client, without_claim)
    # Révocation PAR COMPTE : les sessions d'un autre compte ne bougent pas.
    assert client.get("/auth/me", headers=other.headers).status_code == 200
    # Une nouvelle connexion rend l'accès, avec la nouvelle version.
    login = client.post("/auth/login", json={"email": user.email, "password": user.password})
    fresh = {"Authorization": f"Bearer {login.json()['access_token']}"}
    assert client.get("/auth/me", headers=fresh).status_code == 200


@pytest.mark.parametrize(
    "stored,claim",
    [
        (1, True),  # True == 1 en Python : un booléen n'est pas une version
        (0, False),
        (1, 1.0),
        (0, 0.0),
        (1, "1"),
        (0, "0"),
        (0, None),  # claim présent mais nul : ce n'est pas un jeton « sans claim »
        (0, []),
        (0, {}),
        (0, -1),
        (0, 2**70),
    ],
)
def test_a_malformed_or_stale_claim_is_a_401_never_a_500(
    client, make_user, db_session, stored, claim
):
    user = make_user()
    user_id = _user(db_session, user.email).id
    _set_version(db_session, user.email, stored)

    _assert_revoked(client, _forge(user_id, token_version=claim))


def test_a_successful_reset_bumps_the_version_and_revokes_every_session(
    client, make_user, db_session
):
    user = make_user()
    user_id = _user(db_session, user.email).id
    without_claim = _forge(user_id)
    plain = _seed_reset_token(db_session, user_id)

    reset = client.post(
        "/auth/reset-password", json={"token": plain, "new_password": "nouveau-mot-de-passe"}
    )

    assert reset.status_code == 200
    assert _user(db_session, user.email).token_version == 1
    _assert_revoked(client, user.headers)
    _assert_revoked(client, without_claim)
    login = client.post(
        "/auth/login", json={"email": user.email, "password": "nouveau-mot-de-passe"}
    )
    assert login.status_code == 200
    assert _decode(login.json()["access_token"])["token_version"] == 1
    fresh = {"Authorization": f"Bearer {login.json()['access_token']}"}
    assert client.get("/auth/me", headers=fresh).status_code == 200


def test_a_refused_reset_revokes_nothing(client, make_user, db_session):
    """Un lien invalide ne touche ni à la version ni aux sessions ouvertes."""
    user = make_user()

    reset = client.post(
        "/auth/reset-password",
        json={"token": generate_url_token(), "new_password": "nouveau-mot-de-passe"},
    )

    assert reset.status_code == 400
    assert _user(db_session, user.email).token_version == 0
    assert client.get("/auth/me", headers=user.headers).status_code == 200
