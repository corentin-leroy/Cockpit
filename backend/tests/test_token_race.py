"""Consommation concurrente d'un SecurityToken : un seul gagnant, tous les autres en 400.

/auth/reset-password et /auth/verify-email doivent être à USAGE UNIQUE. Une
consommation qui lit le jeton, teste `consumed_at` en Python, puis l'écrit plus tard
laisse une fenêtre où plusieurs requêtes passent le même contrôle : le jeton sert
alors plusieurs fois (et, pour la réinitialisation, plusieurs mots de passe sont
écrits l'un sur l'autre). La fenêtre de reset est large (bcrypt, ~0,2 s, entre la
lecture et le commit) ; celle de la vérification est étroite.

Comme test_registration_race.py, ces tests utilisent une base SQLite FICHIER (une
connexion par requête) et non la base en mémoire à connexion unique des autres
tests, qui ne permettrait pas de vraie concurrence. Les jetons sont semés
directement en base : c'est l'état stocké qui décide, pas l'email envoyé.
"""

import threading
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.database import Base, get_db
from app.main import app
from app.models import SecurityToken, TokenPurpose, User
from app.security import generate_url_token, hash_password, hash_token, utcnow, verify_password

INVALID_LINK_DETAIL = "Ce lien est invalide ou expiré. Demandez-en un nouveau."
SIMULTANEOUS_REQUESTS = 20
ROUNDS = 5


@pytest.fixture
def file_database(tmp_path, monkeypatch):
    """Base SQLite fichier + session par requête, substituées à celles de conftest
    le temps du test (le dictionnaire d'overrides est restauré ensuite)."""
    engine = create_engine(
        f"sqlite:///{tmp_path / 'token_race.db'}",
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


def _seed(engine, email: str, purpose: TokenPurpose) -> tuple[int, str]:
    """Crée un compte non vérifié et un jeton valide de cet usage.
    Renvoie (user_id, jeton EN CLAIR)."""
    plain = generate_url_token()
    with Session(engine) as session:
        user = User(
            email=email,
            hashed_password=hash_password("ancien-mot-de-passe"),
            is_verified=False,
        )
        session.add(user)
        session.flush()
        session.add(
            SecurityToken(
                token_hash=hash_token(plain),
                purpose=purpose,
                user_id=user.id,
                expires_at=utcnow() + timedelta(hours=1),
            )
        )
        session.commit()
        return user.id, plain


def _fire_simultaneously(requests_: list[tuple[str, dict]]) -> list:
    """Lance toutes les requêtes EN MÊME TEMPS (barrière). Renvoie pour chacune
    (code, corps JSON) ; une exception non gérée (= un 500) devient un texte."""
    barrier = threading.Barrier(len(requests_))

    def go(item):
        path, body = item
        client = TestClient(app)  # lève les exceptions non gérées
        barrier.wait()
        try:
            response = client.post(path, json=body)
            return response.status_code, response.json()
        except Exception as exc:  # noqa: BLE001 — c'est précisément ce qu'on compte
            return f"exception {type(exc).__name__}", None

    with ThreadPoolExecutor(len(requests_)) as pool:
        return list(pool.map(go, requests_))


def test_simultaneous_password_resets_with_the_same_token_give_one_200(file_database):
    """20 réinitialisations simultanées avec le MÊME jeton, chacune avec son propre
    nouveau mot de passe : exactement une 200, les 19 autres en 400 au corps
    identique à celui d'un jeton déjà consommé ; et seul le mot de passe du gagnant
    est en base. Répété 5 fois : la course ne doit pas dépendre d'un tirage chanceux.
    """
    for round_number in range(1, ROUNDS + 1):
        user_id, plain = _seed(
            file_database, f"reset{round_number}@example.com", TokenPurpose.PASSWORD_RESET
        )
        passwords = [f"nouveau-mdp-{round_number}-{i:02d}" for i in range(SIMULTANEOUS_REQUESTS)]

        results = _fire_simultaneously(
            [("/auth/reset-password", {"token": plain, "new_password": p}) for p in passwords]
        )

        codes = Counter(str(code) for code, _ in results)
        assert codes == {"200": 1, "400": SIMULTANEOUS_REQUESTS - 1}, (
            f"manche {round_number} : {dict(codes)}"
        )
        bodies_400 = {str(body) for code, body in results if code == 400}
        assert bodies_400 == {str({"detail": INVALID_LINK_DETAIL})}

        winner = next(i for i, (code, _) in enumerate(results) if code == 200)
        with Session(file_database) as session:
            user = session.get(User, user_id)
            assert user.is_verified is True
            # Un seul bcrypt : si une perdante avait écrit après la gagnante, le mot
            # de passe de la gagnante ne serait plus celui de la base.
            assert verify_password(passwords[winner], user.hashed_password), (
                f"manche {round_number} : le mot de passe en base n'est pas celui "
                f"de la requête gagnante ({passwords[winner]})"
            )
            assert not verify_password("ancien-mot-de-passe", user.hashed_password)
            token = session.scalar(
                select(SecurityToken).where(SecurityToken.token_hash == hash_token(plain))
            )
            assert token.consumed_at is not None


def test_simultaneous_email_verifications_with_the_same_token_give_one_200(file_database):
    """40 vérifications d'email simultanées avec le MÊME jeton : exactement une 200,
    les autres en 400 au corps identique à celui d'un jeton déjà consommé."""
    count = 40
    for round_number in range(1, ROUNDS + 1):
        user_id, plain = _seed(
            file_database, f"verify{round_number}@example.com", TokenPurpose.EMAIL_VERIFICATION
        )

        results = _fire_simultaneously(
            [("/auth/verify-email", {"token": plain}) for _ in range(count)]
        )

        codes = Counter(str(code) for code, _ in results)
        assert codes == {"200": 1, "400": count - 1}, f"manche {round_number} : {dict(codes)}"
        bodies_400 = {str(body) for code, body in results if code == 400}
        assert bodies_400 == {str({"detail": INVALID_LINK_DETAIL})}
        with Session(file_database) as session:
            assert session.get(User, user_id).is_verified is True
