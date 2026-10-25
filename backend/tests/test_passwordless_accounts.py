"""Comptes SANS mot de passe (`users.hashed_password` NULL : connexion avec Google).

Aucun endpoint de ce lot n'en crée : les comptes sont inscrits normalement, puis leur
empreinte est effacée DIRECTEMENT en base (c'est l'état stocké qui décide). Chaque
chemin qui lisait le mot de passe doit se comporter ainsi :

- connexion : échec EXACTEMENT comme un mot de passe faux (même 401, même coût bcrypt
  grâce au hash leurre, même compteur d'échecs) : rien ne révèle la nature du compte ;
- mot de passe oublié : même réponse à l'écran ; un email (sans lien de
  réinitialisation ni jeton) dit de se connecter avec Google, plafonné en silence à
  3 par heure et par compte ;
- réinitialisation : le même 400 « lien invalide » qu'un jeton inconnu, avant bcrypt ;
- suppression du compte : 409 explicite (provisoire, jusqu'à la reconfirmation par
  Google), jamais un 500 ;
- UserRead expose `has_password`, jamais `google_sub` ni `token_version`.
"""

from datetime import timedelta

import pytest
from sqlalchemy import func, select, update

from app import email
from app.models import Application, Board, SecurityToken, TokenPurpose, User
from app.routers import auth
from app.security import (
    DUMMY_PASSWORD_HASH,
    generate_url_token,
    hash_token,
    utcnow,
)

LOGIN_401 = {"detail": "Email ou mot de passe incorrect."}
FORGOT_OK = {"message": "Si un compte existe avec cette adresse, un email vient d'être envoyé."}
INVALID_LINK = {"detail": "Ce lien est invalide ou expiré. Demandez-en un nouveau."}
PASSWORDLESS_DELETE = {
    "detail": (
        "Ce compte n'a pas de mot de passe : sa suppression ne peut pas être "
        "confirmée de cette façon."
    )
}
# Texte en clair du hash leurre (app/security.py). Un compte sans mot de passe vérifié
# contre le leurre ne doit JAMAIS s'ouvrir avec ce texte.
DECOY_PLAINTEXT = "timing-attack-mitigation-placeholder"


def _passwordless(make_user, db_session):
    """Inscrit un compte, puis efface son empreinte en base. Renvoie l'AuthedUser (son
    jeton de session reste valable : la session n'est pas liée au mot de passe)."""
    user = make_user()
    db_session.execute(update(User).where(User.email == user.email).values(hashed_password=None))
    db_session.commit()
    return user


def _stored(db_session, email_address: str) -> User:
    db_session.expire_all()
    return db_session.scalar(select(User).where(User.email == email_address))


def _login(client, email_address, password="un-mot-de-passe"):
    return client.post("/auth/login", json={"email": email_address, "password": password})


def _forgot(client, email_address):
    return client.post("/auth/forgot-password", json={"email": email_address})


def _comparable(response) -> tuple:
    """Ce que voit le client : code, corps, et en-têtes hors date."""
    headers = tuple(sorted((k, v) for k, v in response.headers.items() if k != "date"))
    return response.status_code, response.text, headers


@pytest.fixture
def sent_emails(monkeypatch):
    """Espionne les deux emails de /auth/forgot-password (rien n'est envoyé)."""
    sent = {"reset": [], "google": []}
    monkeypatch.setattr(
        auth, "send_password_reset_email", lambda to, token: sent["reset"].append((to, token))
    )
    monkeypatch.setattr(
        auth, "send_google_sign_in_notice_email", lambda to: sent["google"].append(to)
    )
    return sent


# ---------------------------------------------------------------------------
# Connexion
# ---------------------------------------------------------------------------


def test_login_on_a_passwordless_account_fails_exactly_like_a_wrong_password(
    client, make_user, db_session
):
    google = _passwordless(make_user, db_session)
    normal = make_user()

    responses = [
        _login(client, google.email),
        _login(client, google.email, google.password),  # l'ancien mot de passe non plus
        _login(client, google.email, DECOY_PLAINTEXT),  # ni le texte du leurre
        _login(client, normal.email, "mauvais-mot-de-passe"),
        _login(client, "inconnu@example.com"),
    ]

    assert {_comparable(r) for r in responses} == {_comparable(responses[-1])}
    assert responses[0].status_code == 401
    assert responses[0].json() == LOGIN_401


def test_login_on_a_passwordless_account_pays_bcrypt_against_the_decoy(
    client, make_user, db_session, monkeypatch
):
    """Même coût qu'un compte inconnu : exactement UN verify_password, contre le hash
    leurre (sinon le temps de réponse trahirait la nature du compte)."""
    google = _passwordless(make_user, db_session)
    real_verify = auth.verify_password
    hashes_checked = []

    def spy(plain, hashed):
        hashes_checked.append(hashed)
        return real_verify(plain, hashed)

    monkeypatch.setattr(auth, "verify_password", spy)

    _login(client, google.email)

    assert hashes_checked == [DUMMY_PASSWORD_HASH]


def test_failures_on_a_passwordless_account_lead_to_the_same_429(
    client, clock, make_user, db_session
):
    """Les échecs comptent pour le couple (IP, email) comme ailleurs : au 6e essai, le
    même 429 (corps et Retry-After) que pour une adresse inconnue."""
    google = _passwordless(make_user, db_session)

    for _ in range(5):
        assert _login(client, google.email).status_code == 401
        assert _login(client, "inconnu@example.com").status_code == 401
    blocked = _login(client, google.email)
    unknown = _login(client, "inconnu@example.com")

    assert blocked.status_code == 429
    assert _comparable(blocked) == _comparable(unknown)


# ---------------------------------------------------------------------------
# Mot de passe oublié
# ---------------------------------------------------------------------------


def test_forgot_password_on_a_passwordless_account_sends_the_google_notice_only(
    client, make_user, db_session, sent_emails
):
    google = _passwordless(make_user, db_session)
    user_id = _stored(db_session, google.email).id

    response = _forgot(client, google.email)
    unknown = _forgot(client, "inconnu@example.com")

    assert response.status_code == 200
    assert response.json() == FORGOT_OK
    assert _comparable(response) == _comparable(unknown)
    assert sent_emails == {"reset": [], "google": [google.email]}
    reset_tokens = db_session.scalar(
        select(func.count()).select_from(SecurityToken).where(
            SecurityToken.user_id == user_id,
            SecurityToken.purpose == TokenPurpose.PASSWORD_RESET,
        )
    )
    assert reset_tokens == 0


def test_the_google_notice_is_capped_silently_at_3_per_hour(
    client, clock, make_user, db_session, sent_emails
):
    google = _passwordless(make_user, db_session)

    responses = [_forgot(client, google.email) for _ in range(4)]

    assert {_comparable(r) for r in responses} == {_comparable(responses[0])}
    assert responses[0].json() == FORGOT_OK
    assert sent_emails["google"] == [google.email] * 3

    clock.advance(3600)
    assert _forgot(client, google.email).json() == FORGOT_OK
    assert sent_emails["google"] == [google.email] * 4


def test_forgot_password_with_a_password_still_sends_a_reset_link(
    client, make_user, db_session, sent_emails
):
    """Garde contre une branche inversée : un compte AVEC mot de passe reçoit toujours
    le lien de réinitialisation, jamais l'email Google."""
    normal = make_user()

    _forgot(client, normal.email)

    assert sent_emails["google"] == []
    assert [to for to, _ in sent_emails["reset"]] == [normal.email]


def test_the_google_notice_points_to_the_login_page_without_any_token(monkeypatch):
    """Ni lien de réinitialisation ni jeton : un bouton « Se connecter » vers la page
    de connexion du site (FRONTEND_URL + /login)."""
    monkeypatch.setenv("FRONTEND_URL", "https://site.example/")
    captured = {}

    def fake_send(to_email, subject, html_content, dev_link):
        captured.update(to=to_email, subject=subject, html=html_content, link=dev_link)

    monkeypatch.setattr(email, "_send", fake_send)

    email.send_google_sign_in_notice_email("google@example.com")

    assert captured["to"] == "google@example.com"
    assert captured["link"] == "https://site.example/login"
    assert 'href="https://site.example/login"' in captured["html"]
    assert "Se connecter" in captured["html"]
    assert "Continuer avec Google" in captured["html"]
    assert "reset-password" not in captured["html"]
    assert "token" not in captured["html"]


# ---------------------------------------------------------------------------
# Réinitialisation du mot de passe
# ---------------------------------------------------------------------------


def test_a_pending_reset_link_cannot_give_a_password_back(
    client, make_user, db_session, monkeypatch
):
    """Un lien encore en attente (demandé AVANT que le compte ne perde son mot de passe
    par la liaison Google, au lot 2) ne rend jamais de mot de passe : le même 400 qu'un
    jeton inconnu, refusé AVANT bcrypt, et rien ne change."""
    google = _passwordless(make_user, db_session)
    user_id = _stored(db_session, google.email).id
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
    hashed = []
    monkeypatch.setattr(auth, "hash_password", lambda plain_password: hashed.append(1) or "x")
    body = {"token": plain, "new_password": "nouveau-mot-de-passe"}

    refused = client.post("/auth/reset-password", json=body)
    unknown = client.post(
        "/auth/reset-password", json={**body, "token": generate_url_token()}
    )

    assert refused.status_code == 400
    assert refused.json() == INVALID_LINK
    assert _comparable(refused) == _comparable(unknown)
    assert hashed == []
    stored = _stored(db_session, google.email)
    assert stored.hashed_password is None
    assert stored.token_version == 0
    assert _login(client, google.email, "nouveau-mot-de-passe").status_code == 401


# ---------------------------------------------------------------------------
# Suppression du compte
# ---------------------------------------------------------------------------


def test_deleting_a_passwordless_account_is_an_explicit_409(
    client, make_user, make_application, db_session
):
    google = _passwordless(make_user, db_session)
    make_application(google)

    response = client.request(
        "DELETE", "/auth/me", json={"password": "un-mot-de-passe"}, headers=google.headers
    )

    assert response.status_code == 409
    assert response.json() == PASSWORDLESS_DELETE
    stored = _stored(db_session, google.email)
    assert stored is not None
    boards = db_session.scalar(
        select(func.count()).select_from(Board).where(Board.user_id == stored.id)
    )
    applications = db_session.scalar(
        select(func.count()).select_from(Application).join(Board).where(Board.user_id == stored.id)
    )
    assert (boards, applications) == (1, 1)
    # La session reste valable : un 401 ferait purger le jeton côté front.
    assert client.get("/auth/me", headers=google.headers).status_code == 200


# ---------------------------------------------------------------------------
# Contrat de sortie (UserRead)
# ---------------------------------------------------------------------------


def test_user_read_exposes_has_password_and_nothing_else_new(client, make_user, db_session):
    register = client.post(
        "/auth/register", json={"email": "nouveau@example.com", "password": "password123"}
    )
    normal = make_user()
    google = _passwordless(make_user, db_session)
    db_session.execute(
        update(User).where(User.email == google.email).values(google_sub="1234567890")
    )
    db_session.commit()

    me_normal = client.get("/auth/me", headers=normal.headers).json()
    me_google = client.get("/auth/me", headers=google.headers).json()

    expected_keys = {"id", "email", "is_verified", "created_at", "has_password"}
    assert set(register.json()) == expected_keys
    assert set(me_normal) == expected_keys
    assert set(me_google) == expected_keys
    assert register.json()["has_password"] is True
    assert me_normal["has_password"] is True
    assert me_google["has_password"] is False
