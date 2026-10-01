"""Lecture de l'adresse IP du client derrière le proxy de Railway (app/client_ip.py).

La forme réelle a été MESURÉE en production (journaux d'un diagnostic temporaire) :
- l'application reçoit l'adresse du dernier proxy (100.64.0.x), pas celle du client ;
- `X-Forwarded-For` arrive sous la forme « <client>, <saut du proxy> » ; un en-tête
  falsifié par le client (une ou deux valeurs) est écarté par Railway ;
- `X-Real-IP` porte le client ; `Forwarded` traverse tel quel (donc JAMAIS lu).

La règle testée ici : avec N proxys de confiance, le client est la N-ième entrée en
partant de la DROITE. C'est correct que le proxy écrase l'en-tête reçu OU qu'il y
ajoute. Toute anomalie replie sur l'adresse TCP (compteur partagé : jamais de
contournement).

Adresses de documentation (RFC 5737 / 3849) : 198.51.100.x, 203.0.113.x, 2001:db8::.
"""

import ipaddress
import logging

import pytest
from starlette.requests import Request

from app import client_ip
from app.client_ip import ProxySettings, load_proxy_settings, resolve_client_ip

RAILWAY = ProxySettings(
    trusted_proxy_count=2, trusted_networks=(ipaddress.ip_network("100.64.0.0/10"),)
)
PROXY_PEER = "100.64.0.2"
EDGE = "152.233.56.194"  # saut du proxy observé en dernière position (pas le client)
CLIENT = "198.51.100.7"


def resolve(peer, headers, settings=RAILWAY):
    return resolve_client_ip(peer, headers, settings)


# ---------------------------------------------------------------------------
# La forme observée, et les falsifications
# ---------------------------------------------------------------------------


def test_the_observed_railway_shape_gives_the_client():
    assert resolve(PROXY_PEER, [f"{CLIENT}, {EDGE}"]) == CLIENT


@pytest.mark.parametrize(
    "header",
    [
        f"1.2.3.4, {CLIENT}, {EDGE}",  # le proxy a AJOUTÉ à la valeur falsifiée
        f"1.2.3.4, 5.6.7.8, {CLIENT}, {EDGE}",  # deux valeurs falsifiées
        f"9.9.9.9,{CLIENT},{EDGE}",  # sans espaces
        f"{'1.1.1.1, ' * 500}{CLIENT}, {EDGE}",  # énorme en-tête falsifié
    ],
)
def test_forged_leading_values_never_change_the_result(header):
    """Compter depuis la droite : tout ce que le client a écrit à gauche est ignoré,
    que le proxy écrase l'en-tête ou y ajoute."""
    assert resolve(PROXY_PEER, [header]) == CLIENT


def test_repeated_header_lines_are_joined_in_arrival_order():
    """Le client envoie deux lignes `X-Forwarded-For` ; le proxy ajoute la sienne à la
    suite : la concaténation (dans l'ordre) garde le client réel en avant-dernier."""
    assert resolve(PROXY_PEER, ["1.2.3.4", f"9.9.9.9, {CLIENT}, {EDGE}"]) == CLIENT
    assert resolve(PROXY_PEER, ["1.2.3.4, 5.6.7.8", f"{CLIENT}, {EDGE}"]) == CLIENT


def test_a_single_trusted_proxy_reads_the_last_entry():
    one = ProxySettings(1, RAILWAY.trusted_networks)
    assert resolve(PROXY_PEER, [CLIENT], one) == CLIENT
    assert resolve(PROXY_PEER, [f"1.2.3.4, {CLIENT}"], one) == CLIENT


# ---------------------------------------------------------------------------
# Replis : jamais un contournement, toujours l'adresse TCP
# ---------------------------------------------------------------------------


def test_without_trusted_proxies_the_header_is_ignored_entirely():
    """Réglage par défaut (TRUSTED_PROXY_COUNT absent = 0) : l'en-tête, falsifiable,
    n'est jamais lu."""
    assert resolve("203.0.113.9", [f"{CLIENT}, {EDGE}"], ProxySettings()) == "203.0.113.9"


def test_no_header_falls_back_to_the_peer():
    assert resolve(PROXY_PEER, []) == PROXY_PEER


def test_too_few_entries_fall_back_to_the_peer():
    """Moins d'entrées que de proxys de confiance : topologie inattendue."""
    assert resolve(PROXY_PEER, [CLIENT]) == PROXY_PEER


@pytest.mark.parametrize(
    "header",
    [
        f"pas-une-ip, {EDGE}",
        f"{CLIENT}:5000, {EDGE}",  # port : refusé, on ne devine pas
        f", {EDGE}",
        f" , {EDGE}",
        "",
        ",",
        f"[{CLIENT}], {EDGE}",
        f"{CLIENT}; for=1.2.3.4, {EDGE}",
    ],
)
def test_an_unparsable_client_entry_falls_back_to_the_peer(header):
    assert resolve(PROXY_PEER, [header]) == PROXY_PEER


def test_a_peer_outside_the_proxy_network_means_a_direct_access():
    """Connexion directe à l'application, sans passer par le proxy : l'en-tête est
    forgeable, il est ignoré."""
    assert resolve("203.0.113.50", [f"1.2.3.4, {CLIENT}, {EDGE}"]) == "203.0.113.50"


def test_missing_peer_gives_a_shared_bucket():
    assert resolve(None, [f"{CLIENT}, {EDGE}"]) == "unknown"


def test_a_non_ip_peer_is_kept_verbatim():
    """Le client de test de Starlette annonce « testclient » comme adresse."""
    assert resolve("testclient", [], ProxySettings()) == "testclient"


# ---------------------------------------------------------------------------
# Normalisation : IPv6 par préfixe /64, IPv4 mappée, casse
# ---------------------------------------------------------------------------


def test_ipv6_clients_share_a_bucket_per_64_prefix():
    a = resolve(PROXY_PEER, [f"2001:db8:1:2:aaaa:bbbb:cccc:dddd, {EDGE}"])
    b = resolve(PROXY_PEER, [f"2001:db8:1:2:1111:2222:3333:4444, {EDGE}"])
    other = resolve(PROXY_PEER, [f"2001:db8:1:3::1, {EDGE}"])

    assert a == b == "2001:db8:1:2::/64"
    assert other != a


def test_ipv4_mapped_ipv6_is_the_ipv4_address():
    assert resolve(PROXY_PEER, [f"::ffff:{CLIENT}, {EDGE}"]) == CLIENT


def test_ipv6_notation_variants_are_the_same_bucket():
    assert resolve(PROXY_PEER, [f"2001:DB8::1, {EDGE}"]) == resolve(
        PROXY_PEER, [f"2001:0db8:0000:0000:0000:0000:0000:0002, {EDGE}"]
    )


def test_ipv4_mapped_peer_is_normalised_too():
    assert resolve(f"::ffff:{CLIENT}", [], ProxySettings()) == CLIENT


# ---------------------------------------------------------------------------
# Journal d'avertissement : un repli doit se voir, sans inonder les journaux
# ---------------------------------------------------------------------------


def test_a_fallback_is_logged_once_not_for_every_request(caplog):
    with caplog.at_level(logging.WARNING, logger="app.rate_limit"):
        for _ in range(50):
            resolve(PROXY_PEER, [CLIENT])  # trop peu d'entrées
    assert len(caplog.records) == 1
    assert "TRUSTED_PROXY_COUNT" in caplog.records[0].getMessage()


def test_no_warning_when_no_proxy_is_trusted(caplog):
    with caplog.at_level(logging.WARNING, logger="app.rate_limit"):
        resolve("203.0.113.9", [CLIENT], ProxySettings())
    assert caplog.records == []


# ---------------------------------------------------------------------------
# Réglages d'environnement
# ---------------------------------------------------------------------------


def test_default_settings_trust_no_proxy():
    assert load_proxy_settings({}).trusted_proxy_count == 0


def test_blank_count_means_zero():
    assert load_proxy_settings({"TRUSTED_PROXY_COUNT": "  "}).trusted_proxy_count == 0


def test_count_and_default_network_are_read():
    loaded = load_proxy_settings({"TRUSTED_PROXY_COUNT": "2"})
    assert loaded.trusted_proxy_count == 2
    assert ipaddress.ip_network("100.64.0.0/10") in loaded.trusted_networks


def test_custom_networks_are_read():
    loaded = load_proxy_settings(
        {"TRUSTED_PROXY_COUNT": "1", "TRUSTED_PROXY_NETWORKS": "10.0.0.0/8, 192.0.2.0/24"}
    )
    assert loaded.trusted_networks == (
        ipaddress.ip_network("10.0.0.0/8"),
        ipaddress.ip_network("192.0.2.0/24"),
    )


@pytest.mark.parametrize("bad", ["abc", "-1", "11", "1.5", "deux"])
def test_an_invalid_count_fails_loudly_instead_of_falling_back(bad):
    """Jamais de repli silencieux sur le défaut : une coquille ferait croire que la
    limite par IP est en place alors que tous les utilisateurs partageraient un compteur."""
    with pytest.raises(ValueError, match="TRUSTED_PROXY_COUNT"):
        load_proxy_settings({"TRUSTED_PROXY_COUNT": bad})


@pytest.mark.parametrize("bad", ["pas-un-reseau", "10.0.0.0/99", "100.64.0.0/10, xx"])
def test_an_invalid_network_fails_loudly(bad):
    with pytest.raises(ValueError, match="TRUSTED_PROXY_NETWORKS"):
        load_proxy_settings({"TRUSTED_PROXY_COUNT": "2", "TRUSTED_PROXY_NETWORKS": bad})


# ---------------------------------------------------------------------------
# get_client_ip : lecture d'une vraie requête
# ---------------------------------------------------------------------------


def make_request(peer, *forwarded):
    headers = [(b"host", b"api.example.com")]
    headers += [(b"x-forwarded-for", value.encode()) for value in forwarded]
    headers += [(b"x-real-ip", b"9.9.9.9"), (b"forwarded", b"for=8.8.8.8")]
    return Request(
        {"type": "http", "client": (peer, 4242), "headers": headers, "method": "GET", "path": "/"}
    )


def test_get_client_ip_reads_the_raw_header_lines(monkeypatch):
    monkeypatch.setattr(client_ip, "settings", RAILWAY)
    request = make_request(PROXY_PEER, "1.2.3.4", f"{CLIENT}, {EDGE}")
    assert client_ip.get_client_ip(request) == CLIENT


def test_get_client_ip_never_reads_x_real_ip_or_forwarded(monkeypatch):
    """`Forwarded` traverse Railway tel quel (falsifiable) et X-Real-IP n'est pas la
    source retenue : seule la lecture de X-Forwarded-For depuis la droite compte."""
    monkeypatch.setattr(client_ip, "settings", RAILWAY)
    request = make_request(PROXY_PEER)  # aucun X-Forwarded-For
    assert client_ip.get_client_ip(request) == PROXY_PEER


def test_get_client_ip_without_client_in_scope():
    request = Request({"type": "http", "headers": [], "method": "GET", "path": "/"})
    assert client_ip.get_client_ip(request) == "unknown"
