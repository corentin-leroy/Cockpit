"""Modèles ORM : la structure des tables en base.

Hiérarchie : User → Boards → Applications.
- Un utilisateur possède plusieurs tableaux (Board).
- Un tableau contient plusieurs candidatures (Application).
- Une candidature référence son tableau (board_id) et NON plus l'utilisateur
  directement : l'ownership se déduit en chaîne (application → board → user),
  ce qui évite toute redondance (un seul endroit porte le lien au propriétaire).
"""

import enum
from datetime import datetime, timezone

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

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

    # Un utilisateur possède plusieurs tableaux. Supprimer un utilisateur
    # supprime ses tableaux (et, par cascade en chaîne, leurs candidatures).
    boards: Mapped[list["Board"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class Board(Base):
    """Un tableau kanban appartenant à un utilisateur.

    Niveau intermédiaire entre User et Application : un utilisateur peut
    organiser ses candidatures dans plusieurs tableaux (ex. par secteur, par
    type de contrat…). Chaque utilisateur en a toujours au moins un.
    """

    __tablename__ = "boards"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)

    # Propriétaire du tableau. C'est LE lien vers l'utilisateur : l'ownership
    # d'une candidature se déduit via son board (board.user_id).
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"), index=True, nullable=False
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    user: Mapped["User"] = relationship(back_populates="boards")
    # Supprimer un tableau supprime ses candidatures (cascade — voir la règle du
    # dernier tableau non supprimable côté router).
    applications: Mapped[list["Application"]] = relationship(
        back_populates="board", cascade="all, delete-orphan"
    )


class Application(Base):
    """Une candidature suivie dans le cockpit, rattachée à un tableau (Board)."""

    __tablename__ = "applications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    # --- Données de l'offre ---
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    company: Mapped[str] = mapped_column(String(255), nullable=False)
    location: Mapped[str | None] = mapped_column(String(255))
    url: Mapped[str | None] = mapped_column(String(2048))
    source: Mapped[str] = mapped_column(String(50), default="manual")
    # source : "manual", "extension", "france_travail", "la_bonne_alternance"

    # --- Suivi ---
    status: Mapped[ApplicationStatus] = mapped_column(
        Enum(ApplicationStatus), default=ApplicationStatus.SAVED, nullable=False
    )
    notes: Mapped[str | None] = mapped_column(Text)
    applied_at: Mapped[datetime | None] = mapped_column(DateTime)

    # --- Rattachement ---
    # Une candidature appartient à un tableau (obligatoire). Le propriétaire n'est
    # PLUS stocké ici : on le retrouve via board.user_id (chaîne d'ownership).
    board_id: Mapped[int] = mapped_column(
        ForeignKey("boards.id"), index=True, nullable=False
    )

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

    board: Mapped["Board"] = relationship(back_populates="applications")
