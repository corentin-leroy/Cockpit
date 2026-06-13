"""Primitives de sécurité : hachage des mots de passe et émission de JWT.

Isolé dans son propre module pour que le jour où l'on change d'algorithme
(ou de bibliothèque), un seul fichier soit touché.
"""

import os
from datetime import datetime, timedelta, timezone

import jwt  # PyJWT
from passlib.context import CryptContext

# bcrypt : standard éprouvé, salage intégré et coût ajustable.
# `deprecated="auto"` permettra de re-hacher en douceur si l'on durcit
# le schéma plus tard.
_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# --- Configuration JWT ---
JWT_ALGORITHM = "HS256"  # signature symétrique : un seul secret partagé
ACCESS_TOKEN_EXPIRE_MINUTES = 60


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
