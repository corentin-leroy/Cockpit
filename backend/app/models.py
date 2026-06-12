"""Modèles ORM : la structure des tables en base.

Schéma V1 volontairement minimal. Le champ user_id est déjà prévu
(nullable pour l'instant) : il deviendra obligatoire quand l'auth
sera en place — premier chantier de Corentin 😉
"""

import enum
from datetime import datetime, timezone

from sqlalchemy import DateTime, Enum, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ApplicationStatus(str, enum.Enum):
    """Les colonnes du kanban."""

    SAVED = "saved"          # Repérée
    APPLIED = "applied"      # Postulée
    FOLLOWED_UP = "followed_up"  # Relancée
    INTERVIEW = "interview"  # Entretien
    REJECTED = "rejected"    # Refusée
    ACCEPTED = "accepted"    # Acceptée 🎉


class User(Base):
    """Un utilisateur du cockpit (multi-utilisateurs)."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    # unique=True garantit l'unicité en base ; index=True accélère le lookup
    # par email (login et contrôle de doublon à l'inscription).
    email: Mapped[str] = mapped_column(
        String(255), unique=True, index=True, nullable=False
    )
    # On ne stocke JAMAIS le mot de passe en clair, seulement son empreinte bcrypt.
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )


class Application(Base):
    """Une candidature suivie dans le cockpit."""

    __tablename__ = "applications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    # --- Données de l'offre ---
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    company: Mapped[str] = mapped_column(String(255), nullable=False)
    location: Mapped[str | None] = mapped_column(String(255))
    url: Mapped[str | None] = mapped_column(String(2048))
    source: Mapped[str] = mapped_column(String(50), default="manual")
    # source : "manual", "bookmarklet", "france_travail", "la_bonne_alternance"

    # --- Suivi ---
    status: Mapped[ApplicationStatus] = mapped_column(
        Enum(ApplicationStatus), default=ApplicationStatus.SAVED, nullable=False
    )
    notes: Mapped[str | None] = mapped_column(Text)
    applied_at: Mapped[datetime | None] = mapped_column(DateTime)

    # --- Multi-utilisateurs (à activer avec l'auth) ---
    user_id: Mapped[int | None] = mapped_column(Integer, index=True)

    # --- Métadonnées ---
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
