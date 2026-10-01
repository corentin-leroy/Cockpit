"""Inscription concurrente de la MÊME adresse : une 201, toutes les autres en 409.

Le contrôle de doublon de /auth/register lit puis insère. Deux requêtes (ou plus)
qui passent la lecture avant qu'aucune n'ait commité arrivent toutes à l'INSERT, et
seule la contrainte unique de la base les départage. Avant correction, les perdantes
levaient une IntegrityError non gérée : un 500 sur un endpoint public.

Le nombre de perdantes n'est pas aléatoire : il vaut la taille maximale du pool de
connexions (5 + 10 = 15) moins un. Les 15 premières requêtes passent le contrôle
ensemble (chacune tient une connexion pendant le hachage bcrypt), une gagne, 14
heurtent la contrainte unique, et les suivantes attendent une connexion puis voient
le compte (409). Mesuré : 14 x 500 / 25 x 409 / 1 x 201 sur chaque manche, sous
PostgreSQL comme sous SQLite fichier.

Ces tests utilisent une base SQLite FICHIER (une connexion par requête, pool par
défaut), et non la base en mémoire à connexion unique des autres tests : c'est ce qui
donne une vraie concurrence entre requêtes.
"""

import threading
from collections import Counter
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from app.database import Base, get_db
from app.main import app
from app.models import Board, User
from app.rate_limit import limiters

EMAIL_TAKEN_DETAIL = "Un compte existe déjà avec cet email."
SIMULTANEOUS_REQUESTS = 40
ROUNDS = 5


@pytest.fixture
def file_database(tmp_path, monkeypatch):
    """Base SQLite fichier + session par requête, substituées à celles de conftest
    le temps du test (le dictionnaire d'overrides est restauré ensuite)."""
    engine = create_engine(
        f"sqlite:///{tmp_path / 'race.db'}",
        connect_args={"check_same_thread": False, "timeout": 30},
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    def override_get_db():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    monkeypatch.setitem(app.dependency_overrides, get_db, override_get_db)
    # Ce test vérifie la contrainte UNIQUE en base face à 40 inscriptions simultanées de
    # la même adresse depuis la même IP : le plafond de 20 inscriptions par heure et par
    # IP (app/rate_limit.py) en refuserait la moitié en 429 et masquerait ce qu'il teste.
    # Le limiteur a ses propres tests (test_auth_rate_limit.py).
    monkeypatch.setattr(limiters, "enabled", False)
    yield engine
    engine.dispose()


def _register_simultaneously(email: str, count: int) -> list:
    """`count` inscriptions de la même adresse lancées EN MÊME TEMPS (barrière).
    Renvoie les codes HTTP ; une exception non gérée (= un 500) est renvoyée telle
    quelle sous forme de texte, pour que l'assertion l'affiche."""
    barrier = threading.Barrier(count)

    def go(_):
        client = TestClient(app)  # lève les exceptions non gérées
        barrier.wait()
        try:
            response = client.post(
                "/auth/register", json={"email": email, "password": "password123"}
            )
            return response.status_code
        except Exception as exc:  # noqa: BLE001 — c'est précisément ce qu'on compte
            return f"exception {type(exc).__name__}"

    with ThreadPoolExecutor(count) as pool:
        return list(pool.map(go, range(count)))


def test_simultaneous_registrations_give_one_201_and_the_rest_409(file_database):
    """40 requêtes simultanées, 5 manches : exactement une 201, toutes les autres en
    409, aucune exception ; et un seul compte (avec son tableau par défaut) par
    manche. Répété car la course ne doit pas dépendre d'un tirage chanceux."""
    for round_number in range(1, ROUNDS + 1):
        email = f"course{round_number}@example.com"

        results = _register_simultaneously(email, SIMULTANEOUS_REQUESTS)

        assert Counter(results) == {201: 1, 409: SIMULTANEOUS_REQUESTS - 1}, (
            f"manche {round_number} : {dict(Counter(map(str, results)))}"
        )
        with file_database.connect() as connection:
            users = connection.scalar(
                select(func.count()).select_from(User).where(User.email == email)
            )
            boards = connection.scalar(
                select(func.count())
                .select_from(Board)
                .join(User, Board.user_id == User.id)
                .where(User.email == email)
            )
        assert users == 1
        assert boards == 1  # pas de tableau orphelin laissé par une perdante


def test_another_integrity_error_is_not_disguised_as_email_taken(client, db_session, monkeypatch):
    """Une IntegrityError qui n'est PAS un doublon d'email doit rester une erreur
    visible (500), pas devenir un « email déjà pris » trompeur. La correction relit
    l'email après le rollback : ici aucun compte n'existe, l'exception remonte."""
    from sqlalchemy.exc import IntegrityError

    original_get_db = app.dependency_overrides[get_db]

    class FailingFlush:
        """Session réelle dont le flush lève une violation d'intégrité étrangère."""

        def __init__(self, session):
            self._session = session

        def flush(self, *args, **kwargs):
            raise IntegrityError("INSERT ...", {}, Exception("autre contrainte violée"))

        def __getattr__(self, name):
            return getattr(self._session, name)

    def failing_get_db():
        generator = original_get_db()
        session = next(generator)
        try:
            yield FailingFlush(session)
        finally:
            generator.close()

    monkeypatch.setitem(app.dependency_overrides, get_db, failing_get_db)

    with pytest.raises(IntegrityError):
        client.post(
            "/auth/register",
            json={"email": "autre@example.com", "password": "password123"},
        )
    assert db_session.scalar(select(func.count()).select_from(User)) == 0


def test_registration_that_slips_past_the_precheck_is_a_409(client, db_session, monkeypatch):
    """Version DÉTERMINISTE de la course : le contrôle préalable est rendu aveugle (il
    ne voit pas le compte déjà créé), donc l'INSERT heurte la contrainte unique. La
    réponse doit être le MÊME 409, avec le même corps, que celle du contrôle préalable.
    """
    payload = {"email": "aveugle@example.com", "password": "password123"}
    assert client.post("/auth/register", json=payload).status_code == 201
    through_precheck = client.post("/auth/register", json=payload)
    assert through_precheck.status_code == 409
    assert through_precheck.json()["detail"] == EMAIL_TAKEN_DETAIL

    # `get_db` que conftest a installé : on l'enveloppe au lieu de le recréer.
    original_get_db = app.dependency_overrides[get_db]

    class BlindPrecheck:
        """Session réelle dont le PREMIER scalar() (le contrôle de doublon) ne voit
        rien ; tout le reste (add, flush, commit, rollback, relecture) est réel."""

        def __init__(self, session):
            self._session = session
            self._first_scalar = True

        def scalar(self, *args, **kwargs):
            if self._first_scalar:
                self._first_scalar = False
                return None
            return self._session.scalar(*args, **kwargs)

        def __getattr__(self, name):
            return getattr(self._session, name)

    def blind_get_db():
        generator = original_get_db()
        session = next(generator)
        try:
            yield BlindPrecheck(session)
        finally:
            generator.close()  # exécute le `finally` d'origine : session.close()

    monkeypatch.setitem(app.dependency_overrides, get_db, blind_get_db)

    slipped = client.post("/auth/register", json=payload)

    assert slipped.status_code == 409
    assert slipped.json() == through_precheck.json()
    assert db_session.scalar(
        select(func.count()).select_from(User).where(User.email == payload["email"])
    ) == 1
