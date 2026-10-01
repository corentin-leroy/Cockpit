"""Normalisation des adresses email : minuscules, sans espaces autour, à CHAQUE entrée.

Sans elle, « Case@Example.com » et « case@example.com » créaient deux comptes
(l'index unique de la colonne compare la casse), et un utilisateur inscrit en
minuscules qui tapait une majuscule à la connexion échouait. La normalisation vit
dans UN type partagé (schemas.NormalizedEmail) ; l'index unique existant suffit
ensuite à empêcher les doublons, sans contrainte supplémentaire en base.
"""

import json

import pytest
from pydantic import EmailStr, TypeAdapter
from pydantic.functional_validators import BeforeValidator
from sqlalchemy import func, select

from app import schemas
from app.models import SecurityToken, TokenPurpose, User

PASSWORD = "password123"
FORGOT_MESSAGE = "Si un compte existe avec cette adresse, un email vient d'être envoyé."


def _register(client, email: str, password: str = PASSWORD):
    return client.post("/auth/register", json={"email": email, "password": password})


def _login(client, email: str, password: str = PASSWORD):
    return client.post("/auth/login", json={"email": email, "password": password})


# ---------------------------------------------------------------------------
# Inscription : un seul compte par adresse, quelle que soit la casse
# ---------------------------------------------------------------------------


def test_second_registration_in_other_case_is_a_409(client, db_session):
    """Majuscule d'abord, minuscules ensuite : le MÊME 409 que pour un doublon exact,
    et un seul compte en base."""
    first = _register(client, "Case@Example.com")
    assert first.status_code == 201, first.text

    exact_duplicate = _register(client, "Case@Example.com")
    other_case = _register(client, "case@example.com")

    assert other_case.status_code == 409
    assert other_case.json() == exact_duplicate.json()
    assert db_session.scalar(select(func.count()).select_from(User)) == 1


def test_stored_email_is_lowercase_and_trimmed(client, db_session):
    response = _register(client, "  MiXed.Case@Example.COM \t")

    assert response.status_code == 201, response.text
    assert response.json()["email"] == "mixed.case@example.com"
    stored = db_session.scalars(select(User)).one()
    assert stored.email == "mixed.case@example.com"


# ---------------------------------------------------------------------------
# Connexion : la casse tapée n'a pas d'importance
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "typed",
    ["alice@example.com", "Alice@Example.com", "ALICE@EXAMPLE.COM", "  alice@example.com  "],
)
def test_login_works_whatever_the_case_typed(client, typed):
    assert _register(client, "alice@example.com").status_code == 201
    response = _login(client, typed)
    assert response.status_code == 200, response.text
    assert "access_token" in response.json()


def test_login_works_for_an_account_registered_with_capitals(client):
    assert _register(client, "Bob@Example.com").status_code == 201
    assert _login(client, "bob@example.com").status_code == 200
    assert _login(client, "BOB@example.com").status_code == 200


# ---------------------------------------------------------------------------
# Mot de passe oublié : atteint le bon compte quelle que soit la casse
# ---------------------------------------------------------------------------


def _reset_tokens_count(db_session, email: str) -> int:
    return db_session.scalar(
        select(func.count())
        .select_from(SecurityToken)
        .join(User, SecurityToken.user_id == User.id)
        .where(User.email == email, SecurityToken.purpose == TokenPurpose.PASSWORD_RESET)
    )


def test_forgot_password_in_other_case_reaches_the_right_account(client, db_session):
    assert _register(client, "carol@example.com").status_code == 201
    assert _reset_tokens_count(db_session, "carol@example.com") == 0

    response = client.post("/auth/forgot-password", json={"email": "CAROL@Example.com"})

    assert response.status_code == 200
    # Preuve que le compte a été trouvé : un jeton de reset a été émis pour lui.
    assert _reset_tokens_count(db_session, "carol@example.com") == 1


# ---------------------------------------------------------------------------
# Anti-énumération : rien ne change selon l'existence du compte ni la casse
# ---------------------------------------------------------------------------


def test_forgot_password_response_is_identical_whatever_exists_or_case(client):
    assert _register(client, "dave@example.com").status_code == 201

    responses = [
        client.post("/auth/forgot-password", json={"email": email})
        for email in (
            "dave@example.com",  # existe
            "DAVE@Example.com",  # existe, autre casse
            "inconnu@example.com",  # n'existe pas
            "INCONNU@Example.com",  # n'existe pas, autre casse
        )
    ]

    assert {r.status_code for r in responses} == {200}
    assert {r.text for r in responses} == {responses[0].text}
    assert responses[0].json()["message"] == FORGOT_MESSAGE


def test_login_401_is_identical_whatever_exists_or_case(client):
    assert _register(client, "erin@example.com").status_code == 201

    responses = [
        _login(client, "erin@example.com", "mauvais-mot-de-passe"),  # existe, mdp faux
        _login(client, "ERIN@Example.com", "mauvais-mot-de-passe"),  # idem, autre casse
        _login(client, "inconnu@example.com", "mauvais-mot-de-passe"),  # inconnu
        _login(client, "INCONNU@Example.com", "mauvais-mot-de-passe"),  # inconnu, autre casse
    ]

    assert {r.status_code for r in responses} == {401}
    assert {r.text for r in responses} == {responses[0].text}
    assert {r.headers.get("www-authenticate") for r in responses} == {"Bearer"}


# ---------------------------------------------------------------------------
# Limites de la normalisation
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "bad",
    [
        "inner space@example.com",  # espace À L'INTÉRIEUR : refusé par EmailStr
        "alice@exam ple.com",
        "   ",  # espaces seuls : vide après normalisation
        "",
        "pas-un-email",
    ],
)
def test_malformed_email_is_still_a_422_on_every_entry_point(client, bad):
    for path, body in (
        ("/auth/register", {"email": bad, "password": PASSWORD}),
        ("/auth/login", {"email": bad, "password": PASSWORD}),
        ("/auth/forgot-password", {"email": bad}),
    ):
        response = client.post(path, json=body)
        assert response.status_code == 422, f"{path} {bad!r} : {response.status_code}"
        assert response.json()["errors"][0]["field"] == "email"


@pytest.mark.parametrize("bad", ["a\x00b@example.com", "a\ud800b@example.com"])
def test_forbidden_characters_are_refused_before_normalisation(client, bad):
    """NUL et surrogate isolé : refusés (InputModel passe AVANT la normalisation),
    jamais nettoyés en silence."""
    # JSON brut (json.dumps échappe en \u0000 / \ud800) : le client de test ne
    # pourrait pas encoder lui-même un surrogate isolé.
    response = client.post(
        "/auth/forgot-password",
        content=json.dumps({"email": bad}),
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 422
    assert response.json()["errors"][0]["field"] == "email"


@pytest.mark.parametrize("value", [None, 5, ["a@b.com"]])
def test_non_string_email_keeps_its_usual_422(client, value):
    response = client.post("/auth/forgot-password", json={"email": value})
    assert response.status_code == 422


def test_normalisation_is_idempotent():
    adapter = TypeAdapter(schemas.NormalizedEmail)
    once = adapter.validate_python("  MiXed@Example.COM ")
    assert adapter.validate_python(once) == once == "mixed@example.com"


# ---------------------------------------------------------------------------
# Garde contre l'oubli : tout champ email d'un schéma d'ENTRÉE est normalisé
# ---------------------------------------------------------------------------


def _input_models() -> list[type]:
    return [
        obj
        for obj in vars(schemas).values()
        if isinstance(obj, type)
        and issubclass(obj, schemas.InputModel)
        and obj is not schemas.InputModel
    ]


def _unnormalized_email_fields(models) -> list[str]:
    """Champs « email » (typés EmailStr, ou dont le nom contient « email » même
    typés str) qui ne passent PAS par schemas.NormalizedEmail."""
    offenders = []
    for model in models:
        for name, field in model.model_fields.items():
            if field.annotation is not EmailStr and "email" not in name.lower():
                continue
            normalised = any(
                isinstance(meta, BeforeValidator) and meta.func is schemas._normalize_email
                for meta in field.metadata
            )
            if not normalised:
                offenders.append(f"{model.__name__}.{name}")
    return offenders


def test_every_input_email_field_goes_through_the_normalisation():
    assert _unnormalized_email_fields(_input_models()) == []


def test_the_guard_does_see_the_known_email_fields():
    """Le garde ne doit pas passer par vacuité : il connaît les trois champs réels."""
    seen = {
        f"{m.__name__}.{n}"
        for m in _input_models()
        for n, f in m.model_fields.items()
        if f.annotation is EmailStr
    }
    assert seen == {"UserCreate.email", "UserLogin.email", "ForgotPasswordRequest.email"}


def test_the_guard_catches_a_forgotten_normalisation():
    """Preuve que le garde détecte l'oubli : deux schémas fautifs factices (EmailStr
    nu, et un champ « email » typé str) sont signalés ; le champ normalisé non."""

    class Forgetful(schemas.InputModel):
        email: EmailStr

    class ForgetfulStr(schemas.InputModel):
        contact_email: str

    class Fine(schemas.InputModel):
        email: schemas.NormalizedEmail

    assert _unnormalized_email_fields([Forgetful, ForgetfulStr, Fine]) == [
        "Forgetful.email",
        "ForgetfulStr.contact_email",
    ]
