"""Primitives de sécurité : hachage des mots de passe.

Isolé dans son propre module pour que le jour où l'on change d'algorithme
(ou de bibliothèque), un seul fichier soit touché. La vérification
(`verify_password`) servira au login, prochaine étape.
"""

from passlib.context import CryptContext

# bcrypt : standard éprouvé, salage intégré et coût ajustable.
# `deprecated="auto"` permettra de re-hacher en douceur si l'on durcit
# le schéma plus tard.
_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain_password: str) -> str:
    """Renvoie l'empreinte bcrypt (salée) d'un mot de passe en clair."""
    return _pwd_context.hash(plain_password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Vérifie qu'un mot de passe en clair correspond à son empreinte."""
    return _pwd_context.verify(plain_password, hashed_password)
