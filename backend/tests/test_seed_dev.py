"""Script de remplissage de la base de dev (`scripts/seed_dev.py`).

Règles vérifiées (cf. `dev-docs/seed-dev.md`) :
- garde-fou : refus AVANT toute connexion si la base effectivement utilisée par
  l'application n'est pas SQLite, que DATABASE_URL soit définie ou non, sans jamais
  afficher l'URL ;
- contenu : un compte demo@cockpit.example vérifié, trois tableaux, 40 actives réparties
  sur les cinq statuts, 15 archivées, positions 0..n-1 dans chaque colonne ;
- compte déjà présent : arrêt sans RIEN écrire ;
- --reset : supprime et recrée le SEUL compte de test, les autres comptes restent
  intacts ligne pour ligne ;
- déterminisme : deux exécutions produisent les mêmes contenus.

Base : celle de conftest.py (SQLite en mémoire, recréée à chaque test par la
fixture `client`), passée au script par son paramètre `engine`.
"""

import pytest
from sqlalchemy import create_engine, event, select

import app.database
from app.database import Base
from app.models import Application, ApplicationStatus, Board, SecurityToken, User
from app.security import verify_password
from scripts import seed_dev

DEMO_EMAIL = "demo@cockpit.example"

# Répartition attendue des ACTIVES, par tableau puis par statut (valeur de l'enum).
EXPECTED_ACTIVE = {
    "Alternance": {"saved": 12, "applied": 5, "followed_up": 2, "interview": 2, "accepted": 1},
    "CDI": {"saved": 3, "applied": 4, "followed_up": 2, "interview": 1, "accepted": 0},
    "Stage": {"saved": 2, "applied": 3, "followed_up": 1, "interview": 1, "accepted": 1},
}
EXPECTED_ARCHIVED = {"Alternance": 6, "CDI": 5, "Stage": 4}


# ---------------------------------------------------------------------------
# Outils
# ---------------------------------------------------------------------------


@pytest.fixture
def seed(client, db_session):
    """Lance le script sur la base de test ; renvoie son code de sortie."""
    engine = db_session.get_bind()

    def _run(*argv: str) -> int:
        return seed_dev.main(list(argv), engine=engine)

    return _run


def _demo_user(db_session) -> User | None:
    db_session.expire_all()
    return db_session.scalar(select(User).where(User.email == DEMO_EMAIL))


def _demo_applications(db_session) -> list[tuple[Board, Application]]:
    db_session.expire_all()
    return db_session.execute(
        select(Board, Application)
        .join(Application, Application.board_id == Board.id)
        .join(User, Board.user_id == User.id)
        .where(User.email == DEMO_EMAIL)
    ).all()


def _dump(db_session) -> dict[str, list[tuple]]:
    """Toutes les lignes de toutes les tables, triées par id (lecture seule)."""
    db_session.expire_all()
    return {
        table.name: sorted(
            (tuple(row) for row in db_session.execute(select(table))), key=lambda r: r[0]
        )
        for table in Base.metadata.sorted_tables
    }


def _rows_of_user(db_session, email: str) -> dict[str, list[tuple]]:
    """Lignes (toutes colonnes) d'un compte et de ses données, triées par id."""
    db_session.expire_all()
    user = db_session.scalar(select(User).where(User.email == email))
    assert user is not None
    users = User.__table__
    boards = Board.__table__
    applications = Application.__table__
    tokens = SecurityToken.__table__
    queries = {
        "users": select(users).where(users.c.id == user.id),
        "boards": select(boards).where(boards.c.user_id == user.id),
        "applications": select(applications)
        .join(boards, applications.c.board_id == boards.c.id)
        .where(boards.c.user_id == user.id),
        "security_tokens": select(tokens).where(tokens.c.user_id == user.id),
    }
    return {
        name: sorted((tuple(row) for row in db_session.execute(query)), key=lambda r: r[0])
        for name, query in queries.items()
    }


def _content(db_session) -> list[tuple]:
    """Contenu métier du compte de test, sans identifiants ni horodatages serveur.
    Trié par repr : position et dates valent parfois None (non comparable à int)."""
    rows = [
        (
            board.name,
            app_.status.value,
            app_.position,
            app_.archived_at is not None,
            app_.title,
            app_.company,
            app_.location,
            app_.url,
            app_.source,
            app_.notes,
            app_.applied_at,
        )
        for board, app_ in _demo_applications(db_session)
    ]
    return sorted(rows, key=repr)


# ---------------------------------------------------------------------------
# Garde-fou : SQLite uniquement
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("argv", [[], ["--reset"]])
@pytest.mark.parametrize("env_value", [None, "sqlite:///./cockpit.db"])
def test_refuses_a_non_sqlite_database_before_any_connection(
    monkeypatch, capsys, argv, env_value
):
    """La base EFFECTIVE de l'application (app.database.engine) est PostgreSQL :
    refus, aucune connexion ouverte (donc aucune écriture), URL jamais affichée.
    Vrai que DATABASE_URL soit absente ou qu'elle annonce faussement un SQLite : le
    contrôle porte sur le moteur réellement utilisé, pas sur la variable."""
    postgres = create_engine("postgresql+psycopg://seeduser:pw-must-not-leak@db.invalid:5432/prod")
    attempts: list[str] = []

    @event.listens_for(postgres, "do_connect")
    def _forbid_connection(*args, **kwargs):
        attempts.append("connect")
        raise RuntimeError("le script a tenté de se connecter à la base PostgreSQL")

    monkeypatch.setattr(app.database, "engine", postgres)
    if env_value is None:
        monkeypatch.delenv("DATABASE_URL", raising=False)
    else:
        monkeypatch.setenv("DATABASE_URL", env_value)

    code = seed_dev.main(argv)

    captured = capsys.readouterr()
    output = captured.out + captured.err
    assert code != 0
    assert attempts == []
    assert "SQLite" in output
    for leak in ("pw-must-not-leak", "seeduser", "db.invalid", "postgresql+psycopg://", "/prod"):
        assert leak not in output


# ---------------------------------------------------------------------------
# Contenu créé
# ---------------------------------------------------------------------------


def test_creates_a_verified_demo_account_that_can_log_in(seed, client, db_session):
    assert seed() == 0

    user = _demo_user(db_session)
    assert user is not None
    assert user.is_verified is True
    assert user.hashed_password is not None
    assert verify_password(seed_dev.DEMO_PASSWORD, user.hashed_password)

    # Par le vrai chemin de connexion de l'API.
    login = client.post("/auth/login", json={"email": DEMO_EMAIL, "password": seed_dev.DEMO_PASSWORD})
    assert login.status_code == 200, login.text
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    assert client.get("/auth/me", headers=headers).json()["is_verified"] is True
    assert len(client.get("/applications", headers=headers).json()) == 40


def test_active_cards_per_board_and_status(seed, db_session):
    assert seed() == 0

    user = _demo_user(db_session)
    board_names = sorted(db_session.scalars(select(Board.name).where(Board.user_id == user.id)))
    assert board_names == ["Alternance", "CDI", "Stage"]

    counts = {name: {s.value: 0 for s in ApplicationStatus} for name in EXPECTED_ACTIVE}
    for board, app_ in _demo_applications(db_session):
        if app_.archived_at is None:
            counts[board.name][app_.status.value] += 1
    assert counts == EXPECTED_ACTIVE
    assert sum(sum(c.values()) for c in counts.values()) == 40
    assert max(max(c.values()) for c in counts.values()) >= 12


def test_positions_are_contiguous_in_every_column(seed, db_session):
    """Chaque colonne active vaut exactement 0..n-1 ; toute archivée a une position
    NULL (état qu'écrit l'application, cohérent avec le glisser-déposer)."""
    assert seed() == 0

    columns: dict[tuple[str, str], list] = {}
    for board, app_ in _demo_applications(db_session):
        if app_.archived_at is not None:
            assert app_.position is None, f"archivée « {app_.title} » numérotée"
            continue
        columns.setdefault((board.name, app_.status.value), []).append(app_.position)
    assert columns, "aucune colonne active"
    for key, positions in columns.items():
        assert None not in positions, f"colonne {key} : position NULL"
        assert sorted(positions) == list(range(len(positions))), (
            f"colonne {key} : positions {sorted(positions)}"
        )


def test_kanban_order_is_the_listed_order_and_survives_a_drag(seed, client, db_session):
    """L'API (ordre du kanban) affiche chaque colonne dans l'ordre où le script la
    liste, première carte en haut ; un glisser-déposer réel (POST /move) sur ces
    données garde des positions continues."""
    assert seed() == 0
    login = client.post("/auth/login", json={"email": DEMO_EMAIL, "password": seed_dev.DEMO_PASSWORD})
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    boards = {b["name"]: b["id"] for b in client.get("/boards", headers=headers).json()}

    for name, board_id in boards.items():
        listed = client.get("/applications", params={"board_id": board_id}, headers=headers).json()
        for status_ in ApplicationStatus:
            shown = [a["title"] for a in listed if a["status"] == status_.value]
            expected = [
                c.title for c in seed_dev.CARDS
                if c.board == name and c.status is status_ and not c.archived
            ]
            assert shown == expected, f"{name} / {status_.value}"

    saved = client.get(
        "/applications",
        params={"board_id": boards["Alternance"], "status_filter": "saved"},
        headers=headers,
    ).json()
    moved = client.post(
        f"/applications/{saved[-1]['id']}/move",
        json={"status": "applied", "position": 2},
        headers=headers,
    )
    assert moved.status_code == 200, moved.text
    applied = client.get(
        "/applications",
        params={"board_id": boards["Alternance"], "status_filter": "applied"},
        headers=headers,
    ).json()
    assert [a["id"] for a in applied].index(saved[-1]["id"]) == 2

    db_session.expire_all()
    columns: dict[tuple, list] = {}
    for app_ in db_session.scalars(select(Application).where(Application.archived_at.is_(None))):
        columns.setdefault((app_.board_id, app_.status), []).append(app_.position)
    for key, positions in columns.items():
        assert sorted(positions) == list(range(len(positions))), f"colonne {key}"


def test_archived_cards_per_board(seed, db_session):
    assert seed() == 0

    archived = {name: 0 for name in EXPECTED_ARCHIVED}
    statuses = set()
    for board, app_ in _demo_applications(db_session):
        if app_.archived_at is not None:
            archived[board.name] += 1
            statuses.add(app_.status)
    assert archived == EXPECTED_ARCHIVED
    assert sum(archived.values()) == 15
    # L'archivage garde le statut : les archivées ne sont pas toutes « Repérée ».
    assert len(statuses) >= 3


def test_two_runs_produce_the_same_content(seed, db_session):
    assert seed() == 0
    first = _content(db_session)
    assert seed("--reset") == 0
    assert _content(db_session) == first
    assert len(first) == 55


# ---------------------------------------------------------------------------
# Compte déjà présent, --reset
# ---------------------------------------------------------------------------


def test_stops_without_writing_when_the_account_already_exists(seed, db_session, capsys):
    assert seed() == 0
    before = _dump(db_session)
    capsys.readouterr()

    assert seed() != 0

    assert _dump(db_session) == before
    output = "".join(capsys.readouterr())
    assert DEMO_EMAIL in output
    assert "--reset" in output


def test_stops_without_writing_when_a_bare_demo_account_exists(seed, db_session):
    """Compte de test présent mais vide (créé à la main) : rien n'est ajouté."""
    db_session.add(User(email=DEMO_EMAIL, hashed_password="x", is_verified=False))
    db_session.commit()
    before = _dump(db_session)

    assert seed() != 0

    assert _dump(db_session) == before


def test_reset_recreates_only_the_demo_account(seed, client, db_session, make_user, make_board, make_application):
    """Deux autres comptes, dont un à l'adresse proche de celle du compte de test :
    leurs lignes (compte, tableaux, candidatures, jetons) sont identiques avant et
    après --reset ; le compte de test est recréé complet."""
    other = make_user()
    second_board = make_board(other, "Mon tableau")
    make_application(other, title="Carte d'un autre compte")
    archived = make_application(other, second_board, title="Archivée d'un autre compte")
    assert client.post(f"/applications/{archived['id']}/archive", headers=other.headers).status_code == 200
    lookalike = "copie-demo@cockpit.example"
    assert client.post("/auth/register", json={"email": lookalike, "password": "password123"}).status_code == 201

    assert seed() == 0
    others_before = {email: _rows_of_user(db_session, email) for email in (other.email, lookalike)}
    table_sizes_before = {name: len(rows) for name, rows in _dump(db_session).items()}

    assert seed("--reset") == 0

    for email, rows in others_before.items():
        assert _rows_of_user(db_session, email) == rows, f"compte {email} modifié"
    demo = _demo_user(db_session)
    assert demo is not None
    # Recréé, pas ajouté : 3 tableaux et 55 cartes (et non le double), et chaque
    # table compte autant de lignes qu'avant (ni reste de l'ancien, ni perte).
    assert len(db_session.scalars(select(Board).where(Board.user_id == demo.id)).all()) == 3
    assert len(_demo_applications(db_session)) == 55
    assert {name: len(rows) for name, rows in _dump(db_session).items()} == table_sizes_before


def test_reset_without_an_existing_account_creates_it(seed, db_session):
    assert seed("--reset") == 0
    assert _demo_user(db_session) is not None
    assert len(_demo_applications(db_session)) == 55
