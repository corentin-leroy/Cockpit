"""Configuration et fixtures partagées de la suite de tests.

Isolation de la base de test — la partie la plus importante de ce fichier :

1. On force l'environnement AVANT tout import de l'application. `app.main` appelle
   `load_dotenv()` à l'import, or le vrai `.env` contient une CLÉ BREVO RÉELLE et
   une `DATABASE_URL` pointant sur cockpit.db. `load_dotenv()` n'écrase PAS les
   variables déjà présentes (override=False par défaut) : en les posant ici en
   premier, on garantit que les tests ne touchent jamais la base de prod et
   n'envoient jamais de vrai email.
   - BREVO_API_KEY / BREVO_SENDER_EMAIL vidées → email.py bascule en MODE DEV
     (aucun appel réseau, le lien est simplement logué). Les tests d'inscription
     déclenchent un envoi de vérification : il ne doit rien envoyer.
   - DATABASE_URL = "sqlite://" (in-memory jetable) → le `create_all` exécuté à
     l'import de app.main ne crée rien dans cockpit.db.
   - JWT_SECRET_KEY fixé → le login peut forger des tokens sans dépendre du .env.

2. La base RÉELLE des tests est un moteur SQLite EN MÉMOIRE dédié, partagé entre
   toutes les connexions grâce à StaticPool (sans lui, chaque connexion SQLite
   in-memory verrait une base vide distincte). On surcharge la dépendance
   `get_db` de FastAPI pour que TOUTE requête de l'app passe par ce moteur.

3. Le schéma est (re)créé avant chaque test et détruit après (fixture `client`,
   portée fonction) : chaque test démarre sur une base vierge. Les tests sont
   donc indépendants et exécutables dans n'importe quel ordre.
"""

import os

# --- (1) Environnement figé AVANT tout import applicatif ---
os.environ["DATABASE_URL"] = "sqlite://"  # jetable ; le vrai moteur de test est défini plus bas
os.environ["JWT_SECRET_KEY"] = "test-secret-key-not-used-in-production"
os.environ["BREVO_API_KEY"] = ""  # vide → mode DEV, aucun email envoyé
os.environ["BREVO_SENDER_EMAIL"] = ""

from dataclasses import dataclass, field

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.security import verify_password  # ré-exporté pour les tests (mot de passe non stocké en clair)

# --- (2) Moteur de test en mémoire, partagé entre connexions ---
test_engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(bind=test_engine, autoflush=False, autocommit=False)


def _override_get_db():
    """Version de test de get_db : une session par requête, sur le moteur de test.

    On reproduit le cycle de production (session ouverte puis fermée par requête)
    pour que les tests d'ownership, qui enchaînent plusieurs requêtes, voient bien
    l'état commité et non un cache de session partagé."""
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = _override_get_db


@pytest.fixture
def client():
    """Client de test FastAPI sur une base vierge, recréée pour CHAQUE test."""
    Base.metadata.create_all(bind=test_engine)
    with TestClient(app) as test_client:
        yield test_client
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture
def db_session():
    """Session directe sur la base de test, pour les assertions sur l'état stocké
    (ex. vérifier qu'un mot de passe n'est jamais persisté en clair)."""
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


# --- (3) Helpers : créer un utilisateur authentifié et des ressources ---


@dataclass
class AuthedUser:
    """Un utilisateur inscrit + connecté, avec tout le nécessaire pour agir en son nom."""

    email: str
    password: str
    token: str
    headers: dict = field(default_factory=dict)
    default_board_id: int = 0


@pytest.fixture
def make_user(client):
    """Factory : inscrit un utilisateur, le connecte et renvoie un AuthedUser.

    Chaque appel génère un email unique (utilisateur A, B, C… dans un même test).
    Le board par défaut créé à l'inscription est récupéré au passage."""
    created = {"count": 0}

    def _make(password: str = "password123") -> AuthedUser:
        created["count"] += 1
        email = f"user{created['count']}@example.com"

        register = client.post("/auth/register", json={"email": email, "password": password})
        assert register.status_code == 201, register.text

        login = client.post("/auth/login", json={"email": email, "password": password})
        assert login.status_code == 200, login.text
        token = login.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        boards = client.get("/boards", headers=headers).json()
        return AuthedUser(
            email=email,
            password=password,
            token=token,
            headers=headers,
            default_board_id=boards[0]["id"],
        )

    return _make


@pytest.fixture
def make_board(client):
    """Factory : crée un tableau pour un AuthedUser et renvoie son id."""

    def _make(user: AuthedUser, name: str = "Autre tableau") -> int:
        response = client.post("/boards", json={"name": name}, headers=user.headers)
        assert response.status_code == 201, response.text
        return response.json()["id"]

    return _make


@pytest.fixture
def make_application(client):
    """Factory : crée une candidature dans un tableau donné (ou le board par défaut)."""

    def _make(user: AuthedUser, board_id: int | None = None, **overrides) -> dict:
        payload = {
            "board_id": board_id if board_id is not None else user.default_board_id,
            "title": "Développeur",
            "company": "ACME",
            **overrides,
        }
        response = client.post("/applications", json=payload, headers=user.headers)
        assert response.status_code == 201, response.text
        return response.json()

    return _make
