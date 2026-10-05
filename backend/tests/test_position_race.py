"""Positions du kanban sous requêtes SIMULTANÉES (deux onglets, double clic…).

Chaque écriture qui touche une position relit une ou deux colonnes, calcule la
nouvelle numérotation, puis l'écrit. Sans sérialisation, deux requêtes lisent la
même colonne avant qu'aucune n'ait écrit, et la seconde écrase la première sur des
données périmées : doublons, trous, carte numérotée deux fois. La garantie est un
VERROU PAR UTILISATEUR pris en PREMIÈRE instruction de la transaction
(routers/applications.py, `_lock_positions_of`) : toutes les écritures de
positions d'un même utilisateur passent l'une après l'autre, chacune relisant
l'état laissé par la précédente.

Comme test_token_race.py : base SQLite FICHIER (une connexion par requête), la
base en mémoire à connexion unique des autres tests ne permettant pas de vraie
concurrence. Sous SQLite, le verrou est la première écriture de la transaction ;
sous PostgreSQL, un verrou de ligne : même SQL, vérifié à la main sur PostgreSQL
18 (cf. CLAUDE.md).

Invariant vérifié après chaque manche, sur l'ÉTAT STOCKÉ : chaque colonne active
vaut exactement 0..n-1, toute archivée a une position NULL.
"""

import random
import threading
from collections import Counter
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.database import Base, get_db
from app.main import app
from app.models import Application

STATUSES = ["saved", "applied", "followed_up", "interview", "accepted"]
SIMULTANEOUS_REQUESTS = 40
ROUNDS = 5
INITIAL_APPLICATIONS = 16


@pytest.fixture
def file_database(tmp_path, monkeypatch):
    """Base SQLite fichier + session par requête, substituées à celles de conftest
    le temps du test (le dictionnaire d'overrides est restauré ensuite)."""
    engine = create_engine(
        f"sqlite:///{tmp_path / 'position_race.db'}",
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
    yield engine
    engine.dispose()


def _incoherences(engine) -> list[str]:
    """Écarts à l'invariant, lus en base (liste vide = cohérent)."""
    problems = []
    columns: dict[tuple, list] = {}
    with Session(engine) as session:
        for app_ in session.scalars(select(Application)):
            if app_.archived_at is not None:
                if app_.position is not None:
                    problems.append(f"archivée {app_.id} numérotée {app_.position}")
                continue
            columns.setdefault((app_.board_id, app_.status.value), []).append(app_.position)
    for key, positions in sorted(columns.items()):
        if None in positions or sorted(positions) != list(range(len(positions))):
            problems.append(f"colonne {key} : {sorted(positions, key=lambda p: (p is not None, p))}")
    return problems


def _setup_user(client: TestClient) -> tuple[dict, list[int]]:
    """Un utilisateur, deux tableaux. Renvoie (en-têtes, ids des tableaux)."""
    credentials = {"email": "race@example.com", "password": "password123"}
    assert client.post("/auth/register", json=credentials).status_code == 201
    token = client.post("/auth/login", json=credentials).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    first = client.get("/boards", headers=headers).json()[0]["id"]
    second = client.post("/boards", json={"name": "Second"}, headers=headers).json()["id"]
    return headers, [first, second]


def _random_operations(rng: random.Random, ids: list[int], boards: list[int], count: int):
    """Mélange de TOUTES les écritures qui touchent une position. Une même carte peut
    être visée plusieurs fois : c'est le cas qui fait diverger deux onglets."""
    operations = []
    for _ in range(count):
        target = rng.choice(ids)
        kind = rng.choices(
            ["move", "status", "board", "archive", "unarchive", "create", "delete"],
            weights=[10, 3, 2, 2, 2, 2, 1],
        )[0]
        if kind == "move":
            body = {"status": rng.choice(STATUSES), "position": rng.randint(0, 12)}
            operations.append(("POST", f"/applications/{target}/move", body))
        elif kind == "status":
            operations.append(("PATCH", f"/applications/{target}", {"status": rng.choice(STATUSES)}))
        elif kind == "board":
            operations.append(("PATCH", f"/applications/{target}", {"board_id": rng.choice(boards)}))
        elif kind in ("archive", "unarchive"):
            operations.append(("POST", f"/applications/{target}/{kind}", None))
        elif kind == "create":
            body = {"board_id": rng.choice(boards), "title": "Nouvelle", "company": "ACME"}
            operations.append(("POST", "/applications", body))
        else:
            operations.append(("DELETE", f"/applications/{target}", None))
    return operations


def _fire_simultaneously(headers: dict, operations: list) -> list:
    """Lance toutes les requêtes EN MÊME TEMPS (barrière). Une exception non gérée
    (= un 500) devient un texte, comptée comme telle."""
    barrier = threading.Barrier(len(operations))

    def go(operation):
        method, path, body = operation
        client = TestClient(app)  # lève les exceptions non gérées
        barrier.wait()
        try:
            response = client.request(method, path, json=body, headers=headers)
            return response.status_code
        except Exception as exc:  # noqa: BLE001 — c'est précisément ce qu'on compte
            return f"exception {type(exc).__name__}: {exc}"

    with ThreadPoolExecutor(len(operations)) as pool:
        return list(pool.map(go, operations))


def test_simultaneous_position_writes_keep_every_column_coherent(file_database):
    """40 écritures simultanées par manche (déplacements dans et entre colonnes,
    changements de statut et de tableau, archivages, désarchivages, créations,
    suppressions), 5 manches au tirage fixé : après chaque manche, aucune colonne
    n'a de doublon, de trou ni de NULL, et aucune requête n'a planté.

    Codes admis : 200/201/204, 404 (carte supprimée par une requête concurrente) et
    409 (archiver une archivée, déplacer une archivée…). Jamais de 500."""
    client = TestClient(app)
    headers, boards = _setup_user(client)
    rng = random.Random(20261005)

    for round_number in range(1, ROUNDS + 1):
        for _ in range(INITIAL_APPLICATIONS):
            created = client.post(
                "/applications",
                json={"board_id": rng.choice(boards), "title": "Seed", "company": "ACME"},
                headers=headers,
            )
            assert created.status_code == 201
        with Session(file_database) as session:
            ids = list(session.scalars(select(Application.id)))

        results = _fire_simultaneously(
            headers, _random_operations(rng, ids, boards, SIMULTANEOUS_REQUESTS)
        )

        codes = Counter(str(code) for code in results)
        assert set(codes) <= {"200", "201", "204", "404", "409"}, (
            f"manche {round_number} : {dict(codes)}"
        )
        assert _incoherences(file_database) == [], f"manche {round_number} ({dict(codes)})"
