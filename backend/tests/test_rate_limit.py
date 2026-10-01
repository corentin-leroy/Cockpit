"""Compteur à fenêtre glissante (app/rate_limit.py) : seuils, glissement, purge, plafond.

Tout se teste avec une HORLOGE INJECTABLE : aucune attente réelle. Les seuils sont
écrits EN DUR ici (ils fixent le contrat voulu), pas relus depuis limits.py.
"""

import logging
import threading

import pytest

from app.rate_limit import RateLimiters, SlidingWindowCounter, limiters


@pytest.fixture
def make_counter(clock):
    """Fabrique un compteur branché sur l'horloge factice ; renvoie (compteur, horloge)."""

    def _make(limit=3, window=60.0, max_keys=100, enabled=True):
        counter = SlidingWindowCounter(
            "test", limit, window, max_keys, clock=clock, enabled=lambda: enabled
        )
        return counter, clock

    return _make


# ---------------------------------------------------------------------------
# Seuil : atteint puis dépassé
# ---------------------------------------------------------------------------


def test_allows_up_to_the_limit_then_refuses(make_counter):
    counter, _ = make_counter(limit=3)

    assert [counter.hit("k") for _ in range(3)] == [None, None, None]
    assert counter.hit("k") is not None
    assert counter.hit("k") is not None


def test_retry_after_is_the_time_until_the_oldest_attempt_leaves_the_window(make_counter):
    counter, clock = make_counter(limit=3, window=60)
    for _ in range(3):  # à t = 0, 10, 20
        counter.hit("k")
        clock.advance(10)
    # t = 30 : la plus ancienne (t = 0) sort à t = 60.
    assert counter.hit("k") == pytest.approx(30)
    clock.advance(20)  # t = 50
    assert counter.hit("k") == pytest.approx(10)


def test_the_window_slides_one_attempt_at_a_time(make_counter):
    counter, clock = make_counter(limit=3, window=60)
    counter.hit("k")  # t = 0
    clock.advance(10)
    counter.hit("k")  # t = 10
    clock.advance(10)
    counter.hit("k")  # t = 20
    clock.advance(30)  # t = 50 : plein
    assert counter.hit("k") is not None

    clock.advance(10)  # t = 60 : la tentative de t = 0 vient de sortir (bord INCLUS)
    assert counter.hit("k") is None  # une place libérée...
    assert counter.hit("k") is not None  # ...une seule
    clock.advance(10)  # t = 70 : celle de t = 10 sort à son tour
    assert counter.hit("k") is None


def test_refused_attempts_are_not_recorded(make_counter):
    """Marteler une clé déjà bloquée ne prolonge pas le blocage."""
    counter, clock = make_counter(limit=2, window=60)
    counter.hit("k")
    counter.hit("k")  # t = 0, plein
    clock.advance(30)
    for _ in range(100):
        assert counter.hit("k") is not None
    clock.advance(30)  # t = 60 : les deux tentatives d'origine sont sorties
    assert counter.hit("k") is None


def test_keys_are_independent(make_counter):
    counter, _ = make_counter(limit=1)
    assert counter.hit("a") is None
    assert counter.hit("a") is not None
    assert counter.hit("b") is None


def test_clear_resets_one_key_only(make_counter):
    counter, _ = make_counter(limit=1)
    counter.hit("a")
    counter.hit("b")
    counter.clear("a")
    assert counter.hit("a") is None
    assert counter.hit("b") is not None
    counter.clear("inconnue")  # sans effet, sans erreur


def test_reset_forgets_everything(make_counter):
    counter, _ = make_counter(limit=1)
    counter.hit("a")
    counter.reset()
    assert len(counter) == 0
    assert counter.hit("a") is None


def test_disabled_counter_never_refuses_and_stores_nothing(make_counter):
    counter, _ = make_counter(limit=1, enabled=False)
    assert all(counter.hit("k") is None for _ in range(50))
    assert len(counter) == 0


# ---------------------------------------------------------------------------
# Mémoire bornée : purge des entrées expirées et plafond de clés
# ---------------------------------------------------------------------------


def test_expired_keys_are_purged(make_counter):
    counter, clock = make_counter(limit=3, window=60, max_keys=10_000)
    for i in range(500):
        counter.hit(f"k{i}")
    assert len(counter) == 500

    clock.advance(61)
    counter.hit("nouvelle")  # n'importe quel appel déclenche la purge

    assert len(counter) == 1


def test_purge_removes_only_the_expired_prefix(make_counter):
    counter, clock = make_counter(limit=3, window=60)
    counter.hit("vieille")  # t = 0
    clock.advance(40)
    counter.hit("recente")  # t = 40
    clock.advance(30)  # t = 70 : « vieille » a expiré, « recente » (30 s) non
    counter.hit("autre")

    assert len(counter) == 2
    assert counter.hit("recente") is None  # toujours suivie : 2e tentative sur 3
    assert counter.hit("recente") is None  # 3e
    assert counter.hit("recente") is not None  # 4e : refusée, elle n'avait pas été oubliée


def test_the_cap_bounds_the_number_of_keys_and_forgets_the_least_recent(make_counter):
    counter, clock = make_counter(limit=1, window=3600, max_keys=100)
    for i in range(150):
        assert counter.hit(f"k{i}") is None  # une NOUVELLE clé n'est jamais refusée
        clock.advance(1)

    assert len(counter) == 100
    # La plus ancienne a été oubliée : son quota est de nouveau intact.
    assert counter.hit("k0") is None
    # La plus récente est toujours suivie.
    assert counter.hit("k149") is not None


def test_a_flood_of_distinct_keys_never_grows_memory_past_the_cap(make_counter):
    counter, clock = make_counter(limit=60, window=3600, max_keys=10_000)
    for i in range(50_000):
        counter.hit(f"cle-{i}")
        if i % 100 == 0:
            clock.advance(1)
    assert len(counter) == 10_000


def test_per_key_storage_never_exceeds_the_limit(make_counter):
    counter, _ = make_counter(limit=60, window=3600)
    for _ in range(1_000):
        for key in ("a", "b", "c"):
            counter.hit(key)
    assert all(len(stamps) <= 60 for stamps in counter._entries.values())


def test_eviction_is_logged_but_throttled(make_counter, caplog):
    counter, clock = make_counter(limit=1, window=3600, max_keys=10)
    with caplog.at_level(logging.WARNING, logger="app.rate_limit"):
        for i in range(500):
            counter.hit(f"k{i}")
    records = [r for r in caplog.records if "plafond" in r.getMessage().lower()]
    assert 1 <= len(records) <= 2  # pas 490 lignes de journal


# ---------------------------------------------------------------------------
# Atomicité : des requêtes simultanées ne dépassent jamais le seuil
# ---------------------------------------------------------------------------


def test_simultaneous_hits_never_exceed_the_limit(make_counter):
    counter, _ = make_counter(limit=50, window=60)
    barrier = threading.Barrier(200)
    results = []

    def go():
        barrier.wait()
        results.append(counter.hit("k"))

    threads = [threading.Thread(target=go) for _ in range(200)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert results.count(None) == 50
    assert len(results) == 200


# ---------------------------------------------------------------------------
# Les quatre règles de l'application : seuils voulus, horloge injectable
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "attribute,limit,window",
    [
        ("login_ip", 60, 60),  # 60 tentatives par minute et par IP
        ("login_pair", 5, 15 * 60),  # 5 échecs par quart d'heure et par (IP, email)
        ("register_ip", 20, 3600),  # 20 inscriptions par heure et par IP
        ("forgot_ip", 10, 3600),  # 10 demandes par heure et par IP
    ],
)
def test_application_rules_use_the_decided_thresholds(clock, attribute, limit, window):
    counter = getattr(limiters, attribute)

    assert [counter.hit("k") for _ in range(limit)] == [None] * limit
    assert counter.hit("k") == pytest.approx(window)
    clock.advance(window - 1)
    assert counter.hit("k") is not None
    clock.advance(1)
    assert counter.hit("k") is None


def test_registry_clock_and_enabled_switch_reach_every_counter(clock):
    registry = RateLimiters()
    registry.clock = clock
    assert registry.register_ip.hit("k") is None
    registry.enabled = False
    assert all(registry.login_ip.hit("k") is None for _ in range(200))
