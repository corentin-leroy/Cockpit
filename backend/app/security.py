"""Primitives de sécurité : hachage des mots de passe et émission de JWT.

Isolé dans son propre module pour que le jour où l'on change d'algorithme
(ou de bibliothèque), un seul fichier soit touché.
"""

import hashlib
import os
import secrets
from datetime import datetime, timedelta, timezone

import jwt  # PyJWT
from passlib.context import CryptContext

# bcrypt : standard éprouvé, salage intégré et coût ajustable.
# `deprecated="auto"` permettra de re-hacher en douceur si l'on durcit
# le schéma plus tard.
_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# --- Configuration JWT ---
JWT_ALGORITHM = "HS256"  # signature symétrique : un seul secret partagé


def _positive_int_env(name: str, default: int) -> int:
    """Lit une variable d'environnement entière et strictement positive.

    Échoue BRUYAMMENT sur une valeur invalide, au lieu de retomber en silence sur
    le défaut : une coquille (« 12h », « 720 minutes », une valeur négative) doit
    interrompre le démarrage, pas produire une durée de session différente de
    celle qu'on croit avoir configurée. Sur Railway, l'erreur apparaît
    immédiatement dans les logs de déploiement et le healthcheck échoue — bien
    préférable à une expiration silencieusement fausse en production.
    """
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default

    try:
        value = int(raw)
    except ValueError:
        raise RuntimeError(
            f"{name} doit être un nombre entier de minutes (reçu : {raw!r})."
        ) from None

    if value <= 0:
        raise RuntimeError(f"{name} doit être strictement positif (reçu : {value}).")
    return value


# Durée de vie du jeton de session, en minutes. Défaut : 720 (12 heures), pour
# couvrir une journée d'utilisation sans reconnexion.
#
# COMPROMIS ASSUMÉ : ces jetons sont SANS ÉTAT (rien n'est stocké côté serveur,
# la signature suffit à les valider). Ils sont donc IRRÉVOCABLES — se déconnecter
# efface le jeton du navigateur, mais une copie volée reste valable jusqu'à son
# expiration. Cette durée est par conséquent la SEULE borne à l'exploitation d'un
# jeton dérobé : la porter à 12 h multiplie par douze la fenêtre d'attaque. Voir
# la note sur les refresh tokens dans CLAUDE.md avant de l'allonger davantage.
#
# Configurable pour pouvoir être resserrée sans redéploiement — typiquement en
# réaction à un incident, où l'on veut réduire la fenêtre tout de suite. Une
# valeur plus courte ne s'applique qu'aux jetons émis ENSUITE : ceux déjà en
# circulation gardent l'expiration inscrite à leur émission.
ACCESS_TOKEN_EXPIRE_MINUTES = _positive_int_env("ACCESS_TOKEN_EXPIRE_MINUTES", 720)

# --- Durées de vie des tokens envoyés par email ---
# Reset : court, c'est un secret qui donne accès au compte.
PASSWORD_RESET_EXPIRE_MINUTES = 60
# Vérification : long, l'utilisateur peut confirmer plus tard (non bloquant).
EMAIL_VERIFICATION_EXPIRE_HOURS = 24


def hash_password(plain_password: str) -> str:
    """Renvoie l'empreinte bcrypt (salée) d'un mot de passe en clair."""
    return _pwd_context.hash(plain_password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Vérifie qu'un mot de passe en clair correspond à son empreinte."""
    return _pwd_context.verify(plain_password, hashed_password)


# Empreinte « leurre », calculée une fois au chargement du module. Sert au login
# à égaliser le temps de réponse quand l'email est inconnu : on fait alors un
# vrai verify_password contre ce hash plutôt que de court-circuiter bcrypt, ce
# qui empêche d'énumérer les comptes existants par mesure du temps de réponse.
DUMMY_PASSWORD_HASH = hash_password("timing-attack-mitigation-placeholder")


def generate_url_token() -> str:
    """Génère un token à usage unique, transmissible dans une URL.

    32 octets d'aléa cryptographique (soit 256 bits), encodés en base64 URL-safe.
    C'est le secret envoyé par email ; il n'est jamais stocké tel quel (voir
    `hash_token`).
    """
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    """Empreinte SHA-256 (hexadécimale) d'un token, telle que stockée en base.

    Hash RAPIDE, volontairement : contrairement à un mot de passe, un token de
    256 bits d'aléa n'est pas brute-forçable, donc le coût d'un bcrypt serait
    payé pour rien à chaque vérification de lien. Le hash sert ici à ce qu'une
    fuite de la base ne livre aucun lien réutilisable.
    """
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def utcnow() -> datetime:
    """Heure UTC courante, SANS fuseau attaché.

    Les colonnes DateTime de SQLite ne conservent pas le fuseau : une valeur
    écrite avec tzinfo revient naïve à la lecture. On manipule donc partout des
    datetimes naïfs exprimés en UTC, pour que les comparaisons (expiration) ne
    mélangent jamais aware et naive — ce qui lèverait un TypeError.
    """
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _get_secret_key() -> str:
    """Lit la clé de signature depuis l'environnement.

    Lecture paresseuse (et non au niveau module) pour ne pas casser l'import
    de ce module — donc l'inscription, qui n'a pas besoin de JWT — quand la
    variable n'est pas définie. Échoue clairement le jour où on forge un token.
    """
    secret = os.getenv("JWT_SECRET_KEY")
    if not secret:
        raise RuntimeError(
            "JWT_SECRET_KEY n'est pas définie. Renseignez-la dans votre "
            "environnement (voir .env.example)."
        )
    return secret


def create_access_token(data: dict) -> str:
    """Forge un JWT signé (HS256) à partir de `data`.

    Ajoute automatiquement le claim `exp` (expiration). L'appelant fournit le
    claim `sub` (identifiant utilisateur, sous forme de chaîne).
    """
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode["exp"] = expire
    return jwt.encode(to_encode, _get_secret_key(), algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> dict:
    """Décode et vérifie un JWT, puis renvoie son payload.

    `jwt.decode` valide la signature ET l'expiration (claim `exp`). En cas de
    problème, PyJWT lève l'exception appropriée — `jwt.ExpiredSignatureError`
    si le token est expiré, une autre sous-classe de `jwt.PyJWTError` (signature
    invalide, token malformé...) sinon. On laisse remonter : c'est à l'appelant
    (la dépendance `get_current_user`) de la traduire en réponse HTTP 401.
    """
    return jwt.decode(token, _get_secret_key(), algorithms=[JWT_ALGORITHM])
