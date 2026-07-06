"""Schémas Pydantic : le contrat de l'API.

Distinction importante (et classique) :
- models.py  = ce qui est stocké en base (SQLAlchemy)
- schemas.py = ce qui entre et sort de l'API (Pydantic)
Les deux se ressemblent mais ne sont PAS la même chose : on ne veut pas
exposer tous les champs internes, et les règles de validation diffèrent.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models import ApplicationStatus


class UserCreate(BaseModel):
    """Payload d'inscription. EmailStr valide le format de l'email ;
    le mot de passe en clair n'existe que le temps de la requête, jamais stocké."""

    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class UserRead(BaseModel):
    """Représentation publique d'un utilisateur.

    N'expose volontairement PAS hashed_password : le contrat de sortie est
    distinct du modèle ORM, c'est tout l'intérêt de séparer schemas et models.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    created_at: datetime


class UserLogin(BaseModel):
    """Identifiants de connexion. Pas de contrainte de longueur ici : on valide
    le mot de passe en le comparant au hash, pas en rejouant la politique
    d'inscription (un mot de passe valide hier ne doit pas devenir non saisissable)."""

    email: EmailStr
    password: str


class Token(BaseModel):
    """Réponse du login : le JWT et son type, au format attendu par OAuth2."""

    access_token: str
    token_type: str = "bearer"


class BoardCreate(BaseModel):
    """Payload pour créer un tableau. Seul le nom est fourni ; le propriétaire
    (user_id) est renseigné côté serveur depuis le current_user."""

    name: str = Field(min_length=1, max_length=255)


class BoardUpdate(BaseModel):
    """Payload pour renommer un tableau. Le nom est le seul champ modifiable."""

    name: str = Field(min_length=1, max_length=255)


class BoardRead(BaseModel):
    """Ce que l'API renvoie pour un tableau."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    user_id: int
    created_at: datetime
    updated_at: datetime


class ApplicationCreate(BaseModel):
    """Payload pour créer une candidature (formulaire ou extension).

    board_id désigne le tableau cible ; le serveur vérifie qu'il appartient bien
    au current_user (sinon 404). Le statut n'est pas fourni : il démarre en
    « saved » (voir le modèle)."""

    board_id: int
    title: str = Field(min_length=1, max_length=255)
    company: str = Field(min_length=1, max_length=255)
    location: str | None = Field(default=None, max_length=255)
    url: str | None = Field(default=None, max_length=2048)
    source: str = "manual"
    notes: str | None = None


class ApplicationUpdate(BaseModel):
    """Payload pour modifier une candidature. Tous les champs optionnels :
    on ne met à jour que ce qui est fourni (PATCH sémantique)."""

    title: str | None = Field(default=None, min_length=1, max_length=255)
    company: str | None = Field(default=None, min_length=1, max_length=255)
    location: str | None = None
    url: str | None = None
    status: ApplicationStatus | None = None
    notes: str | None = None
    applied_at: datetime | None = None


class ApplicationRead(BaseModel):
    """Ce que l'API renvoie au client."""

    model_config = ConfigDict(from_attributes=True)  # lecture depuis l'objet ORM

    id: int
    board_id: int
    title: str
    company: str
    location: str | None
    url: str | None
    source: str
    status: ApplicationStatus
    notes: str | None
    applied_at: datetime | None
    created_at: datetime
    updated_at: datetime
