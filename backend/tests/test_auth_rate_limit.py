"""Limites de débit sur la connexion, l'inscription et le mot de passe oublié.

Seuils décidés (écrits EN DUR ici) :
- connexion : 60 tentatives par minute et par IP, toutes tentatives confondues ;
- connexion : 5 ÉCHECS par quart d'heure et par COUPLE (IP, email) ; une connexion
  réussie remet ce compteur à zéro ;
- inscription : 20 par heure et par IP ;
- mot de passe oublié : 10 par heure et par IP, EN PLUS du plafond silencieux de
  3 envois par heure et par compte (inchangé).

Les fenêtres se testent avec une horloge injectable (fixture `clock`). Le coût de bcrypt
est neutralisé par un faux hachage COMPTEUR (fixture `fake_bcrypt`) : cela permet 60
requêtes en quelques millisecondes ET de prouver que la limite est vérifiée AVANT le
calcul (le compteur n'augmente plus une fois la limite atteinte). Le vrai bcrypt est
exercé par le test de rafale, en fin de fichier.
"""

import ipaddress
import threading
from collections import Counter
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker

from app import client_ip
from app.database import Base, get_db
from app.main import app
from app.models import SecurityToken, TokenPurpose, User
from app.routers import auth
from app.security import hash_password

LOGIN_429 = (
    "Trop de tentatives de connexion. Patientez quelques minutes avant de réessayer, "
    "ou utilisez « Mot de passe oublié »."
)
REGISTER_429 = "Trop d'inscriptions depuis cette connexion. Réessayez plus tard."
FORGOT_429 = "Trop de demandes de réinitialisation depuis cette connexion. Réessayez plus tard."
FORGOT_OK = "Si un compte existe avec cette adresse, un email vient d'être envoyé."

PASSWORD = "motdepasse-correct"


@pytest.fixture
def fake_bcrypt(monkeypatch):
    """Hachage factice et COMPTEUR : « fake:<mot de passe> ». Les appels à
    verify_password / hash_password de l'endpoint sont comptés."""
    calls = Counter()

    def fake_hash(plain):
        calls["hash"] += 1
        return f"fake:{plain}"

    def fake_verify(plain, hashed):
        calls["verify"] += 1
        return hashed == f"fake:{plain}"

    monkeypatch.setattr(auth, "hash_password", fake_hash)
    monkeypatch.setattr(auth, "verify_password", fake_verify)
    return calls


def seed_account(db_session, email="victime@example.com", password=PASSWORD, real=False):
    hashed = hash_password(password) if real else f"fake:{password}"
    db_session.add(User(email=email, hashed_password=hashed))
    db_session.commit()


def client_from(ip: str) -> TestClient:
    """Client de test dont l'adresse TCP (l'IP vue par l'application) est `ip`."""
    return TestClient(app, client=(ip, 5000))


def login(client, email, password="faux-mot-de-passe"):
    return client.post("/auth/login", json={"email": email, "password": password})


def assert_retry_after(response, expected_max):
    value = response.headers["retry-after"]
    assert value.isdigit(), value
    assert 1 <= int(value) <= expected_max


# ---------------------------------------------------------------------------
# Connexion : 60 tentatives par minute et par IP
# ---------------------------------------------------------------------------


def test_login_is_limited_to_60_attempts_per_minute_per_ip(client, clock, fake_bcrypt):
    for i in range(60):  # des emails tous différents : seul le seuil par IP s'applique
        assert login(client, f"inconnu{i}@example.com").status_code == 401
    assert fake_bcrypt["verify"] == 60

    refused = login(client, "inconnu60@example.com")

    assert refused.status_code == 429
    assert refused.json() == {"detail": LOGIN_429}
    assert_retry_after(refused, 60)
    assert fake_bcrypt["verify"] == 60  # refusée AVANT le calcul de hachage


def test_every_attempt_counts_for_the_ip_even_a_malformed_one(client, clock, fake_bcrypt):
    for _ in range(60):
        assert client.post("/auth/login", json={"email": "pas-un-email"}).status_code == 422

    assert login(client, "x@example.com").status_code == 429


def test_the_ip_limit_slides_with_the_clock(client, clock, fake_bcrypt):
    for i in range(60):
        login(client, f"inconnu{i}@example.com")
        clock.advance(0.5)  # 30 s en tout
    assert login(client, "a@example.com").status_code == 429

    clock.advance(30)  # t = 60 : la 1re tentative (t = 0) sort de la fenêtre
    assert login(client, "b@example.com").status_code == 401
    assert login(client, "c@example.com").status_code == 429  # une seule place libérée


def test_the_ip_limit_is_per_ip(client, clock, fake_bcrypt):
    for i in range(60):
        login(client, f"inconnu{i}@example.com")
    assert login(client, "a@example.com").status_code == 429

    other = client_from("203.0.113.9")
    assert login(other, "a@example.com").status_code == 401


# ---------------------------------------------------------------------------
# Connexion : 5 échecs par quart d'heure et par couple (IP, email)
# ---------------------------------------------------------------------------


def test_five_failures_block_the_sixth_attempt_even_with_the_right_password(
    client, clock, fake_bcrypt, db_session
):
    seed_account(db_session)
    for _ in range(5):
        assert login(client, "victime@example.com").status_code == 401
    assert fake_bcrypt["verify"] == 5

    blocked = login(client, "victime@example.com", PASSWORD)  # le BON mot de passe

    assert blocked.status_code == 429
    assert blocked.json() == {"detail": LOGIN_429}
    assert_retry_after(blocked, 15 * 60)
    assert fake_bcrypt["verify"] == 5  # pas de bcrypt pour la 6e : vérifié AVANT


def test_the_block_lifts_after_a_quarter_of_an_hour(client, clock, fake_bcrypt, db_session):
    seed_account(db_session)
    for _ in range(5):
        login(client, "victime@example.com")
    assert login(client, "victime@example.com", PASSWORD).status_code == 429

    clock.advance(15 * 60 - 1)
    assert login(client, "victime@example.com", PASSWORD).status_code == 429
    clock.advance(1)
    assert login(client, "victime@example.com", PASSWORD).status_code == 200


def test_retry_after_counts_down(client, clock, fake_bcrypt, db_session):
    seed_account(db_session)
    for _ in range(5):
        login(client, "victime@example.com")
    first = int(login(client, "victime@example.com").headers["retry-after"])
    clock.advance(300)
    second = int(login(client, "victime@example.com").headers["retry-after"])

    assert first == 900
    assert second == 600


def test_blocked_attempts_do_not_extend_the_block(client, clock, fake_bcrypt, db_session):
    seed_account(db_session)
    for _ in range(5):
        login(client, "victime@example.com")
    for _ in range(40):
        assert login(client, "victime@example.com").status_code == 429
    clock.advance(15 * 60)
    assert login(client, "victime@example.com", PASSWORD).status_code == 200


def test_a_successful_login_resets_the_failure_counter(client, clock, fake_bcrypt, db_session):
    seed_account(db_session)
    for _ in range(4):
        assert login(client, "victime@example.com").status_code == 401
    assert login(client, "victime@example.com", PASSWORD).status_code == 200

    # Compteur remis à zéro : 5 nouveaux échecs sont permis, le 6e est refusé.
    for _ in range(5):
        assert login(client, "victime@example.com").status_code == 401
    assert login(client, "victime@example.com").status_code == 429


def test_successes_never_count_towards_the_failure_limit(client, clock, fake_bcrypt, db_session):
    seed_account(db_session)
    for _ in range(20):
        assert login(client, "victime@example.com", PASSWORD).status_code == 200
    for _ in range(5):
        assert login(client, "victime@example.com").status_code == 401  # toujours 5 permis


def test_failures_on_one_email_do_not_block_another_email_from_the_same_ip(
    client, clock, fake_bcrypt, db_session
):
    seed_account(db_session, "victime@example.com")
    seed_account(db_session, "autre@example.com")
    for _ in range(5):
        login(client, "victime@example.com")
    assert login(client, "victime@example.com").status_code == 429

    assert login(client, "autre@example.com", PASSWORD).status_code == 200


def test_nobody_can_lock_another_users_account_by_failing_on_it(
    client, clock, fake_bcrypt, db_session
):
    """Le couple (IP, email) : l'attaquant épuise SON compteur, pas celui de la victime
    qui se connecte depuis une autre adresse."""
    seed_account(db_session)
    attacker = client_from("203.0.113.66")
    for _ in range(5):
        assert login(attacker, "victime@example.com").status_code == 401
    assert login(attacker, "victime@example.com").status_code == 429

    victim = client_from("198.51.100.20")
    assert login(victim, "victime@example.com", PASSWORD).status_code == 200


def test_email_case_cannot_dodge_the_pair_counter(client, clock, fake_bcrypt, db_session):
    seed_account(db_session)
    for email in ["victime@example.com", "VICTIME@example.com", "Victime@Example.COM",
                  " victime@example.com ", "victime@EXAMPLE.com"]:
        assert login(client, email).status_code == 401
    assert login(client, "ViCtImE@example.com", PASSWORD).status_code == 429


# ---------------------------------------------------------------------------
# Anti-énumération : chaque 429 est identique, que le compte existe ou non
# ---------------------------------------------------------------------------


def test_login_429_is_identical_whether_the_account_exists(client, clock, fake_bcrypt, db_session):
    seed_account(db_session, "existe@example.com")
    outcomes = {}
    for label, email in (("existant", "existe@example.com"), ("inconnu", "inconnu@example.com")):
        statuses = [login(client, email).status_code for _ in range(5)]
        blocked = login(client, email)
        outcomes[label] = (
            statuses,
            blocked.status_code,
            blocked.text,
            blocked.headers["retry-after"],
        )

    assert outcomes["existant"] == outcomes["inconnu"]
    assert outcomes["existant"][0] == [401] * 5
    assert outcomes["existant"][1] == 429


def test_the_401_stays_identical_before_the_limit(client, clock, fake_bcrypt, db_session):
    seed_account(db_session, "existe@example.com")
    a = login(client, "existe@example.com")
    b = login(client, "inconnu@example.com")
    assert (a.status_code, a.text, dict(a.headers)) == (b.status_code, b.text, dict(b.headers))


# ---------------------------------------------------------------------------
# Inscription : 20 par heure et par IP
# ---------------------------------------------------------------------------


def register(client, email, password="password123"):
    return client.post("/auth/register", json={"email": email, "password": password})


def test_registration_is_limited_to_20_per_hour_per_ip(client, clock, fake_bcrypt):
    for i in range(20):
        assert register(client, f"nouveau{i}@example.com").status_code == 201
    assert fake_bcrypt["hash"] == 20

    refused = register(client, "nouveau20@example.com")

    assert refused.status_code == 429
    assert refused.json() == {"detail": REGISTER_429}
    assert_retry_after(refused, 3600)
    assert fake_bcrypt["hash"] == 20  # aucun hachage pour la requête refusée


def test_every_registration_attempt_counts_duplicates_and_invalid_ones_too(
    client, clock, fake_bcrypt
):
    assert register(client, "doublon@example.com").status_code == 201
    for _ in range(10):
        assert register(client, "doublon@example.com").status_code == 409
    for _ in range(9):
        assert client.post("/auth/register", json={"email": "x"}).status_code == 422

    assert register(client, "encore@example.com").status_code == 429


def test_the_registration_limit_slides_and_is_per_ip(client, clock, fake_bcrypt):
    for i in range(20):
        register(client, f"nouveau{i}@example.com")
    assert register(client, "a@example.com").status_code == 429
    assert register(client_from("203.0.113.9"), "a@example.com").status_code == 201

    clock.advance(3600)
    assert register(client, "b@example.com").status_code == 201


# ---------------------------------------------------------------------------
# Mot de passe oublié : 10 par heure et par IP, EN PLUS du plafond par compte
# ---------------------------------------------------------------------------


def forgot(client, email):
    return client.post("/auth/forgot-password", json={"email": email})


def test_forgot_password_is_limited_to_10_per_hour_per_ip(client, clock, fake_bcrypt):
    for i in range(10):
        response = forgot(client, f"quelquun{i}@example.com")
        assert response.status_code == 200
        assert response.json() == {"message": FORGOT_OK}

    refused = forgot(client, "quelquun10@example.com")

    assert refused.status_code == 429
    assert refused.json() == {"detail": FORGOT_429}
    assert_retry_after(refused, 3600)


def test_forgot_password_429_is_identical_whether_the_account_exists(
    client, clock, fake_bcrypt, db_session
):
    seed_account(db_session, "existe@example.com")
    for i in range(10):
        forgot(client, f"quelquun{i}@example.com")

    existing = forgot(client, "existe@example.com")
    unknown = forgot(client, "inconnu@example.com")

    assert (existing.status_code, existing.text, existing.headers["retry-after"]) == (
        unknown.status_code,
        unknown.text,
        unknown.headers["retry-after"],
    )
    assert existing.status_code == 429


def test_the_per_account_cap_stays_silent_and_unchanged(client, clock, fake_bcrypt, db_session):
    """Le plafond de 3 envois par heure et par compte n'a pas bougé : au-delà, la
    réponse reste le même 200 neutre (pas de 429, qui trahirait le compte) et aucun
    4e jeton n'est émis. Il s'ajoute au seuil par IP, il ne le remplace pas."""
    seed_account(db_session, "existe@example.com")
    responses = [forgot(client, "existe@example.com") for _ in range(6)]

    assert {r.status_code for r in responses} == {200}
    assert {r.text for r in responses} == {responses[0].text}
    db_session.expire_all()
    user_id = db_session.scalar(select(User.id).where(User.email == "existe@example.com"))
    tokens = db_session.scalar(
        select(func.count()).select_from(SecurityToken).where(
            SecurityToken.user_id == user_id,
            SecurityToken.purpose == TokenPurpose.PASSWORD_RESET,
        )
    )
    assert tokens == 3


def test_forgot_password_ip_limit_slides_and_is_per_ip(client, clock, fake_bcrypt):
    for i in range(10):
        forgot(client, f"quelquun{i}@example.com")
    assert forgot(client, "a@example.com").status_code == 429
    assert forgot(client_from("203.0.113.9"), "a@example.com").status_code == 200

    clock.advance(3600)
    assert forgot(client, "b@example.com").status_code == 200


# ---------------------------------------------------------------------------
# Lecture de l'IP derrière le proxy : le compteur suit le VRAI client
# ---------------------------------------------------------------------------


@pytest.fixture
def behind_railway(monkeypatch):
    monkeypatch.setattr(
        client_ip,
        "settings",
        client_ip.ProxySettings(2, (ipaddress.ip_network("100.64.0.0/10"),)),
    )
    return TestClient(app, client=("100.64.0.2", 5000))  # adresse du dernier proxy


def forwarded(real_client, forged=""):
    return {"X-Forwarded-For": f"{forged}{real_client}, 152.233.56.194"}


def test_behind_the_proxy_each_real_client_has_its_own_counter(
    client, behind_railway, clock, fake_bcrypt
):
    for i in range(60):
        r = behind_railway.post(
            "/auth/login", json={"email": f"u{i}@example.com", "password": "x"},
            headers=forwarded("198.51.100.7"),
        )
        assert r.status_code == 401
    blocked = behind_railway.post(
        "/auth/login", json={"email": "u@example.com", "password": "x"},
        headers=forwarded("198.51.100.7"),
    )
    other = behind_railway.post(
        "/auth/login", json={"email": "u@example.com", "password": "x"},
        headers=forwarded("198.51.100.8"),
    )

    assert blocked.status_code == 429
    assert other.status_code == 401  # un autre client derrière le MÊME proxy n'est pas gêné


def test_a_forged_forwarded_for_cannot_dodge_the_limit(client, behind_railway, clock, fake_bcrypt):
    """Chaque requête présente une valeur de gauche différente (falsifiée) : le
    compteur suit toujours le vrai client, lu depuis la droite."""
    for i in range(60):
        behind_railway.post(
            "/auth/login", json={"email": f"u{i}@example.com", "password": "x"},
            headers=forwarded("198.51.100.7", forged=f"10.0.{i}.1, "),
        )
    blocked = behind_railway.post(
        "/auth/login", json={"email": "z@example.com", "password": "x"},
        headers=forwarded("198.51.100.7", forged="1.2.3.4, "),
    )
    assert blocked.status_code == 429


def test_without_trusted_proxies_the_header_is_not_a_way_around_the_limit(
    client, clock, fake_bcrypt
):
    """Réglage par défaut : même avec un X-Forwarded-For différent à chaque requête,
    tout compte sur l'adresse TCP."""
    for i in range(60):
        client.post(
            "/auth/login", json={"email": f"u{i}@example.com", "password": "x"},
            headers={"X-Forwarded-For": f"10.9.{i}.1, 152.233.56.194"},
        )
    blocked = client.post(
        "/auth/login", json={"email": "z@example.com", "password": "x"},
        headers={"X-Forwarded-For": "10.9.99.1, 152.233.56.194"},
    )
    assert blocked.status_code == 429


# ---------------------------------------------------------------------------
# Gardes : la limite est bien branchée, les messages sont propres
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "path,dependency_name",
    [
        ("/auth/login", "limit_login_per_ip"),
        ("/auth/register", "limit_register_per_ip"),
        ("/auth/forgot-password", "limit_forgot_password_per_ip"),
    ],
)
def test_the_limit_dependency_is_attached_to_the_route(path, dependency_name):
    """Retirer la dépendance d'une route la laisserait sans protection, en silence :
    aucun autre test ne le verrait avant d'avoir envoyé des dizaines de requêtes."""
    routes = [r for r in app.routes if getattr(r, "path", None) == path and "POST" in r.methods]
    assert len(routes) == 1
    names = [d.call.__name__ for d in routes[0].dependant.dependencies]
    assert dependency_name in names


def test_rate_limit_messages_are_clean_french():
    from app import error_messages

    for message in (
        error_messages.RATE_LIMITED_LOGIN_DETAIL,
        error_messages.RATE_LIMITED_REGISTER_DETAIL,
        error_messages.RATE_LIMITED_FORGOT_PASSWORD_DETAIL,
    ):
        assert message and message[0].isupper() and message.endswith(".")
        for technical in ("429", "rate", "limit", "IP", "Retry", "requête"):
            assert technical not in message
    assert "Mot de passe oublié" in error_messages.RATE_LIMITED_LOGIN_DETAIL


# ---------------------------------------------------------------------------
# Rafale simultanée : le seuil tient, et bcrypt n'est payé que par les admises
# ---------------------------------------------------------------------------


@pytest.fixture
def file_database(tmp_path, monkeypatch):
    """Base SQLite fichier (une connexion par requête) : seule une vraie concurrence
    révèle une réservation non atomique. Même montage que test_registration_race.py."""
    engine = create_engine(
        f"sqlite:///{tmp_path / 'burst.db'}",
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


def test_a_simultaneous_burst_on_one_pair_pays_bcrypt_only_five_times(file_database, monkeypatch):
    """20 mauvais mots de passe EN MÊME TEMPS sur le même couple (IP, email) : exactement
    5 passent le contrôle (donc 5 calculs bcrypt RÉELS), 15 reçoivent un 429. Avec un
    contrôle séparé de l'enregistrement de l'échec, les 15 premières requêtes (taille
    du pool) passeraient toutes avant qu'aucun échec ne soit compté."""
    with Session(file_database) as session:
        session.add(User(email="victime@example.com", hashed_password=hash_password(PASSWORD)))
        session.commit()
    real_verify = auth.verify_password
    verify_calls = Counter()

    def counting_verify(plain, hashed):
        verify_calls["n"] += 1
        return real_verify(plain, hashed)

    monkeypatch.setattr(auth, "verify_password", counting_verify)
    barrier = threading.Barrier(20)

    def attempt(_):
        http = TestClient(app)  # lève les exceptions non gérées
        barrier.wait()
        return http.post(
            "/auth/login", json={"email": "victime@example.com", "password": "faux-mot-de-passe"}
        ).status_code

    with ThreadPoolExecutor(20) as pool:
        codes = list(pool.map(attempt, range(20)))

    assert Counter(codes) == {401: 5, 429: 15}
    assert verify_calls["n"] == 5
