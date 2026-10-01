"""Mot de passe CHOISI limité à 72 OCTETS UTF-8 (inscription et réinitialisation).

bcrypt ignore tout ce qui dépasse 72 octets : « a » x 72 + « X » et « a » x 72 + « Y »
ouvrent le même compte. Accepter 128 caractères laissait croire que toute la longueur
compte. La limite est en OCTETS (un « é » en pèse 2), le message parle en caractères.

Le mot de passe PRÉSENTÉ (connexion, suppression de compte) garde sa borne technique
de 4096 octets : un compte existant au mot de passe plus long doit continuer de
fonctionner, bcrypt le tronquant à la connexion exactement comme à l'inscription.

Le chiffre 72 est écrit EN DUR dans ces tests, volontairement : il fixe le contrat
(c'est la limite de bcrypt), il ne le suit pas depuis limits.py.
"""

from datetime import timedelta

import pytest
from sqlalchemy import select

from app.models import SecurityToken, TokenPurpose, User
from app.security import generate_url_token, hash_password, hash_token, utcnow, verify_password

REGISTER_TOO_LONG = (
    "Le mot de passe est trop long : 72 caractères maximum, moins s'il contient des accents."
)
RESET_TOO_LONG = (
    "Le nouveau mot de passe est trop long : 72 caractères maximum, moins s'il contient des accents."
)

# (identifiant, mot de passe, accepté ?). Octets : ASCII 1, « é » 2, émoji 4.
BOUNDARY_CASES = [
    ("ascii 72 octets", "a" * 72, True),
    ("ascii 73 octets", "a" * 73, False),
    ("36 é = 72 octets", "é" * 36, True),
    ("37 é = 74 octets", "é" * 37, False),
    ("70 a + é = 72 octets", "a" * 70 + "é", True),
    ("71 a + é = 73 octets", "a" * 71 + "é", False),
    ("18 émojis = 72 octets", "😀" * 18, True),
    ("19 émojis = 76 octets", "😀" * 19, False),
]
IDS = [case[0] for case in BOUNDARY_CASES]


def _seed_account(db_session, email: str, password: str = "ancien-mot-de-passe") -> int:
    user = User(email=email, hashed_password=hash_password(password), is_verified=False)
    db_session.add(user)
    db_session.commit()
    return user.id


def _seed_reset_token(db_session, user_id: int) -> str:
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


def _consumed_at(db_session, plain: str):
    db_session.expire_all()  # la session de test peut avoir mis la ligne en cache
    return db_session.scalar(
        select(SecurityToken.consumed_at).where(SecurityToken.token_hash == hash_token(plain))
    )


# ---------------------------------------------------------------------------
# Inscription et réinitialisation : 72 octets acceptés, 73 refusés
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("label,password,accepted", BOUNDARY_CASES, ids=IDS)
def test_registration_bound_is_72_bytes(client, label, password, accepted):
    response = client.post(
        "/auth/register", json={"email": "bound@example.com", "password": password}
    )

    if accepted:
        assert response.status_code == 201, response.text
    else:
        assert response.status_code == 422
        body = response.json()
        assert body["detail"] == REGISTER_TOO_LONG
        assert body["errors"] == [{"field": "password", "message": REGISTER_TOO_LONG}]


@pytest.mark.parametrize("label,password,accepted", BOUNDARY_CASES, ids=IDS)
def test_reset_bound_is_72_bytes(client, db_session, label, password, accepted):
    user_id = _seed_account(db_session, "reset-bound@example.com")
    plain = _seed_reset_token(db_session, user_id)

    response = client.post(
        "/auth/reset-password", json={"token": plain, "new_password": password}
    )

    if accepted:
        assert response.status_code == 200, response.text
        db_session.expire_all()
        assert verify_password(password, db_session.get(User, user_id).hashed_password)
    else:
        assert response.status_code == 422
        body = response.json()
        assert body["detail"] == RESET_TOO_LONG
        assert body["errors"] == [{"field": "new_password", "message": RESET_TOO_LONG}]


def test_minimum_stays_8_characters(client):
    """Le minimum ne change pas : 8 CARACTÈRES (8 « é » font 16 octets, acceptés)."""
    assert client.post(
        "/auth/register", json={"email": "min1@example.com", "password": "a" * 7}
    ).status_code == 422
    assert client.post(
        "/auth/register", json={"email": "min2@example.com", "password": "a" * 8}
    ).status_code == 201
    assert client.post(
        "/auth/register", json={"email": "min3@example.com", "password": "é" * 8}
    ).status_code == 201


def test_the_message_never_echoes_the_submitted_password(client, db_session):
    secret = "Sup3r-secret-" + "x" * 80  # 93 octets
    user_id = _seed_account(db_session, "echo@example.com")
    plain = _seed_reset_token(db_session, user_id)

    for response in (
        client.post("/auth/register", json={"email": "echo2@example.com", "password": secret}),
        client.post("/auth/reset-password", json={"token": plain, "new_password": secret}),
    ):
        assert response.status_code == 422
        assert "Sup3r-secret" not in response.text
        assert all("input" not in error for error in response.json()["errors"])


# ---------------------------------------------------------------------------
# Un mot de passe refusé ne consomme JAMAIS le lien de réinitialisation
# ---------------------------------------------------------------------------


def test_a_refused_password_does_not_consume_the_reset_link(client, db_session):
    """La validation du corps précède la consommation du jeton : un mot de passe trop
    long (422) laisse le lien intact. L'utilisateur corrige et le MÊME lien aboutit ;
    après ce succès seulement, il est consommé (usage unique inchangé)."""
    user_id = _seed_account(db_session, "retry@example.com")
    plain = _seed_reset_token(db_session, user_id)
    old_hash = db_session.get(User, user_id).hashed_password

    for too_long in ("a" * 73, "é" * 37):
        refused = client.post(
            "/auth/reset-password", json={"token": plain, "new_password": too_long}
        )
        assert refused.status_code == 422
        assert _consumed_at(db_session, plain) is None  # lien intact
        assert db_session.get(User, user_id).hashed_password == old_hash  # rien écrit

    accepted = client.post(
        "/auth/reset-password", json={"token": plain, "new_password": "nouveau-mot-de-passe"}
    )
    assert accepted.status_code == 200, accepted.text
    assert _consumed_at(db_session, plain) is not None
    login = client.post(
        "/auth/login", json={"email": "retry@example.com", "password": "nouveau-mot-de-passe"}
    )
    assert login.status_code == 200

    replay = client.post(
        "/auth/reset-password", json={"token": plain, "new_password": "encore-un-autre-mdp"}
    )
    assert replay.status_code == 400  # usage unique toujours garanti


# ---------------------------------------------------------------------------
# Comptes EXISTANTS : un mot de passe de plus de 72 octets continue de fonctionner
# ---------------------------------------------------------------------------

LEGACY_PASSWORDS = [
    pytest.param("a" * 99 + "Z", id="100 ascii"),
    pytest.param("a" * 127 + "Z", id="128 ascii (ancienne limite)"),
    pytest.param("é" * 60, id="60 é = 120 octets"),
]


def _login(client, email: str, password: str):
    return client.post("/auth/login", json={"email": email, "password": password})


@pytest.mark.parametrize("legacy", LEGACY_PASSWORDS)
def test_login_still_works_for_an_existing_password_over_72_bytes(client, db_session, legacy):
    """Le compte est semé directement en base, comme avant la limite (le hash de la
    chaîne complète). La connexion garde sa borne de 4096 octets : le mot de passe
    complet ouvre le compte.

    Même résultat, par construction, qu'avant le changement : bcrypt ne lit que les
    72 premiers octets, donc une fin différente ouvre aussi le compte (c'est le
    défaut qui motive la limite, DOCUMENTÉ ici, pas voulu). Ce test dépend de
    bcrypt < 5 (qui LÈVE au-delà de 72 octets) : un relèvement du pin le fera
    échouer bruyamment, c'est voulu."""
    _seed_account(db_session, "legacy@example.com", password=legacy)

    assert _login(client, "legacy@example.com", legacy).status_code == 200
    assert _login(client, "legacy@example.com", legacy + "-autre-fin").status_code == 200

    # Une différence DANS les 72 premiers octets, elle, est toujours refusée.
    first = legacy[0]
    changed = ("b" if first != "b" else "c") + legacy[1:]
    assert _login(client, "legacy@example.com", changed).status_code == 401


def test_account_deletion_still_accepts_an_existing_password_over_72_bytes(client, db_session):
    legacy = "a" * 99 + "Z"
    _seed_account(db_session, "legacy-del@example.com", password=legacy)
    token = _login(client, "legacy-del@example.com", legacy).json()["access_token"]

    response = client.request(
        "DELETE",
        "/auth/me",
        json={"password": legacy},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 204, response.text
