"""Adresse IP du client, lue derrière le proxy de Railway, pour les limites de débit.

PROBLÈME. Derrière un proxy, l'application voit l'adresse TCP du PROXY, pas celle du
client : limiter dessus ferait partager des compteurs à tous les utilisateurs. L'IP
réelle arrive dans `X-Forwarded-For`, mais un client peut y écrire ce qu'il veut : lire
naïvement la première valeur permettrait de contourner toute limite.

MESURÉ en production (journaux d'un diagnostic temporaire, retiré depuis) :
- uvicorn ne réécrit PAS l'adresse (FORWARDED_ALLOW_IPS n'est pas posée, son défaut
  est 127.0.0.1) : `request.client.host` vaut 100.64.0.x, des adresses internes de
  Railway, plusieurs différentes ;
- `X-Forwarded-For` arrive sous la forme « <client>, <saut du proxy> » ; un en-tête
  falsifié par le client (une ou deux valeurs) est écarté par Railway ;
- `X-Real-IP` porte l'IP du client (la valeur falsifiée est écrasée) ;
- `Forwarded` traverse TEL QUEL : falsifiable, donc JAMAIS lu.
Non mesuré : un client IPv6, un autre point d'entrée que bcn1, un en-tête répété sur
plusieurs lignes.

MÉTHODE. Avec N proxys de confiance (TRUSTED_PROXY_COUNT ; 2 sur Railway : le proxy
d'entrée et un proxy interne), le client est la N-ième entrée de X-Forwarded-For EN
PARTANT DE LA DROITE. Chaque proxy ajoute l'adresse de son interlocuteur ; ce que le
client a écrit se retrouve à GAUCHE et n'est jamais lu. C'est correct que le proxy
écrase l'en-tête reçu (cas mesuré) ou qu'il y ajoute : c'est pourquoi on ne lit pas la
première valeur et qu'on ne s'en remet pas non plus à X-Real-IP.

REPLIS. Toute anomalie replie sur l'adresse TCP (un compteur PARTAGÉ : cela gêne, cela
ne permet jamais de contourner) et se signale par un avertissement (limité en
fréquence) : moins d'entrées que de proxys, entrée qui n'est pas une adresse IP, ou
adresse TCP hors du réseau des proxys (accès direct à l'application, en-tête forgeable).
Seul risque résiduel : Railway retirerait un saut ET se mettrait à AJOUTER au lieu
d'écraser, ce qui ferait lire une valeur forgée sans repli ni avertissement.

⚠ Ne JAMAIS poser FORWARDED_ALLOW_IPS (ni `--forwarded-allow-ips`) : avec `*`, uvicorn
réécrirait l'adresse du client avec la PREMIÈRE valeur de X-Forwarded-For (celle de
gauche, falsifiable) et rouvrirait exactement le contournement évité ici. Ce module
suppose que `request.client` est l'adresse TCP brute.
"""

import ipaddress
import logging
import os
import time
from dataclasses import dataclass

from starlette.requests import Request

logger = logging.getLogger("app.rate_limit")

# Réseau des proxys de Railway tel qu'observé (100.64.0.2 à .4) : l'espace partagé
# 100.64.0.0/10 (RFC 6598) est DÉDUIT de la norme, seul 100.64.0.x a été observé. Hors
# de ce réseau, repli sur l'adresse TCP (journalisé) : modifiable sans redéploiement.
DEFAULT_TRUSTED_PROXY_NETWORKS = "100.64.0.0/10"
MAX_TRUSTED_PROXY_COUNT = 10
_WARNING_INTERVAL_SECONDS = 300.0


@dataclass(frozen=True)
class ProxySettings:
    """Topologie du proxy. 0 proxy de confiance (défaut) = ne JAMAIS lire
    X-Forwarded-For : seule l'adresse TCP compte (développement, tests)."""

    trusted_proxy_count: int = 0
    trusted_networks: tuple = ()


def load_proxy_settings(environ=None) -> ProxySettings:
    """Lit TRUSTED_PROXY_COUNT et TRUSTED_PROXY_NETWORKS.

    Valeur invalide → ValueError au démarrage, JAMAIS de repli silencieux sur le
    défaut : une coquille ferait croire que la limite par IP est en place alors que
    tous les utilisateurs partageraient quelques compteurs."""
    env = os.environ if environ is None else environ

    raw_count = env.get("TRUSTED_PROXY_COUNT", "").strip()
    if raw_count == "":
        count = 0
    else:
        try:
            count = int(raw_count)
        except ValueError:
            raise ValueError(
                f"TRUSTED_PROXY_COUNT doit être un entier (reçu {raw_count!r})."
            ) from None
        if not 0 <= count <= MAX_TRUSTED_PROXY_COUNT:
            raise ValueError(
                f"TRUSTED_PROXY_COUNT doit être compris entre 0 et "
                f"{MAX_TRUSTED_PROXY_COUNT} (reçu {count})."
            )

    raw_networks = env.get("TRUSTED_PROXY_NETWORKS", "").strip() or DEFAULT_TRUSTED_PROXY_NETWORKS
    networks = []
    for item in raw_networks.split(","):
        try:
            networks.append(ipaddress.ip_network(item.strip(), strict=False))
        except ValueError:
            raise ValueError(
                f"TRUSTED_PROXY_NETWORKS contient un réseau invalide : {item.strip()!r}."
            ) from None
    return ProxySettings(trusted_proxy_count=count, trusted_networks=tuple(networks))


settings = load_proxy_settings()

# Raison de l'avertissement -> dernier instant où il a été émis (limitation de débit
# des journaux : un repli systématique ne doit pas écrire une ligne par requête).
_warned_at: dict = {}


def _warn(reason: str, message: str) -> None:
    now = time.monotonic()
    last = _warned_at.get(reason)
    if last is not None and now - last < _WARNING_INTERVAL_SECONDS:
        return
    _warned_at[reason] = now
    logger.warning(
        "Lecture de l'IP du client : %s Repli sur l'adresse TCP (compteur partagé). "
        "Vérifier TRUSTED_PROXY_COUNT et TRUSTED_PROXY_NETWORKS.",
        message,
    )


def _bucket(address: ipaddress.IPv4Address | ipaddress.IPv6Address) -> str:
    """Clé de compteur : IPv4 telle quelle ; IPv6 ramenée à son préfixe /64 (un client en
    contrôle un entier et en change à volonté, sinon la limite serait contournée) ;
    IPv4 mappée dans IPv6 ramenée à l'IPv4."""
    if isinstance(address, ipaddress.IPv6Address):
        if address.ipv4_mapped is not None:
            return str(address.ipv4_mapped)
        return str(ipaddress.IPv6Network((address, 64), strict=False))
    return str(address)


def _peer_key(peer: str | None) -> str:
    if not peer:
        return "unknown"
    try:
        return _bucket(ipaddress.ip_address(peer))
    except ValueError:
        return peer  # adresse non IP (ex. « testclient » dans les tests) : telle quelle


def resolve_client_ip(
    peer: str | None, forwarded_for_headers: list[str], proxy_settings: ProxySettings | None = None
) -> str:
    """Clé de compteur du client (cf. docstring du module).

    `forwarded_for_headers` : valeurs BRUTES de chaque ligne `X-Forwarded-For`, dans
    l'ordre d'arrivée ; concaténées, les lignes ajoutées par les proxys restent à droite.
    """
    config = settings if proxy_settings is None else proxy_settings
    fallback = _peer_key(peer)
    count = config.trusted_proxy_count
    if count == 0:
        return fallback

    try:
        peer_address = ipaddress.ip_address(peer) if peer else None
    except ValueError:
        peer_address = None
    if peer_address is None or not any(peer_address in net for net in config.trusted_networks):
        _warn(
            "peer-hors-reseau",
            "adresse TCP hors du réseau des proxys de confiance (accès direct ?).",
        )
        return fallback

    joined = ", ".join(forwarded_for_headers)
    # rsplit borné : seul le bout droit de l'en-tête est examiné, quelle que soit la
    # quantité de valeurs écrites à gauche par le client.
    tail = joined.rsplit(",", count)[-count:]
    if len(tail) < count:
        _warn(
            "entrees-insuffisantes",
            f"X-Forwarded-For compte moins de {count} entrées (TRUSTED_PROXY_COUNT).",
        )
        return fallback
    try:
        return _bucket(ipaddress.ip_address(tail[0].strip()))
    except ValueError:
        _warn("entree-invalide", "l'entrée attendue de X-Forwarded-For n'est pas une adresse IP.")
        return fallback


def get_client_ip(request: Request) -> str:
    """Clé de compteur du client de cette requête."""
    peer = request.client.host if request.client else None
    forwarded_for = [
        value.decode("latin1")
        for name, value in request.scope["headers"]
        if name == b"x-forwarded-for"
    ]
    return resolve_client_ip(peer, forwarded_for)
