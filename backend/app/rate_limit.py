"""Limites de débit sur la connexion, l'inscription et le mot de passe oublié.

MENACES : deviner un mot de passe par essais répétés ; tester en masse des identifiants
volés ailleurs ; créer des comptes en masse (chaque inscription fait envoyer un email par
Brevo, sur le quota) ; saturer le serveur (chaque connexion coûte ~0,2 s de bcrypt et une
connexion du pool : environ 15 requêtes simultanées le saturent). La limite est donc
toujours vérifiée AVANT le calcul bcrypt, sinon elle ne protège pas le serveur.

STOCKAGE EN MÉMOIRE, sans dépendance (décision). ⚠ HYPOTHÈSE D'INSTANCE UNIQUE : le
backend tourne en UN SEUL processus sur Railway (railway.json ne passe pas `--workers`,
et le nombre de réplicas du service doit rester à 1). Un compteur en mémoire voit alors
toutes les requêtes. Conséquences acceptées : un redémarrage remet les compteurs à zéro ;
pendant un déploiement l'ancienne et la nouvelle instance coexistent brièvement avec des
compteurs séparés. Passer à plusieurs processus ou réplicas diviserait la protection
(chaque instance compterait de son côté : les seuils seraient multipliés par leur
nombre) : il faudrait alors des compteurs PARTAGÉS (Redis avec expiration, ou une table
PostgreSQL), en gardant l'interface de SlidingWindowCounter.

FENÊTRE GLISSANTE. Par clé, la liste des horodatages des tentatives dans la fenêtre
(jamais plus de `limite` : une tentative refusée n'est pas enregistrée, donc marteler une
clé bloquée ne prolonge pas le blocage).

ATOMICITÉ. `hit` vérifie ET enregistre sous un verrou : des requêtes simultanées ne
passent pas toutes le contrôle avant qu'aucune ne soit comptée (même famille de défaut
que la consommation concurrente des jetons). Pour le couple (IP, email), la tentative est
RÉSERVÉE avant bcrypt puis effacée si la connexion réussit : seuls les échecs restent.

MÉMOIRE BORNÉE. Les clés sont gardées dans l'ordre de leur dernière tentative ENREGISTRÉE.
Les clés expirées forment donc toujours un préfixe : la purge dépile par l'avant à chaque
appel (coût amorti constant, ni balayage complet ni thread). Au-delà de
RATE_LIMIT_MAX_TRACKED_KEYS clés encore vivantes, la moins récemment active est OUBLIÉE
pour admettre la nouvelle : jamais de refus d'une nouvelle clé, qui permettrait de bloquer
tout le monde en remplissant la table. Le coût est de rendre son quota à la clé oubliée ;
un attaquant d'une seule IP ne peut créer que 60 clés par minute (le seuil de connexion),
seul un réseau d'adresses distinctes en profiterait, et il contourne déjà les seuils par IP.
"""

import logging
import math
import threading
import time
from collections import OrderedDict, deque
from typing import Callable

from fastapi import HTTPException, Request, status

from app import error_messages
from app.client_ip import get_client_ip
from app.limits import (
    FORGOT_PASSWORD_IP_WINDOW_SECONDS,
    FORGOT_PASSWORD_MAX_PER_IP,
    LOGIN_IP_WINDOW_SECONDS,
    LOGIN_MAX_ATTEMPTS_PER_IP,
    LOGIN_MAX_FAILURES_PER_PAIR,
    LOGIN_PAIR_WINDOW_SECONDS,
    RATE_LIMIT_MAX_TRACKED_KEYS,
    REGISTER_IP_WINDOW_SECONDS,
    REGISTER_MAX_PER_IP,
)

logger = logging.getLogger("app.rate_limit")

_EVICTION_WARNING_INTERVAL_SECONDS = 300.0


class SlidingWindowCounter:
    """Une règle de limitation : au plus `limit` tentatives par clé et par fenêtre."""

    def __init__(
        self,
        name: str,
        limit: int,
        window_seconds: float,
        max_keys: int,
        clock: Callable[[], float] = time.monotonic,
        enabled: Callable[[], bool] = lambda: True,
    ):
        self.name = name
        self._limit = limit
        self._window = window_seconds
        self._max_keys = max_keys
        self._clock = clock
        self._enabled = enabled
        # clé -> horodatages dans la fenêtre ; ordre = dernière tentative ENREGISTRÉE.
        self._entries: OrderedDict[str, deque[float]] = OrderedDict()
        self._lock = threading.Lock()
        self._last_eviction_warning: float | None = None

    def hit(self, key: str) -> float | None:
        """Enregistre une tentative. Renvoie None si elle est admise ; sinon le nombre de
        secondes à attendre (la plus ancienne tentative comptée sort alors de la
        fenêtre), et RIEN n'est enregistré."""
        if not self._enabled():
            return None
        now = self._clock()
        with self._lock:
            self._purge_expired(now)
            stamps = self._entries.get(key)
            if stamps is not None:
                horizon = now - self._window
                while stamps and stamps[0] <= horizon:
                    stamps.popleft()
                if not stamps:
                    del self._entries[key]
                    stamps = None
            if stamps is not None and len(stamps) >= self._limit:
                return stamps[0] + self._window - now
            if stamps is None:
                self._make_room(now)
                stamps = self._entries[key] = deque()
            stamps.append(now)
            self._entries.move_to_end(key)
            return None

    def clear(self, key: str) -> None:
        """Oublie une clé (connexion réussie : le compteur d'échecs repart de zéro)."""
        with self._lock:
            self._entries.pop(key, None)

    def reset(self) -> None:
        with self._lock:
            self._entries.clear()
            self._last_eviction_warning = None

    def __len__(self) -> int:
        return len(self._entries)

    def _purge_expired(self, now: float) -> None:
        """Retire les clés dont la dernière tentative est sortie de la fenêtre : elles
        sont en tête de l'ordre, on s'arrête à la première encore vivante."""
        horizon = now - self._window
        while self._entries:
            oldest_key = next(iter(self._entries))
            stamps = self._entries[oldest_key]
            if stamps and stamps[-1] > horizon:
                break
            del self._entries[oldest_key]

    def _make_room(self, now: float) -> None:
        """Avant d'ajouter une NOUVELLE clé : oublie la moins récente si la table est
        pleine de clés encore vivantes (la purge a déjà retiré les expirées)."""
        while len(self._entries) >= self._max_keys:
            self._entries.popitem(last=False)
            last = self._last_eviction_warning
            if last is None or now - last >= _EVICTION_WARNING_INTERVAL_SECONDS:
                self._last_eviction_warning = now
                logger.warning(
                    "Limite de débit %r : plafond de %d clés suivies atteint, la clé la "
                    "moins récente est oubliée (afflux d'adresses ou d'emails distincts ?).",
                    self.name,
                    self._max_keys,
                )


class RateLimiters:
    """Les quatre règles de l'application, partageant une horloge et un interrupteur."""

    def __init__(self):
        self.clock: Callable[[], float] = time.monotonic
        self.enabled = True

        def make(name: str, limit: int, window: float) -> SlidingWindowCounter:
            # Lambdas : réassigner `self.clock` / `self.enabled` (tests) atteint les
            # quatre compteurs.
            return SlidingWindowCounter(
                name,
                limit,
                window,
                RATE_LIMIT_MAX_TRACKED_KEYS,
                clock=lambda: self.clock(),
                enabled=lambda: self.enabled,
            )

        self.login_ip = make("login_ip", LOGIN_MAX_ATTEMPTS_PER_IP, LOGIN_IP_WINDOW_SECONDS)
        self.login_pair = make("login_pair", LOGIN_MAX_FAILURES_PER_PAIR, LOGIN_PAIR_WINDOW_SECONDS)
        self.register_ip = make("register_ip", REGISTER_MAX_PER_IP, REGISTER_IP_WINDOW_SECONDS)
        self.forgot_ip = make(
            "forgot_ip", FORGOT_PASSWORD_MAX_PER_IP, FORGOT_PASSWORD_IP_WINDOW_SECONDS
        )

    def reset(self) -> None:
        """Oublie tous les compteurs et restaure l'horloge réelle (tests)."""
        for counter in (self.login_ip, self.login_pair, self.register_ip, self.forgot_ip):
            counter.reset()
        self.clock = time.monotonic
        self.enabled = True


limiters = RateLimiters()


def too_many_requests(detail: str, retry_after: float) -> HTTPException:
    """429 avec un message français du catalogue et l'en-tête Retry-After (secondes
    entières, au moins 1)."""
    return HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail=detail,
        headers={"Retry-After": str(max(1, math.ceil(retry_after)))},
    )


def _enforce(counter: SlidingWindowCounter, key: str, detail: str) -> None:
    retry_after = counter.hit(key)
    if retry_after is not None:
        raise too_many_requests(detail, retry_after)


# --- Dépendances FastAPI (seuils par IP) : exécutées avant le corps de l'endpoint, donc
# --- avant tout calcul bcrypt. Elles comptent TOUTES les tentatives, y compris celles
# --- dont le corps est invalide (422) ou refusées plus loin (409, 401).


def limit_login_per_ip(request: Request) -> None:
    _enforce(limiters.login_ip, get_client_ip(request), error_messages.RATE_LIMITED_LOGIN_DETAIL)


def limit_register_per_ip(request: Request) -> None:
    _enforce(
        limiters.register_ip, get_client_ip(request), error_messages.RATE_LIMITED_REGISTER_DETAIL
    )


def limit_forgot_password_per_ip(request: Request) -> None:
    _enforce(
        limiters.forgot_ip,
        get_client_ip(request),
        error_messages.RATE_LIMITED_FORGOT_PASSWORD_DETAIL,
    )


# --- Couple (IP, email visé) de la connexion. L'email est celui du schéma, DÉJÀ
# --- normalisé (minuscules, sans espaces) : la casse ne permet pas d'esquiver.


def _pair_key(request: Request, email: str) -> str:
    return f"{get_client_ip(request)}|{email}"


def reserve_login_attempt(request: Request, email: str) -> None:
    """Réserve une tentative AVANT le calcul bcrypt ; 429 si le couple a déjà épuisé ses
    5 échecs. Ne dépend pas de l'existence du compte : un email inconnu compte comme un
    mot de passe faux, donc le 429 est identique (anti-énumération)."""
    _enforce(limiters.login_pair, _pair_key(request, email), error_messages.RATE_LIMITED_LOGIN_DETAIL)


def clear_login_failures(request: Request, email: str) -> None:
    """Connexion réussie : remet à zéro le compteur du couple (IP, email)."""
    limiters.login_pair.clear(_pair_key(request, email))
