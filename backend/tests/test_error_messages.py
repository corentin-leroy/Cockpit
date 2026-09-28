"""Format des réponses d'erreur : lisibles en français, jamais de fragment Pydantic
brut, jamais la valeur soumise, un champ identifiable pour un affichage sous le
champ concerné.

Contrat vérifié partout : `detail` est TOUJOURS une chaîne (jamais un tableau —
c'était la cause du « [object Object] » côté client) ; sur un 422, `errors` liste
chaque champ en cause ; aucun message ne contient de vocabulaire Pydantic ou
technique brut.
"""

import json
import re
from dataclasses import dataclass
from typing import Any

import pytest

from app import error_messages, schemas

# Fragments qui ne doivent JAMAIS apparaître dans un message destiné à l'utilisateur :
# vocabulaire Pydantic/FastAPI par défaut, ou noms de champs techniques bruts (sans
# leur article, un nom de champ comme « title » ou « board_id » ne veut rien dire
# pour quelqu'un qui ne lit pas le code).
FORBIDDEN_FRAGMENTS = [
    "Input should",
    "Value error",
    "Assertion failed",
    "field required",
    "Field required",
    "Not authenticated",
    "string_too_long",
    "string_too_short",
    "int_parsing",
    "greater_than_equal",
    "less_than_equal",
    "literal_error",
    "value_error",
    "loc",
    "ctx",
    "pydantic",
]

# Noms de champs techniques : ne doivent apparaître dans AUCUN message (detail ou
# errors[].message), seulement dans errors[].field (destiné au code, pas à l'écran).
TECHNICAL_FIELD_NAMES = [
    "title", "company", "location", "notes", "board_id", "application_id",
    "new_password", "status_filter",
]


def assert_message_is_clean(message: str) -> None:
    """Un message affichable : français, sans fragment Pydantic, sans nom de champ
    technique brut, jamais vide."""
    assert message, "message vide"
    for fragment in FORBIDDEN_FRAGMENTS:
        assert fragment not in message, f"fragment Pydantic {fragment!r} dans {message!r}"
    for name in TECHNICAL_FIELD_NAMES:
        # \b évite de rejeter "location" à cause de "notification" etc. — nos noms
        # sont déjà assez spécifiques, mais on reste rigoureux.
        assert not re.search(rf"\b{name}\b", message), f"nom de champ technique {name!r} dans {message!r}"


def assert_response_shape(response, *, expects_errors: bool) -> dict:
    """Un 422 (ou toute réponse qui en a le format) doit avoir `detail` en CHAÎNE
    (jamais une liste — c'est le bug d'origine) et, si demandé, une clé `errors`.

    `field` n'est PAS exigé sur chaque entrée de `errors` : une erreur qui ne
    désigne aucun champ précis (corps entier illisible, paramètre de chemin ou
    de requête) n'en porte pas — voir error_messages.is_body_field."""
    body = response.json()
    assert isinstance(body.get("detail"), str), f"detail n'est pas une chaîne : {body.get('detail')!r}"
    assert_message_is_clean(body["detail"])
    if expects_errors:
        assert isinstance(body.get("errors"), list) and body["errors"], "errors absent ou vide"
        for error in body["errors"]:
            assert "message" in error
            assert_message_is_clean(error["message"])
    return body


# ---------------------------------------------------------------------------
# Étape 1 : les deux trous connus, PAS ENCORE corrigés à ce stade du lot.
# ---------------------------------------------------------------------------


def test_anonymous_request_to_a_protected_endpoint_is_french(client):
    """Sans Authorization du tout : FastAPI (OAuth2PasswordBearer) répond lui-même
    401 « Not authenticated », AVANT d'atteindre notre code. C'est le message le
    plus souvent vu par un utilisateur réel : une session expirée."""
    response = client.get("/boards")  # aucun header Authorization

    assert response.status_code == 401
    assert_message_is_clean(response.json()["detail"])


def test_unhandled_exception_returns_a_french_json_body():
    """Une exception non prévue doit renvoyer un JSON français générique, jamais le
    texte ou la trace de l'exception, et jamais un corps vide/non-JSON (le défaut
    de Starlette, que `response.statusText` anglais masque côté client).

    Route JETABLE ajoutée au routeur RÉEL de l'app : c'est la façon standard de
    déclencher, via une vraie requête ASGI, le chemin qu'emprunterait un bug non
    prévu — sans dépendre d'un point d'entrée précis ni patcher une fonction déjà
    capturée par référence dans la table de routage (un monkeypatch par nom de
    module n'affecterait pas l'endpoint déjà enregistré)."""
    from fastapi.testclient import TestClient

    from app.main import app

    async def boom():
        raise RuntimeError("mot de passe secret qui ne doit JAMAIS fuiter")

    route_path = "/__test_only_boom__"
    app.add_api_route(route_path, boom, methods=["GET"])
    try:
        # raise_server_exceptions=False : le client laisse passer la réponse
        # produite par l'app (le comportement réel d'un serveur déployé), au lieu
        # de relever l'exception dans le processus de test.
        real_client = TestClient(app, raise_server_exceptions=False)
        response = real_client.get(route_path)
    finally:
        app.router.routes[:] = [
            r for r in app.router.routes if getattr(r, "path", None) != route_path
        ]

    assert response.status_code == 500
    assert response.headers["content-type"].startswith("application/json")
    assert "mot de passe secret" not in response.text
    assert "RuntimeError" not in response.text
    assert "Traceback" not in response.text
    body = response.json()
    assert isinstance(body.get("detail"), str)
    assert_message_is_clean(body["detail"])


# ---------------------------------------------------------------------------
# Garde contre l'oubli : tout champ des schémas d'entrée a un libellé français.
# ---------------------------------------------------------------------------


def _all_labeled_field_names() -> set[str]:
    """Tous les noms de champs des schémas d'ENTRÉE, plus les paramètres de
    chemin/requête entiers (application_id, status_filter — board_id est déjà un
    champ de schéma). C'est l'ensemble que error_messages.FIELD_LABELS doit
    couvrir intégralement : un champ oublié y retomberait sur le libellé neutre
    « Cette information », moins clair qu'un vrai nom."""
    names: set[str] = {"application_id", "status_filter"}
    for obj in vars(schemas).values():
        if isinstance(obj, type) and issubclass(obj, schemas.InputModel) and obj is not schemas.InputModel:
            names.update(obj.model_fields.keys())
    return names


def test_every_input_field_has_a_french_label():
    missing = _all_labeled_field_names() - set(error_messages.FIELD_LABELS)
    assert not missing, f"Champs sans libellé dans error_messages.FIELD_LABELS : {missing}"


# ---------------------------------------------------------------------------
# Le catalogue lui-même : aucun texte ne contient de fragment interdit. Ce test
# porte sur error_messages.py DIRECTEMENT (pas via HTTP) : il protège un futur
# message ajouté au catalogue, avant même qu'un test HTTP ne l'exerce.
# ---------------------------------------------------------------------------


def test_catalog_messages_are_all_clean():
    all_templates = [
        *error_messages.GENERIC_TEMPLATES.values(),
        *error_messages.DEDICATED_MESSAGES.values(),
        error_messages.FALLBACK_MESSAGE,
        error_messages.GENERIC_SERVER_ERROR_DETAIL,
    ]
    for template in all_templates:
        # Les gabarits contiennent {label}/{max_length}/etc. : on les remplit
        # avec des valeurs plates avant de vérifier, comme le ferait
        # message_for_error() en conditions réelles.
        rendered = template.format(
            label="Le champ", max_length=255, min_length=1, ge=1, le=2147483647,
            max_bytes=4096, min="01/01/1900", max="31/12/2100",
        )
        assert_message_is_clean(rendered)


def test_unknown_error_type_falls_back_without_crashing():
    """Un `type` qui n'existe pas (encore) dans le catalogue — un futur champ, une
    future version de Pydantic — ne doit JAMAIS planter ni renvoyer un texte
    brut : repli générique, français, propre."""
    message = error_messages.message_for_error("un_type_totalement_inconnu", "title", {})
    assert message == error_messages.FALLBACK_MESSAGE
    assert_message_is_clean(message)


def test_dedicated_message_with_incomplete_context_falls_back():
    """Un gabarit qui référence une clé absente du `ctx` réel (`ctx` incomplet,
    par ex. une future version de Pydantic qui omettrait une clé) ne doit jamais
    laisser passer un gabarit à moitié rempli ni planter."""
    message = error_messages.message_for_error("string_too_long", "title", {})  # sans max_length
    assert message == error_messages.FALLBACK_MESSAGE


# ---------------------------------------------------------------------------
# Balayage par famille : au moins un déclencheur HTTP RÉEL par type d'erreur du
# catalogue. La garde de couverture, plus bas, empêche d'oublier une entrée du
# catalogue ajoutée sans test correspondant.
# ---------------------------------------------------------------------------


@dataclass
class ErrCtx:
    client: Any
    user: Any
    board_id: int
    application_id: int


@pytest.fixture
def err_ctx(client, make_user, make_application) -> ErrCtx:
    user = make_user()
    application = make_application(user)
    return ErrCtx(client, user, user.default_board_id, application["id"])


def _app_payload(ctx: ErrCtx, **overrides) -> dict:
    return {"board_id": ctx.board_id, "title": "T", "company": "C", **overrides}


# Chaque cas : (id, type Pydantic déclenché, champ attendu ou None, fonction qui
# envoie la requête et renvoie la réponse). `field=None` signifie une erreur qui
# ne désigne aucun champ précis (corps entier illisible).
FAMILY_CASES: list[tuple[str, str, str | None, Any]] = [
    ("champ requis absent", "missing", "title",
     lambda c: c.client.post("/applications", json={"board_id": c.board_id, "company": "C"}, headers=c.user.headers)),
    ("champ vide (obligatoire)", "string_too_short", "title",
     lambda c: c.client.post("/applications", json=_app_payload(c, title=""), headers=c.user.headers)),
    ("mot de passe trop court", "string_too_short", "password",
     lambda c: c.client.post("/auth/register", json={"email": "court@example.com", "password": "short"})),
    ("champ trop long", "string_too_long", "title",
     lambda c: c.client.post("/applications", json=_app_payload(c, title="a" * 256), headers=c.user.headers)),
    ("champ mauvais type (nombre au lieu de texte)", "string_type", "title",
     lambda c: c.client.post("/applications", json=_app_payload(c, title=123), headers=c.user.headers)),
    ("identifiant illisible", "int_parsing", "board_id",
     lambda c: c.client.post("/applications", json=_app_payload(c, board_id="abc"), headers=c.user.headers)),
    ("identifiant flottant", "int_from_float", "board_id",
     lambda c: c.client.post("/applications", json=_app_payload(c, board_id=1.5), headers=c.user.headers)),
    ("identifiant mauvais type", "int_type", "board_id",
     lambda c: c.client.post("/applications", json=_app_payload(c, board_id={"x": 1}), headers=c.user.headers)),
    ("identifiant nul", "greater_than_equal", "board_id",
     lambda c: c.client.post("/applications", json=_app_payload(c, board_id=0), headers=c.user.headers)),
    ("identifiant trop grand", "less_than_equal", "board_id",
     lambda c: c.client.post("/applications", json=_app_payload(c, board_id=99999999999999999999), headers=c.user.headers)),
    ("statut hors enum", "enum", "status",
     lambda c: c.client.patch(f"/applications/{c.application_id}", json={"status": "rejected"}, headers=c.user.headers)),
    ("origine hors liste", "literal_error", "source",
     lambda c: c.client.post("/applications", json=_app_payload(c, source="autre"), headers=c.user.headers)),
    ("email invalide", "value_error", "email",
     lambda c: c.client.post("/auth/register", json={"email": "pas-un-email", "password": "password123"})),
    ("date illisible", "datetime_from_date_parsing", "applied_at",
     lambda c: c.client.patch(f"/applications/{c.application_id}", json={"applied_at": "pas une date"}, headers=c.user.headers)),
    ("date mauvais type", "datetime_type", "applied_at",
     lambda c: c.client.patch(f"/applications/{c.application_id}", json={"applied_at": {"a": 1}}, headers=c.user.headers)),
    ("date hors plage", "applied_at_out_of_range", "applied_at",
     lambda c: c.client.patch(f"/applications/{c.application_id}", json={"applied_at": "1899-12-31T23:59:59"}, headers=c.user.headers)),
    ("null interdit sur champ obligatoire", "null_not_allowed", "title",
     lambda c: c.client.patch(f"/applications/{c.application_id}", json={"title": None}, headers=c.user.headers)),
    ("mot de passe présenté trop long", "password_too_many_bytes", "password",
     lambda c: c.client.post("/auth/login", json={"email": c.user.email, "password": "x" * 5000})),
    ("corps JSON invalide", "json_invalid", None,
     lambda c: c.client.post("/applications", content="pas du json",
                              headers={"Content-Type": "application/json", **c.user.headers})),
    ("corps pas un objet", "model_attributes_type", None,
     lambda c: c.client.post("/applications", content="[1,2]",
                              headers={"Content-Type": "application/json", **c.user.headers})),
]


@pytest.mark.parametrize("label,error_type,field,send", FAMILY_CASES, ids=[c[0] for c in FAMILY_CASES])
def test_error_family_produces_a_clean_message(err_ctx, label, error_type, field, send):
    response = send(err_ctx)

    assert response.status_code == 422, label
    body = assert_response_shape(response, expects_errors=True)
    matching = [e for e in body["errors"] if e.get("field") == field] if field else body["errors"]
    assert matching, f"{label} : aucune erreur pour le champ {field!r} dans {body['errors']}"
    if field is None:
        assert all("field" not in e for e in body["errors"]), label


def test_family_cases_cover_the_whole_catalog():
    """GARDE : toute entrée du catalogue (générique ou dédiée) doit être exercée
    par au moins un cas ci-dessus. Un type ajouté à error_messages.py sans cas
    correspondant ici fait échouer ce test — c'est le filet qui empêche un
    message d'être écrit puis jamais vérifié en conditions réelles."""
    exercised = {error_type for _, error_type, _, _ in FAMILY_CASES}
    generic_types = set(error_messages.GENERIC_TEMPLATES) - {"nul_character", "surrogate_character"}
    dedicated_types = {t for t, _ in error_messages.DEDICATED_MESSAGES}
    missing = (generic_types | dedicated_types) - exercised
    assert not missing, f"Types du catalogue jamais exercés par un test : {missing}"


# ---------------------------------------------------------------------------
# NUL et surrogate isolé : déjà exercés champ par champ dans
# test_input_validation.py (422 + field) ; ici on vérifie en plus le MESSAGE.
# Corps envoyé en JSON BRUT : json.dumps échappe \u0000/\ud800 en ASCII-safe,
# ce que `json=` (httpx) ne garantit pas pour un surrogate isolé.
# ---------------------------------------------------------------------------


def test_malformed_json_body_message_is_exact(err_ctx):
    response = err_ctx.client.post(
        "/applications", content="pas du json",
        headers={"Content-Type": "application/json", **err_ctx.user.headers},
    )
    assert response.status_code == 422
    body = response.json()
    assert body["detail"] == "La requête est mal formée."
    assert "field" not in body["errors"][0]


def test_body_not_an_object_message_is_exact(err_ctx):
    response = err_ctx.client.post(
        "/applications", content="[1,2]",
        headers={"Content-Type": "application/json", **err_ctx.user.headers},
    )
    assert response.status_code == 422
    body = response.json()
    assert body["detail"] == "La requête est mal formée."
    assert "field" not in body["errors"][0]


def test_invalid_email_message_is_exact(client):
    response = client.post(
        "/auth/register", json={"email": "pas-un-email", "password": "password123"}
    )
    assert response.status_code == 422
    body = response.json()
    assert body["detail"] == "L'adresse email n'est pas valide."
    assert body["errors"] == [{"field": "email", "message": body["detail"]}]


@pytest.mark.parametrize(
    "label,error_type,bad_char",
    [("NUL", "nul_character", "a\x00b"), ("surrogate isolé", "surrogate_character", "a\ud800b")],
)
def test_unstorable_character_message_is_clean(err_ctx, label, error_type, bad_char):
    body = json.dumps(_app_payload(err_ctx, title=bad_char))

    response = err_ctx.client.post(
        "/applications",
        content=body,
        headers={"Content-Type": "application/json", **err_ctx.user.headers},
    )

    assert response.status_code == 422, label
    payload = assert_response_shape(response, expects_errors=True)
    assert payload["errors"][0]["field"] == "title"
    assert "caractère" in payload["errors"][0]["message"]
