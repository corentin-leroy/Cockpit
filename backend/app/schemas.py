"""Schémas Pydantic : le contrat de l'API.

Distinction importante (et classique) :
- models.py  = ce qui est stocké en base (SQLAlchemy)
- schemas.py = ce qui entre et sort de l'API (Pydantic)
Les deux se ressemblent mais ne sont PAS la même chose : on ne veut pas
exposer tous les champs internes, et les règles de validation diffèrent.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models import ApplicationStatus


class ApplicationCreate(BaseModel):
    """Payload pour créer une candidature (formulaire ou bookmarklet)."""

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
