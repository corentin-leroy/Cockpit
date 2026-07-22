"""Modèles ORM : la structure des tables en base.

Hiérarchie : User → Boards → Applications.
- Un utilisateur possède plusieurs tableaux (Board).
- Un tableau contient plusieurs candidatures (Application).
- Une candidature référence son tableau (board_id) et NON plus l'utilisateur
  directement : l'ownership se déduit en chaîne (application → board → user),
  ce qui évite toute redondance (un seul endroit porte le lien au propriétaire).

Cascade de suppression, déclarée à DEUX niveaux complémentaires :

1. Dans le SCHÉMA — `ondelete="CASCADE"` sur chaque clé étrangère. C'est la base
   de données qui garantit alors qu'aucune ligne ne survit à son parent, quel que
   soit le chemin emprunté : ORM, script de maintenance, psql, migration. Sans
   cette déclaration, toute suppression passant à côté de l'ORM échouait en
   PostgreSQL sur une violation de contrainte (le défaut d'une clé étrangère est
   NO ACTION, qui REFUSE de supprimer un parent encore référencé).

2. Dans l'ORM — `cascade="all, delete-orphan"` sur les relations parentes. Il
   reste nécessaire : il porte la sémantique ORPHELIN (retirer un enfant de la
   collection de son parent le supprime), que la base ne connaît pas.

`passive_deletes=True` articule les deux : il dit à SQLAlchemy de NE PAS charger
les enfants pour les supprimer un par un lors d'un `db.delete(parent)`, et de
laisser la base appliquer sa cascade. Voir la note dans database.py sur le PRAGMA
que cela impose sous SQLite.
"""

import enum
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.security import utcnow

# Les colonnes DateTime sont NAIVES et exprimées en UTC, partout (cf. utcnow()).
# On alimente donc les valeurs par défaut avec utcnow() et jamais avec un
# datetime.now(timezone.utc) « aware » : SQLite laisse tomber le fuseau en
# silence, mais PostgreSQL, lui, convertit une valeur aware vers le fuseau de la
# session avant de la stocker dans un TIMESTAMP WITHOUT TIME ZONE. Le même code
# écrirait alors des heures décalées selon le moteur — et le rate limiting des
# emails, qui compare created_at à utcnow(), s'en trouverait faussé.


class ApplicationStatus(str, enum.Enum):
    """Les colonnes du kanban."""

    SAVED = "saved"          # Repérée
    APPLIED = "applied"      # Postulée
    FOLLOWED_UP = "followed_up"  # Relancée
    INTERVIEW = "interview"  # Entretien
    REJECTED = "rejected"    # Refusée
    ACCEPTED = "accepted"    # Acceptée 🎉


class TokenPurpose(str, enum.Enum):
    """Usage d'un SecurityToken. Le filtrer à la vérification interdit qu'un
    token émis pour un usage serve à l'autre (un lien de vérification d'email ne
    doit jamais pouvoir changer un mot de passe)."""

    PASSWORD_RESET = "password_reset"
    EMAIL_VERIFICATION = "email_verification"


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

    # Adresse email confirmée via le lien envoyé à l'inscription. NON BLOQUANT :
    # un compte non vérifié peut se connecter et utiliser l'app normalement (le
    # front se sert de ce champ pour afficher un bandeau d'invitation).
    is_verified: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, nullable=False
    )

    # Un utilisateur possède plusieurs tableaux. Supprimer un utilisateur
    # supprime ses tableaux (et, par cascade en chaîne, leurs candidatures).
    boards: Mapped[list["Board"]] = relationship(
        back_populates="user", cascade="all, delete-orphan", passive_deletes=True
    )
    # Supprimer un utilisateur invalide de fait ses liens en attente.
    security_tokens: Mapped[list["SecurityToken"]] = relationship(
        back_populates="user", cascade="all, delete-orphan", passive_deletes=True
    )


class SecurityToken(Base):
    """Token à usage unique envoyé par email (reset de mot de passe, vérification).

    UNE seule table pour les deux usages, discriminés par `purpose` : les deux
    tokens ont exactement la même forme (aléatoire, haché, daté, consommable) et
    le même cycle de vie. Deux tables auraient dupliqué le schéma, la logique de
    vérification et le futur nettoyage des tokens expirés, sans rien apporter :
    la seule chose qui les distingue est la durée de validité et l'action
    déclenchée, décidées à l'appel. Le cloisonnement est assuré par `purpose`,
    obligatoirement filtré à la vérification.

    Le token en clair n'est JAMAIS stocké : seul son SHA-256 l'est. Un vol de la
    base ne permet donc pas de rejouer un lien. SHA-256 et non bcrypt : bcrypt
    protège des secrets à faible entropie (mots de passe humains, brute-forçables
    hors ligne). Ici le secret fait 256 bits d'aléa cryptographique — inattaquable
    par force brute — donc un hash rapide suffit, et évite de payer un coût bcrypt
    à chaque clic sur un lien.
    """

    __tablename__ = "security_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    # SHA-256 en hexadécimal = 64 caractères. unique : deux tokens ne peuvent pas
    # collisionner ; index : la vérification est un lookup par ce hash.
    token_hash: Mapped[str] = mapped_column(
        String(64), unique=True, index=True, nullable=False
    )
    purpose: Mapped[TokenPurpose] = mapped_column(Enum(TokenPurpose), nullable=False)

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )

    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    # NULL tant que le token n'a pas servi. Renseigné à la consommation : un
    # token ne vaut que pour un seul usage, même avant son expiration.
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime)

    # Sert aussi de compteur au rate limiting (nombre de demandes récentes).
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, nullable=False
    )

    user: Mapped["User"] = relationship(back_populates="security_tokens")


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
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=utcnow,
        onupdate=utcnow,
        nullable=False,
    )

    user: Mapped["User"] = relationship(back_populates="boards")
    # Supprimer un tableau supprime ses candidatures (cascade — voir la règle du
    # dernier tableau non supprimable côté router).
    applications: Mapped[list["Application"]] = relationship(
        back_populates="board", cascade="all, delete-orphan", passive_deletes=True
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
        ForeignKey("boards.id", ondelete="CASCADE"), index=True, nullable=False
    )

    # --- Métadonnées ---
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=utcnow,
        onupdate=utcnow,
        nullable=False,
    )

    board: Mapped["Board"] = relationship(back_populates="applications")
