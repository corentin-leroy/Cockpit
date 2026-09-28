"""Validation des entrées : bornes, caractères interdits, entiers, null explicite.

Objectif : qu'aucune entrée d'un client ne produise un 500. Ces tests portent sur
le contrat de validation (Pydantic / FastAPI), qui s'exécute AVANT la base : ils
donnent le même résultat sur SQLite (tests) et sur PostgreSQL (production), ce que
ne fait pas une contrainte de colonne — SQLite n'applique pas les longueurs de
VARCHAR et accepte les NUL.

Le client de test lève les exceptions non gérées au lieu de renvoyer un 500 : un
défaut de validation fait donc échouer le test bruyamment.
"""

import json
from dataclasses import dataclass
from typing import Any, get_args

import pytest
from fastapi.routing import APIRoute

from app import schemas
from app.limits import (
    MAX_BOARD_NAME_LENGTH,
    MAX_COMPANY_LENGTH,
    MAX_ID,
    MAX_LOCATION_LENGTH,
    MAX_NOTES_LENGTH,
    MAX_PASSWORD_INPUT_BYTES,
    MAX_PASSWORD_LENGTH,
    MAX_TITLE_LENGTH,
    MAX_URL_LENGTH,
)
from app.main import app
from app.models import Application, Board

# Message du 401 générique du login (cf. routers/auth.py) : le corps d'un mot de
# passe incorrect mais bien formé doit rester IDENTIQUE quelle que soit la longueur.
LOGIN_FAILURE_DETAIL = "Email ou mot de passe incorrect."


# ---------------------------------------------------------------------------
# Login et suppression de compte : mot de passe borné en OCTETS UTF-8
# ---------------------------------------------------------------------------

# (libellé, mot de passe, statut attendu). 4096 octets = la limite de passlib :
# au-delà il lève PasswordSizeError (500). « é » = 2 octets, l'émoji = 4 octets.
PASSWORD_INPUT_CASES = [
    ("4096 octets ASCII (limite)", "a" * MAX_PASSWORD_INPUT_BYTES, "well_formed"),
    ("4097 octets ASCII", "a" * (MAX_PASSWORD_INPUT_BYTES + 1), "too_long"),
    ("2048 x 'é' = 4096 octets (limite)", "é" * 2048, "well_formed"),
    ("2049 x 'é' = 4098 octets", "é" * 2049, "too_long"),
    ("1024 x émoji = 4096 octets (limite)", "\U0001F600" * 1024, "well_formed"),
    ("1025 x émoji = 4100 octets", "\U0001F600" * 1025, "too_long"),
]


@pytest.mark.parametrize(
    "label,password,expectation", PASSWORD_INPUT_CASES, ids=[c[0] for c in PASSWORD_INPUT_CASES]
)
@pytest.mark.parametrize("known_email", [True, False], ids=["email connu", "email inconnu"])
def test_login_password_is_bounded_in_bytes(
    client, make_user, label, password, expectation, known_email
):
    """Un mot de passe bien formé mais faux donne le 401 générique, jusqu'à 4096
    octets. Au-delà : 422 (entrée hors contrat), jamais un 500.

    Testé avec un email connu ET inconnu : la réponse ne doit pas révéler si le
    compte existe (la validation précède la recherche du compte, donc le statut
    est identique dans les deux cas)."""
    user = make_user()
    email = user.email if known_email else "personne@example.com"

    response = client.post("/auth/login", json={"email": email, "password": password})

    if expectation == "well_formed":
        assert response.status_code == 401
        assert response.json()["detail"] == LOGIN_FAILURE_DETAIL
    else:
        assert response.status_code == 422


@pytest.mark.parametrize(
    "label,password,expectation", PASSWORD_INPUT_CASES, ids=[c[0] for c in PASSWORD_INPUT_CASES]
)
def test_account_deletion_password_is_bounded_in_bytes(
    client, make_user, label, password, expectation
):
    """Même borne pour la suppression de compte : un mot de passe faux mais bien
    formé donne 403 (et le compte survit), au-delà de 4096 octets 422."""
    user = make_user()

    response = client.request(
        "DELETE", "/auth/me", json={"password": password}, headers=user.headers
    )

    if expectation == "well_formed":
        assert response.status_code == 403
    else:
        assert response.status_code == 422
    # Dans tous les cas le compte existe toujours.
    assert client.get("/auth/me", headers=user.headers).status_code == 200


# ---------------------------------------------------------------------------
# Contexte partagé : un utilisateur, son tableau par défaut, une candidature
# ---------------------------------------------------------------------------


@dataclass
class Ctx:
    client: Any
    user: Any
    board_id: int
    application_id: int


@pytest.fixture
def ctx(client, make_user, make_application) -> Ctx:
    user = make_user()
    application = make_application(user)
    return Ctx(client, user, user.default_board_id, application["id"])


def _application_payload(ctx: Ctx, **overrides) -> dict:
    return {"board_id": ctx.board_id, "title": "T", "company": "C", **overrides}


# ---------------------------------------------------------------------------
# Bornes de longueur : la valeur maximale passe, la valeur maximale + 1 donne 422
# ---------------------------------------------------------------------------

BOUNDED_APPLICATION_FIELDS = [
    ("title", MAX_TITLE_LENGTH),
    ("company", MAX_COMPANY_LENGTH),
    ("location", MAX_LOCATION_LENGTH),
    ("url", MAX_URL_LENGTH),
    ("notes", MAX_NOTES_LENGTH),
]


@pytest.mark.parametrize("field,limit", BOUNDED_APPLICATION_FIELDS)
def test_application_field_bound_on_create(ctx, field, limit):
    ok = ctx.client.post(
        "/applications",
        json=_application_payload(ctx, **{field: "a" * limit}),
        headers=ctx.user.headers,
    )
    assert ok.status_code == 201
    assert len(ok.json()[field]) == limit

    too_long = ctx.client.post(
        "/applications",
        json=_application_payload(ctx, **{field: "a" * (limit + 1)}),
        headers=ctx.user.headers,
    )
    assert too_long.status_code == 422
    assert too_long.json()["detail"][0]["loc"][-1] == field


@pytest.mark.parametrize("field,limit", BOUNDED_APPLICATION_FIELDS)
def test_application_field_bound_on_update(ctx, field, limit):
    """Même borne à la MODIFICATION qu'à la création : location et url n'étaient
    pas bornées en PATCH (500 en PostgreSQL au-delà de la colonne)."""
    url = f"/applications/{ctx.application_id}"

    ok = ctx.client.patch(url, json={field: "a" * limit}, headers=ctx.user.headers)
    assert ok.status_code == 200
    assert len(ok.json()[field]) == limit

    too_long = ctx.client.patch(
        url, json={field: "a" * (limit + 1)}, headers=ctx.user.headers
    )
    assert too_long.status_code == 422
    assert too_long.json()["detail"][0]["loc"][-1] == field
    # La valeur refusée n'a rien changé.
    assert len(ctx.client.get(url, headers=ctx.user.headers).json()[field]) == limit


@pytest.mark.parametrize("source", ["manual", "extension"])
def test_application_source_accepts_the_two_known_values(ctx, source):
    response = ctx.client.post(
        "/applications",
        json=_application_payload(ctx, source=source),
        headers=ctx.user.headers,
    )
    assert response.status_code == 201
    assert response.json()["source"] == source


def test_application_source_defaults_to_manual(ctx):
    response = ctx.client.post(
        "/applications", json=_application_payload(ctx), headers=ctx.user.headers
    )
    assert response.status_code == 201
    assert response.json()["source"] == "manual"


@pytest.mark.parametrize(
    "source",
    ["", "Manual", "other", "france_travail", "la_bonne_alternance", "x" * 51, "x" * 5000],
    ids=["vide", "casse", "inconnue", "source d'API future 1", "source d'API future 2", "51 car.", "5000 car."],
)
def test_application_source_is_a_closed_list(ctx, source):
    """`source` est une liste fermée (manual, extension) : les sources d'API
    (V1.5) seront ajoutées le jour où elles existeront."""
    response = ctx.client.post(
        "/applications",
        json=_application_payload(ctx, source=source),
        headers=ctx.user.headers,
    )
    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"][-1] == "source"


def test_board_name_bound(ctx):
    limit = MAX_BOARD_NAME_LENGTH
    assert ctx.client.post(
        "/boards", json={"name": "a" * limit}, headers=ctx.user.headers
    ).status_code == 201
    assert ctx.client.post(
        "/boards", json={"name": "a" * (limit + 1)}, headers=ctx.user.headers
    ).status_code == 422

    url = f"/boards/{ctx.board_id}"
    assert ctx.client.patch(
        url, json={"name": "a" * limit}, headers=ctx.user.headers
    ).status_code == 200
    assert ctx.client.patch(
        url, json={"name": "a" * (limit + 1)}, headers=ctx.user.headers
    ).status_code == 422


def test_chosen_password_bound(client):
    """Mot de passe CHOISI : 128 caractères au plus (inscription et réinitialisation).

    Réinitialisation : la validation précède la vérification du jeton, donc 128
    caractères atteignent le contrôle du jeton (400, jeton inconnu) et 129 sont
    refusés avant (422)."""
    ok = client.post(
        "/auth/register",
        json={"email": "long@example.com", "password": "x" * MAX_PASSWORD_LENGTH},
    )
    assert ok.status_code == 201
    too_long = client.post(
        "/auth/register",
        json={"email": "long2@example.com", "password": "x" * (MAX_PASSWORD_LENGTH + 1)},
    )
    assert too_long.status_code == 422

    at_limit = client.post(
        "/auth/reset-password",
        json={"token": "inconnu", "new_password": "x" * MAX_PASSWORD_LENGTH},
    )
    assert at_limit.status_code == 400
    over = client.post(
        "/auth/reset-password",
        json={"token": "inconnu", "new_password": "x" * (MAX_PASSWORD_LENGTH + 1)},
    )
    assert over.status_code == 422


# ---------------------------------------------------------------------------
# Caractères qu'on ne peut pas enregistrer : NUL et surrogates isolés
# ---------------------------------------------------------------------------

BAD_CHARACTERS = [("NUL", "a\x00b"), ("surrogate isolé", "a\ud800b")]

# (nom, méthode, chemin, corps, authentifié, champs texte). Une ligne par schéma
# d'ENTRÉE : chaque champ texte de chacun est testé avec chaque caractère interdit.
TEXT_INPUTS = [
    ("register", "POST", "/auth/register", lambda c: {"email": "new@example.com", "password": "password123"}, False, ["email", "password"]),
    ("login", "POST", "/auth/login", lambda c: {"email": c.user.email, "password": "password123"}, False, ["email", "password"]),
    ("forgot-password", "POST", "/auth/forgot-password", lambda c: {"email": c.user.email}, False, ["email"]),
    ("reset-password", "POST", "/auth/reset-password", lambda c: {"token": "tok", "new_password": "password123"}, False, ["token", "new_password"]),
    ("verify-email", "POST", "/auth/verify-email", lambda c: {"token": "tok"}, False, ["token"]),
    ("delete-account", "DELETE", "/auth/me", lambda c: {"password": "password123"}, True, ["password"]),
    ("board-create", "POST", "/boards", lambda c: {"name": "N"}, True, ["name"]),
    ("board-rename", "PATCH", "/boards/{board_id}", lambda c: {"name": "N"}, True, ["name"]),
    ("application-create", "POST", "/applications", lambda c: _application_payload(c), True, ["title", "company", "location", "url", "notes"]),
    ("application-update", "PATCH", "/applications/{application_id}", lambda c: {"title": "T"}, True, ["title", "company", "location", "url", "notes"]),
]

TEXT_INPUT_CASES = [
    pytest.param(name, method, path, build, auth, field, bad, id=f"{name}.{field}-{label}")
    for name, method, path, build, auth, fields in TEXT_INPUTS
    for field in fields
    for label, bad in BAD_CHARACTERS
]


@pytest.mark.parametrize("name,method,path,build,auth,field,bad", TEXT_INPUT_CASES)
def test_unstorable_characters_are_rejected(ctx, name, method, path, build, auth, field, bad):
    """NUL et surrogate isolé donnent 422, jamais un 500 : PostgreSQL refuse le NUL,
    bcrypt aussi, et un surrogate isolé n'a pas d'encodage UTF-8.

    Corps envoyé en JSON BRUT (json.dumps échappe le caractère en \\u0000 /
    \\ud800) : le client HTTP de test ne pourrait pas encoder lui-même un
    surrogate isolé."""
    body = build(ctx)
    body[field] = bad
    headers = {"Content-Type": "application/json", **(ctx.user.headers if auth else {})}

    response = ctx.client.request(
        method,
        path.format(board_id=ctx.board_id, application_id=ctx.application_id),
        content=json.dumps(body),
        headers=headers,
    )

    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"][-1] == field


def test_valid_unicode_is_still_accepted(ctx):
    """Témoin : accents et paire de surrogates VALIDE (émoji) restent acceptés."""
    response = ctx.client.post(
        "/applications",
        json=_application_payload(ctx, title="Développeur \U0001F600 été"),
        headers=ctx.user.headers,
    )
    assert response.status_code == 201
    assert response.json()["title"] == "Développeur \U0001F600 été"


# ---------------------------------------------------------------------------
# Garde contre l'oubli : tout schéma d'entrée hérite de InputModel
# ---------------------------------------------------------------------------

# Schémas de SORTIE : ils décrivent ce que le serveur envoie, pas ce qu'il reçoit.
OUTPUT_SCHEMAS = {"UserRead", "BoardRead", "ApplicationRead", "Token", "MessageResponse"}


def _body_models():
    """Classe du corps de chaque route qui en attend un."""
    found = []
    for route in app.routes:
        if isinstance(route, APIRoute):
            for param in route.dependant.body_params:
                found.append((route.path, param.field_info.annotation))
    return found


def test_every_schema_is_declared_input_or_output():
    """Un schéma ajouté à schemas.py doit être un schéma d'entrée (hérite de
    InputModel, donc du refus des caractères interdits) ou figurer explicitement
    dans OUTPUT_SCHEMAS. Un oubli fait échouer ce test."""
    defined = {
        name: obj
        for name, obj in vars(schemas).items()
        if isinstance(obj, type)
        and issubclass(obj, schemas.BaseModel)
        and obj.__module__ == schemas.__name__
        and obj is not schemas.InputModel
    }
    for name, cls in defined.items():
        if name in OUTPUT_SCHEMAS:
            assert not issubclass(cls, schemas.InputModel), f"{name} est une sortie"
        else:
            assert issubclass(cls, schemas.InputModel), (
                f"{name} n'hérite pas de InputModel : ajoutez-le, ou déclarez-le "
                "dans OUTPUT_SCHEMAS s'il décrit une réponse."
            )
    # Le test ne doit pas devenir vide sans que personne ne s'en aperçoive.
    assert len(defined) - len(OUTPUT_SCHEMAS & defined.keys()) >= 10


def test_every_request_body_of_every_route_is_an_input_model():
    """Même garde, côté ROUTES : chaque corps de requête réellement attendu par
    l'API doit être un InputModel, y compris pour un schéma défini hors de
    schemas.py ou un `dict` brut."""
    body_models = _body_models()
    assert len(body_models) >= 10, "introspection des routes vide : test à revoir"
    for path, model in body_models:
        assert isinstance(model, type) and issubclass(model, schemas.InputModel), (
            f"{path} : corps de requête {model!r} qui n'est pas un InputModel"
        )


def test_every_integer_path_or_query_parameter_is_bounded():
    """Tout identifiant reçu dans l'URL doit porter ge=1 et le=MAX_ID (IdPath /
    IdQuery). Un paramètre `int` nu accepterait 99999999999999999999 et la base
    lèverait « integer out of range » (500)."""
    checked = 0
    for route in app.routes:
        if not isinstance(route, APIRoute):
            continue
        for param in route.dependant.path_params + route.dependant.query_params:
            annotation = param.field_info.annotation
            if annotation is int or int in get_args(annotation):
                bounds = {}
                for meta in param.field_info.metadata:
                    for key in ("ge", "le"):
                        if hasattr(meta, key):
                            bounds[key] = getattr(meta, key)
                assert bounds == {"ge": 1, "le": MAX_ID}, (
                    f"{route.path} : paramètre entier `{param.name}` non borné ({bounds})"
                )
                checked += 1
    assert checked >= 6, "aucun paramètre entier trouvé : introspection à revoir"


# ---------------------------------------------------------------------------
# null explicite en PATCH
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("field", ["title", "company", "status", "board_id"])
def test_explicit_null_is_rejected_on_required_fields(ctx, field):
    """Ces champs sont NOT NULL en base : un null explicite donnait un 500
    (violation de contrainte). Pour ne pas modifier un champ, on l'OMET."""
    url = f"/applications/{ctx.application_id}"
    before = ctx.client.get(url, headers=ctx.user.headers).json()

    response = ctx.client.patch(url, json={field: None}, headers=ctx.user.headers)

    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"][-1] == field
    assert ctx.client.get(url, headers=ctx.user.headers).json() == before


@pytest.mark.parametrize("field", ["location", "url", "notes", "applied_at"])
def test_explicit_null_still_clears_optional_fields(ctx, field):
    """Sur les champs facultatifs, null reste le moyen de VIDER la valeur."""
    url = f"/applications/{ctx.application_id}"
    filled = {
        "location": "Lyon",
        "url": "https://example.com/offre",
        "notes": "à relancer",
        "applied_at": "2026-01-15T10:00:00",
    }
    assert ctx.client.patch(url, json=filled, headers=ctx.user.headers).status_code == 200

    response = ctx.client.patch(url, json={field: None}, headers=ctx.user.headers)

    assert response.status_code == 200
    assert response.json()[field] is None


# ---------------------------------------------------------------------------
# applied_at : plage 1900-2100, fuseau normalisé en UTC naïf
# ---------------------------------------------------------------------------
# Une date hors de la plage Python (années 1 à 9999) est acceptée puis COMMITÉE par
# PostgreSQL (son type va de 4713 av. J.-C. à l'an 294276), mais sa relecture
# échoue : la ligne devient illisible, la liste des candidatures du compte donne 500
# et même la suppression échoue. Ces tests vérifient donc chaque fois que la LISTE
# reste lisible : c'est le test de non-empoisonnement.

# (valeur envoyée, valeur relue). Un fuseau est converti en UTC puis retiré (colonnes
# DateTime naïves en UTC, cf. convention datetime du projet).
APPLIED_AT_ACCEPTED = [
    ("1900-01-01T00:00:00", "1900-01-01T00:00:00"),
    ("2100-12-31T23:59:59", "2100-12-31T23:59:59"),
    ("2026-01-15T10:00:00", "2026-01-15T10:00:00"),
    ("2026-01-15", "2026-01-15T00:00:00"),
    ("2026-01-15T10:00:00Z", "2026-01-15T10:00:00"),
    ("2026-01-15T10:00:00+02:00", "2026-01-15T08:00:00"),
    ("2026-01-15T23:30:00-05:00", "2026-01-16T04:30:00"),
    ("1900-01-01T02:00:00+02:00", "1900-01-01T00:00:00"),  # pile sur la borne, après conversion
]

# Toutes doivent donner 422. Les deux dernières sont jugées APRÈS conversion en UTC
# ; les deux précédentes débordent à la conversion elle-même (OverflowError).
APPLIED_AT_REFUSED = [
    "1899-12-31T23:59:59",
    "2101-01-01T00:00:00",
    "0001-01-01T00:00:00",
    "9999-12-31T23:59:59",
    "0001-01-01T00:00:00+02:00",
    "9999-12-31T23:59:59-12:00",
    "1900-01-01T00:00:00+02:00",
    "2100-12-31T23:59:59-02:00",
]


@pytest.mark.parametrize("sent,stored", APPLIED_AT_ACCEPTED, ids=[a[0] for a in APPLIED_AT_ACCEPTED])
def test_applied_at_accepted_values_are_normalized_and_stay_readable(ctx, sent, stored):
    url = f"/applications/{ctx.application_id}"

    response = ctx.client.patch(url, json={"applied_at": sent}, headers=ctx.user.headers)

    assert response.status_code == 200
    assert response.json()["applied_at"] == stored
    # Non-empoisonnement : la ligne se relit, seule et dans la liste du compte.
    assert ctx.client.get(url, headers=ctx.user.headers).json()["applied_at"] == stored
    listing = ctx.client.get("/applications", headers=ctx.user.headers)
    assert listing.status_code == 200
    assert [a["applied_at"] for a in listing.json() if a["id"] == ctx.application_id] == [stored]


@pytest.mark.parametrize("sent", APPLIED_AT_REFUSED)
def test_applied_at_out_of_range_is_rejected_and_nothing_is_written(ctx, sent):
    url = f"/applications/{ctx.application_id}"
    ctx.client.patch(url, json={"applied_at": "2026-01-15T10:00:00"}, headers=ctx.user.headers)

    response = ctx.client.patch(url, json={"applied_at": sent}, headers=ctx.user.headers)

    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"][-1] == "applied_at"
    # Rien n'a été écrit, et le compte reste pleinement utilisable.
    assert ctx.client.get(url, headers=ctx.user.headers).json()["applied_at"] == "2026-01-15T10:00:00"
    assert ctx.client.get("/applications", headers=ctx.user.headers).status_code == 200


# ---------------------------------------------------------------------------
# Identifiants : entiers >= 1 tenant dans le type `integer` de PostgreSQL
# ---------------------------------------------------------------------------

MALFORMED_IDS = [MAX_ID + 1, 99999999999999999999, 0, -1]

# (libellé, méthode, chemin avec {id}, corps, statut attendu pour MAX_ID : valide
# mais inexistant).
URL_ID_ENTRIES = [
    ("GET /applications/{id}", "GET", "/applications/{id}", None, 404),
    ("PATCH /applications/{id}", "PATCH", "/applications/{id}", {}, 404),
    ("DELETE /applications/{id}", "DELETE", "/applications/{id}", None, 404),
    ("PATCH /boards/{id}", "PATCH", "/boards/{id}", {"name": "N"}, 404),
    ("DELETE /boards/{id}", "DELETE", "/boards/{id}", None, 404),
    ("GET /applications?board_id={id}", "GET", "/applications?board_id={id}", None, 200),
]


@pytest.mark.parametrize("label,method,path,body,valid_status", URL_ID_ENTRIES, ids=[e[0] for e in URL_ID_ENTRIES])
def test_ids_in_url_are_bounded(ctx, label, method, path, body, valid_status):
    for bad in MALFORMED_IDS:
        response = ctx.client.request(
            method, path.format(id=bad), json=body, headers=ctx.user.headers
        )
        assert response.status_code == 422, f"{label} avec {bad}"

    # La plus grande valeur admise est bien formée : elle atteint la recherche
    # (404 si la ressource n'existe pas), pas la validation.
    response = ctx.client.request(
        method, path.format(id=MAX_ID), json=body, headers=ctx.user.headers
    )
    assert response.status_code == valid_status


def test_board_id_in_body_is_bounded(ctx):
    """board_id du CORPS (création et déplacement) : mêmes bornes que dans l'URL."""
    patch_url = f"/applications/{ctx.application_id}"
    for bad in MALFORMED_IDS:
        created = ctx.client.post(
            "/applications",
            json=_application_payload(ctx, board_id=bad),
            headers=ctx.user.headers,
        )
        moved = ctx.client.patch(patch_url, json={"board_id": bad}, headers=ctx.user.headers)
        assert created.status_code == 422, f"POST board_id={bad}"
        assert moved.status_code == 422, f"PATCH board_id={bad}"

    created = ctx.client.post(
        "/applications",
        json=_application_payload(ctx, board_id=MAX_ID),
        headers=ctx.user.headers,
    )
    moved = ctx.client.patch(patch_url, json={"board_id": MAX_ID}, headers=ctx.user.headers)
    assert created.status_code == 404
    assert moved.status_code == 404


# ---------------------------------------------------------------------------
# Cohérence des bornes avec les colonnes de la base
# ---------------------------------------------------------------------------


def _column_length(model, column: str):
    return model.__table__.c[column].type.length


COLUMN_BOUNDS = [
    (Application, "title", MAX_TITLE_LENGTH),
    (Application, "company", MAX_COMPANY_LENGTH),
    (Application, "location", MAX_LOCATION_LENGTH),
    (Application, "url", MAX_URL_LENGTH),
    (Application, "notes", MAX_NOTES_LENGTH),
    (Application, "source", max(len(v) for v in get_args(schemas.ApplicationSource))),
    (Board, "name", MAX_BOARD_NAME_LENGTH),
]


@pytest.mark.parametrize(
    "model,column,bound", COLUMN_BOUNDS, ids=[f"{m.__tablename__}.{c}" for m, c, _ in COLUMN_BOUNDS]
)
def test_validation_bound_never_exceeds_the_column(model, column, bound):
    """Une borne de validation plus large que la colonne laisse passer la valeur,
    puis PostgreSQL la refuse à l'écriture (500 au lieu de 422). SQLite n'applique
    pas les longueurs de VARCHAR : ce test est le seul à détecter l'écart en test.

    `notes` est une colonne Text (longueur None, donc sans limite en base) jusqu'à
    la migration prévue vers String(5000) : le test ne compare alors rien et
    s'activera tout seul le jour où la colonne aura une longueur."""
    length = _column_length(model, column)
    if length is None:
        pytest.skip(f"{model.__tablename__}.{column} : colonne sans longueur (Text)")
    assert bound <= length


# ---------------------------------------------------------------------------
# Corps des réponses 422 : la valeur soumise n'est jamais renvoyée
# ---------------------------------------------------------------------------


def test_validation_errors_do_not_echo_the_submitted_value(ctx):
    """Le gestionnaire par défaut de FastAPI recopie la valeur fautive (`input`) :
    un mot de passe refusé serait renvoyé en clair dans la réponse."""
    secret = "Sup3r-secret-" + "x" * MAX_PASSWORD_INPUT_BYTES

    response = ctx.client.post(
        "/auth/login", json={"email": ctx.user.email, "password": secret}
    )

    assert response.status_code == 422
    assert "Sup3r-secret" not in response.text
    assert all("input" not in error for error in response.json()["detail"])


def test_validation_errors_keep_type_location_and_constraint(ctx):
    """On retire la valeur soumise mais on garde de quoi expliquer l'erreur : c'est
    ce que le frontend utilisera pour afficher un message lisible."""
    response = ctx.client.post(
        "/applications",
        json=_application_payload(ctx, title="a" * (MAX_TITLE_LENGTH + 1)),
        headers=ctx.user.headers,
    )

    assert response.status_code == 422
    error = response.json()["detail"][0]
    assert error["type"] == "string_too_long"
    assert error["loc"] == ["body", "title"]
    assert error["ctx"]["max_length"] == MAX_TITLE_LENGTH
    assert "msg" in error
