"""Remplit une base de DEV locale avec un compte de test et des données factices.

Usage, depuis backend/ (schéma à jour : `alembic upgrade head` d'abord) :
    .venv\\Scripts\\python.exe -m scripts.seed_dev           crée le compte de test
    .venv\\Scripts\\python.exe -m scripts.seed_dev --reset   le supprime puis le recrée

Ce que le script crée : le compte demo@cockpit.example (adresse vérifiée), trois
tableaux (Alternance, CDI, Stage), 40 candidatures actives réparties sur les cinq
statuts et 15 archivées. Contenu entièrement inventé (entreprises comprises) et
DÉTERMINISTE : deux exécutions produisent les mêmes contenus ; seuls les
identifiants et les horodatages posés par le serveur (created_at, updated_at,
archived_at) changent.

Garde-fous (cf. dev-docs/seed-dev.md) :
- SQLite uniquement : refus AVANT toute connexion si la base effectivement utilisée
  par l'application (app.database.engine, après chargement du .env comme le font
  app.main et alembic/env.py) n'est pas SQLite, que DATABASE_URL soit définie ou
  non. Le message de refus n'affiche jamais l'URL (elle contiendrait un mot de
  passe).
- Le script ne touche qu'au compte demo@cockpit.example : s'il existe déjà, arrêt sans
  rien écrire ; --reset supprime CE compte (et ses données, par la cascade de la
  base) puis le recrée. Aucun autre compte n'est lu ni modifié.

Écriture par les fonctions de l'application, jamais en SQL brut ni en positions
posées à la main : create_board, puis pour chaque carte create_application (arrivée
en haut de « Repérée »), update_application (statut et date de candidature :
arrivée en haut de la colonne cible, chemin du PATCH) et archive_application. Les
cartes d'une colonne sont donc créées dans l'ordre INVERSE de leur affichage.
Seul le compte est créé par le modèle User : l'inscription (/auth/register) exige
une requête HTTP, applique la limite de débit par IP, envoie un email de
vérification (réel si la clé Brevo du .env est chargée) et crée un tableau « Mes
candidatures » que ce jeu de données ne veut pas.
"""

import argparse
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

# AVANT d'importer app.database, qui lit DATABASE_URL à l'import : le script vise
# ainsi la même base que l'application lancée par uvicorn (app.main charge le .env)
# et qu'alembic (alembic/env.py fait de même). load_dotenv n'écrase pas une variable
# déjà posée dans le shell.
load_dotenv()

from sqlalchemy import select  # noqa: E402
from sqlalchemy.engine import Engine  # noqa: E402
from sqlalchemy.orm import Session, sessionmaker  # noqa: E402

import app.database  # noqa: E402
from app.models import ApplicationStatus, User  # noqa: E402
from app.routers.applications import (  # noqa: E402
    archive_application,
    create_application,
    update_application,
)
from app.routers.boards import create_board  # noqa: E402
from app.schemas import ApplicationCreate, ApplicationUpdate, BoardCreate  # noqa: E402
from app.security import hash_password  # noqa: E402

# TLD réservé `.example` (RFC 2606) : aucune boîte réelle derrière. PAS `.test` : la
# validation des emails de l'API (EmailStr, bibliothèque email-validator) refuse les
# domaines à usage spécial (.test, .localhost, .invalid…), le compte serait créé mais
# la connexion répondrait 422. PAS non plus `demo@example.com` : une adresse qu'un
# développeur pourrait inscrire à la main, et que --reset supprimerait.
DEMO_EMAIL = "demo@cockpit.example"
# Mot de passe de DEV, PUBLIC : ce dépôt est public, ce mot de passe ne protège
# donc rien. Il ne doit servir NULLE PART ailleurs (ni compte réel, ni autre service,
# ni production) et le compte qu'il ouvre ne contient que des données inventées.
DEMO_PASSWORD = "cockpit-demo-dev-only"

BOARD_NAMES = ("Alternance", "CDI", "Stage")

SAVED = ApplicationStatus.SAVED
APPLIED = ApplicationStatus.APPLIED
FOLLOWED_UP = ApplicationStatus.FOLLOWED_UP
INTERVIEW = ApplicationStatus.INTERVIEW
ACCEPTED = ApplicationStatus.ACCEPTED


def _france_travail(offer_id: str) -> str:
    """URL d'offre France Travail (identifiant inventé)."""
    return f"https://candidat.francetravail.fr/offres/recherche/detail/{offer_id}"


def _indeed(job_key: str) -> str:
    """URL d'offre Indeed (identifiant inventé)."""
    return f"https://fr.indeed.com/viewjob?jk={job_key}"


@dataclass(frozen=True)
class SeedCard:
    """Une candidature factice. `applied_at` reste None pour une carte jamais
    envoyée (« Repérée ») ; `extension` marque une offre d'un site quelconque
    ajoutée par l'extension (France Travail et Indeed le sont toujours)."""

    board: str
    status: ApplicationStatus
    title: str
    company: str
    location: str | None
    url: str | None
    notes: str | None = None
    applied_at: datetime | None = None
    archived: bool = False
    extension: bool = False

    @property
    def source(self) -> str:
        """Origine enregistrée : celle qu'écrirait l'application pour cette carte."""
        on_job_board = self.url is not None and (
            "francetravail.fr" in self.url or "indeed.com" in self.url
        )
        return "extension" if on_job_board or self.extension else "manual"


# Domaines des « sites quelconques » : TLD réservé `.example` (RFC 2606), qui ne
# désigne jamais un site réel. Dans chaque colonne, les cartes sont listées DANS
# L'ORDRE AFFICHÉ (la première en haut).
CARDS: tuple[SeedCard, ...] = (
    # --- Alternance : actives (22) ---------------------------------------------
    # Repérée (12)
    SeedCard("Alternance", SAVED, "Développeur·se web full-stack en alternance (React / FastAPI)",
             "Atelier Numérique du Vercors", "Grenoble (38)", _france_travail("196KQZT"),
             notes="Rythme 3 semaines en entreprise / 1 semaine à l'école. Démarrage en septembre."),
    SeedCard("Alternance", SAVED, "Chargé·e de communication digitale – alternance 24 mois",
             "Éditions de la Lagune", "Sète (34)", _indeed("3f9a1c07d2e84b56")),
    SeedCard("Alternance", SAVED,
             "Alternance – Assistant·e chef de projet transformation numérique des services "
             "publics territoriaux, accompagnement au changement et conduite de projets de "
             "dématérialisation des démarches usagers (H/F)",
             "Communauté de communes du Haut-Lézard", "Millau (12)",
             "https://recrutement.cc-haut-lezard.example/offres/2026-0412"),
    SeedCard("Alternance", SAVED, "Technicien·ne de maintenance industrielle en alternance",
             "Fonderies Marchal & Cie", "Saint-Étienne (42)", _france_travail("197BHXD")),
    SeedCard("Alternance", SAVED, "Comptable en alternance (DCG)",
             "Cabinet Lefèvre-Arnaud Expertise", "Rennes (35)", None),
    SeedCard("Alternance", SAVED, "Alternant·e data analyst",
             "Mutuelle Solidaire de l'Estuaire", "Nantes (44)", _indeed("a17e5b90c3d26f48")),
    SeedCard("Alternance", SAVED, "Apprenti·e boulanger·ère – CAP en 2 ans",
             "Boulangerie Dupré & Fils", "Annecy (74)", _france_travail("195MRWA"),
             notes="Lever à 4 h : vérifier les horaires de bus le week-end."),
    SeedCard("Alternance", SAVED, "Alternance UX/UI designer",
             "Studio Hélice", "Bordeaux (33) – télétravail partiel",
             "https://studio-helice.example/jobs/ux-alternance", extension=True),
    SeedCard("Alternance", SAVED, "Assistant·e RH en alternance – recrutement et marque employeur",
             "Transports Mérignac Logistique", "Mérignac (33)", _indeed("5c08d4e1f7a39b62")),
    SeedCard("Alternance", SAVED, "Alternance – Administrateur·rice systèmes et réseaux",
             "Hélioptic Systèmes", "Villeneuve-d'Ascq (59)", _france_travail("198PLNC")),
    SeedCard("Alternance", SAVED, "Chargé·e d'affaires BTP en alternance",
             "Charpentes Le Gall", "Quimper (29)", None,
             notes="Vu au salon de l'alternance : rappeler Mme Kerbrat avant la fin du mois."),
    SeedCard("Alternance", SAVED, "Alternance – Développeur·se mobile Kotlin / Swift",
             "Appli'Côte", "Nice (06)",
             "https://www.applicote.example/carrieres?offre=mobile-2026&lang=fr"),
    # Postulée (5)
    SeedCard("Alternance", APPLIED, "Alternance – Commercial·e sédentaire B2B",
             "Papeteries de l'Ain", "Bourg-en-Bresse (01)", _france_travail("193TGEK"),
             applied_at=datetime(2026, 10, 28)),
    SeedCard("Alternance", APPLIED, "Assistant·e marketing produit en alternance",
             "Cosmétiques Aurore Bio", "Montpellier (34)", _indeed("e2b74a19c05d8f31"),
             applied_at=datetime(2026, 10, 24)),
    SeedCard("Alternance", APPLIED, "Alternance – Développeur·se back-end Python",
             "Coopérative Logicielle Ouest", "Angers (49)",
             "https://cooplogicielle-ouest.example/rejoindre/backend",
             notes="CV et lettre envoyés. Test technique annoncé « sous quinze jours ».",
             applied_at=datetime(2026, 10, 21)),
    SeedCard("Alternance", APPLIED, "Gestionnaire de paie en alternance",
             "Groupe médico-social Les Tilleuls", "Limoges (87)", _france_travail("192ADFV"),
             applied_at=datetime(2026, 10, 15)),
    SeedCard("Alternance", APPLIED, "Alternance – Technicien·ne support informatique",
             "Mairie de Saint-Aubin-des-Prés", "Saint-Aubin-des-Prés",
             "https://recrutement.saint-aubin-des-pres.example/offres/technicien-support",
             applied_at=datetime(2026, 10, 9)),
    # Relancée (2)
    SeedCard("Alternance", FOLLOWED_UP, "Alternance – Chargé·e de projet événementiel",
             "Agence Festiv'Arverne", "Clermont-Ferrand (63)", _indeed("0d6f2e8b47a1c953"),
             notes="Relance par mail le 14/10, pas de réponse.",
             applied_at=datetime(2026, 9, 30)),
    SeedCard("Alternance", FOLLOWED_UP, "Alternance – Juriste en droit social",
             "Étude Bérard-Nguyen", "Lyon (69)", _france_travail("190WSKJ"),
             notes="Relance téléphonique le 08/10 : dossier en cours d'étude.",
             applied_at=datetime(2026, 9, 22)),
    # Entretien (2)
    SeedCard("Alternance", INTERVIEW, "Alternance – Ingénieur·e DevOps (bac+5)",
             "Nuage Alpin Hébergement", "Chambéry (73)",
             "https://nuage-alpin.example/emplois/devops-alternance",
             notes="Entretien technique le 13/11 à 14 h en visio. Réviser Docker et la CI.",
             applied_at=datetime(2026, 9, 15)),
    SeedCard("Alternance", INTERVIEW, "Alternance – Contrôleur·se de gestion",
             "Laiteries du Bocage Normand", "Caen (14)", _france_travail("189RUYB"),
             notes="Second entretien avec la DAF le 18/11.",
             applied_at=datetime(2026, 9, 10)),
    # Acceptée (1)
    SeedCard("Alternance", ACCEPTED, "Alternance – Développeur·se full-stack JavaScript",
             "Fabrique Numérique des Calanques", "Marseille (13)", _indeed("b3c91f05e6d47a28"),
             notes="Promesse d'embauche reçue ! Signature du contrat d'apprentissage le 20/11. 🎉",
             applied_at=datetime(2026, 9, 2)),
    # --- CDI : actives (10) ----------------------------------------------------
    # Repérée (3)
    SeedCard("CDI", SAVED, "Développeur·se Python confirmé·e (H/F) – CDI",
             "Coopérative Logicielle Ouest", "Nantes (44)", _france_travail("197XQMP")),
    SeedCard("CDI", SAVED,
             "Responsable qualité, sécurité et environnement (QSE) multi-sites – industrie "
             "agroalimentaire, déplacements fréquents en Bretagne et Pays de la Loire, "
             "véhicule de fonction",
             "Conserveries Morvan-Le Bris", "Douarnenez (29)", _indeed("7a5e0c3b91f2d864")),
    SeedCard("CDI", SAVED, "Product owner – CDI", "Studio Hélice", "Bordeaux (33)", None),
    # Postulée (4)
    SeedCard("CDI", APPLIED, "Ingénieur·e d'études et développement Java",
             "Fédération Bancaire des Vallons", "Strasbourg (67)", _france_travail("194CVHN"),
             applied_at=datetime(2026, 10, 30)),
    SeedCard("CDI", APPLIED, "Data engineer – CDI, télétravail 3 j/semaine",
             "Mutuelle Solidaire de l'Estuaire", "Nantes (44)", _indeed("c48d1a7f20e5b396"),
             applied_at=datetime(2026, 10, 26)),
    SeedCard("CDI", APPLIED, "Chef·fe de projet web",
             "Agence Festiv'Arverne", "Clermont-Ferrand (63)",
             "https://festivarverne.example/recrutement/chef-de-projet-web",
             applied_at=datetime(2026, 10, 19), extension=True),
    SeedCard("CDI", APPLIED, "Technicien·ne bureau d'études CVC",
             "Thermique Garonne Ingénierie", "Toulouse (31)", _france_travail("191LZEQ"),
             notes="Candidature spontanée doublée d'une réponse à l'offre.",
             applied_at=datetime(2026, 10, 12)),
    # Relancée (2)
    SeedCard("CDI", FOLLOWED_UP, "Développeur·se front-end React – CDI",
             "Appli'Côte", "Nice (06)", _indeed("1e7b3d9c58a0f427"),
             notes="Relance le 10/10 ; recruteuse en congés jusqu'au 20/10.",
             applied_at=datetime(2026, 9, 25)),
    SeedCard("CDI", FOLLOWED_UP, "Administrateur·rice de bases de données PostgreSQL",
             "Nuage Alpin Hébergement", "Annecy (74)", _france_travail("190HNTR"),
             applied_at=datetime(2026, 9, 18)),
    # Entretien (1)
    SeedCard("CDI", INTERVIEW, "Ingénieur·e logiciel embarqué C/C++",
             "Hélioptic Systèmes", "Lannion (22)",
             "https://helioptic.example/carrieres/embarque-cdi",
             notes="Entretien RH validé ; entretien technique le 17/11 sur site.",
             applied_at=datetime(2026, 9, 12)),
    # --- Stage : actives (8) ---------------------------------------------------
    # Repérée (2)
    SeedCard("Stage", SAVED, "Stage de 6 mois – Assistant·e chef de produit",
             "Cosmétiques Aurore Bio", "Grasse (06)", _indeed("f0a29c6e3b81d475")),
    SeedCard("Stage", SAVED, "Stage – Développement d'un outil interne de suivi des stocks",
             "Papeteries de l'Ain", "Oyonnax (01)", _france_travail("198DGSU")),
    # Postulée (3)
    SeedCard("Stage", APPLIED, "Stage ingénieur – Optimisation énergétique des bâtiments",
             "Thermique Garonne Ingénierie", "Toulouse (31)", _france_travail("195JKWE"),
             applied_at=datetime(2026, 10, 27)),
    SeedCard("Stage", APPLIED, "Stage – Chargé·e de communication interne",
             "Groupe médico-social Les Tilleuls", "Brive-la-Gaillarde (19)",
             "https://les-tilleuls-medicosocial.example/stages/communication-interne",
             applied_at=datetime(2026, 10, 20)),
    SeedCard("Stage", APPLIED, "Stage de fin d'études – Data science appliquée à la météo agricole",
             "AgroMétéo Beauce", "Chartres (28)", _indeed("9b6c4e2a0d1f7835"),
             applied_at=datetime(2026, 10, 14)),
    # Relancée (1)
    SeedCard("Stage", FOLLOWED_UP, "Stage – Assistant·e juridique",
             "Étude Bérard-Nguyen", "Lyon (69)", _france_travail("193PVBA"),
             notes="Relance le 15/10.", applied_at=datetime(2026, 9, 29)),
    # Entretien (1)
    SeedCard("Stage", INTERVIEW, "Stage – Développeur·se jeux vidéo (Godot)",
             "Pixels du Bocage", "Laval (53)", "https://pixelsdubocage.example/stage-godot",
             notes="Entretien le 12/11 à 10 h 30 : apporter le portfolio.",
             applied_at=datetime(2026, 9, 20)),
    # Acceptée (1)
    SeedCard("Stage", ACCEPTED, "Stage – Assistant·e logistique internationale",
             "Transports Mérignac Logistique", "Pointe-à-Pitre (971)", _indeed("4d2f8a6c1e9b0357"),
             notes="Convention de stage en cours de signature avec l'école.",
             applied_at=datetime(2026, 9, 5)),
    # --- Archivées (15) : le statut reste celui du moment de l'archivage ---------
    # Alternance (6)
    SeedCard("Alternance", APPLIED, "Alternance – Webmaster",
             "Office de tourisme des Trois Vallons", "Tarbes (65)", _france_travail("187EWQZ"),
             notes="Refus reçu le 01/10 : poste pourvu en interne.",
             applied_at=datetime(2026, 9, 3), archived=True),
    SeedCard("Alternance", FOLLOWED_UP, "Alternance – Assistant·e import-export",
             "Négociants Duval-Ferrand", "Libourne (33)", _indeed("8e1a5f3c0b7d2946"),
             notes="Aucune réponse après deux relances.",
             applied_at=datetime(2026, 8, 28), archived=True),
    SeedCard("Alternance", INTERVIEW, "Alternance – Développeur·se PHP / Symfony",
             "Agence Web Pastel", "Tours (37)", "https://agence-pastel.example/jobs/symfony",
             notes="Refus après entretien : profil plus expérimenté retenu.",
             applied_at=datetime(2026, 8, 20), archived=True),
    SeedCard("Alternance", SAVED, "Alternance – Opérateur·rice de production",
             "Fonderies Marchal & Cie", "Firminy (42)", _france_travail("186NKCT"),
             notes="Offre expirée avant candidature.", archived=True),
    SeedCard("Alternance", APPLIED, "Alternance – Assistant·e de direction",
             "Cabinet Lefèvre-Arnaud Expertise", "Saint-Malo (35)", None,
             applied_at=datetime(2026, 8, 12), archived=True),
    SeedCard("Alternance", ACCEPTED, "Alternance – Technicien·ne réseau fibre optique",
             "Réseaux Fibrés du Morvan", "Autun (71)", _indeed("2c7e9b4a6f0d1853"),
             notes="Acceptée puis déclinée : trop loin de l'école.",
             applied_at=datetime(2026, 7, 30), archived=True),
    # CDI (5)
    SeedCard("CDI", APPLIED, "Développeur·se .NET – CDI",
             "Fédération Bancaire des Vallons", "Metz (57)", _france_travail("188YBLD"),
             notes="Refus par mail, sans détail.",
             applied_at=datetime(2026, 8, 25), archived=True),
    SeedCard("CDI", INTERVIEW, "Lead developer – CDI",
             "Coopérative Logicielle Ouest", "Nantes (44)",
             "https://cooplogicielle-ouest.example/rejoindre/lead-dev",
             notes="Processus arrêté par l'entreprise (gel des recrutements).",
             applied_at=datetime(2026, 8, 18), archived=True),
    SeedCard("CDI", FOLLOWED_UP, "Analyste cybersécurité SOC – CDI",
             "Vigie Numérique Lyonnaise", "Lyon (69)", _indeed("6f3b0d8e2a5c9147"),
             applied_at=datetime(2026, 8, 10), archived=True),
    SeedCard("CDI", SAVED, "Responsable d'agence – CDI",
             "Transports Mérignac Logistique", "Pau (64)", _france_travail("185QMRX"),
             notes="Ne correspond pas à mon projet.", archived=True),
    SeedCard("CDI", APPLIED,
             "Ingénieur·e calcul de structures aéronautiques – CDI, habilitation défense "
             "requise, anglais courant, expérience des méthodes par éléments finis et des "
             "outils de dimensionnement",
             "Aérostructures du Lauragais", "Castelnaudary (11)", _france_travail("184UGHS"),
             notes="Refus : habilitation défense non obtenue à temps.",
             applied_at=datetime(2026, 7, 22), archived=True),
    # Stage (4)
    SeedCard("Stage", APPLIED, "Stage – Assistant·e marketing digital",
             "Cosmétiques Aurore Bio", "Montpellier (34)", _indeed("d5a8c2f6e09b4371"),
             notes="Refus.", applied_at=datetime(2026, 8, 5), archived=True),
    SeedCard("Stage", INTERVIEW, "Stage – Data analyst RH",
             "Mutuelle Solidaire de l'Estuaire", "Saint-Nazaire (44)", _france_travail("186FTWN"),
             notes="Stage pourvu entre-temps.",
             applied_at=datetime(2026, 7, 28), archived=True),
    SeedCard("Stage", SAVED, "Stage – Guide-conférencier·ère",
             "Office de tourisme des Trois Vallons", "Lourdes (65)",
             "https://trois-vallons-tourisme.example/emplois/stage-guide",
             notes="Dates incompatibles avec le calendrier de l'école.", archived=True),
    SeedCard("Stage", FOLLOWED_UP, "Stage – Technicien·ne de laboratoire",
             "Laiteries du Bocage Normand", "Vire (14)", _indeed("0b9e6a3d7c2f5148"),
             applied_at=datetime(2026, 7, 15), archived=True),
)


def _sqlite_refusal(engine: Engine) -> str | None:
    """Message de refus si la base n'est pas SQLite, None sinon.

    Contrôle sur le NOM DU MOTEUR de l'URL (`sqlite`, `sqlite+pysqlite`… → sqlite),
    celle du moteur réellement utilisé : ni la variable DATABASE_URL (absente, elle
    ne dit rien de la base visée), ni une connexion (refus AVANT toute connexion).
    Le message ne cite que le nom du moteur, jamais l'URL, qui contiendrait le mot
    de passe d'une base distante."""
    backend = engine.url.get_backend_name()
    if backend == "sqlite":
        return None
    return (
        "Refus : la base utilisée par l'application n'est pas une base SQLite "
        f"(moteur « {backend} »). Ce script ne remplit qu'une base de développement "
        "locale. Rien n'a été écrit."
    )


def _find_demo_account(db: Session) -> User | None:
    """Le compte de test, par son adresse EXACTE (unique en base), ou None."""
    return db.scalar(select(User).where(User.email == DEMO_EMAIL))


def _delete_demo_account(db: Session, user: User) -> None:
    """Supprime le compte de test : la cascade de la base emporte ses tableaux, leurs
    candidatures et ses jetons (même opération que DELETE /auth/me, sans sa
    vérification du mot de passe, qui bloquerait le reset si le mot de passe du
    compte de démo a été changé depuis l'application)."""
    db.delete(user)
    db.commit()


def _add_card(db: Session, user: User, board_id: int, card: SeedCard) -> None:
    """Crée une carte par les chemins de l'application : création (en haut de
    « Repérée »), PATCH du statut et de la date (en haut de la colonne cible),
    archivage."""
    created = create_application(
        payload=ApplicationCreate(
            board_id=board_id,
            title=card.title,
            company=card.company,
            location=card.location,
            url=card.url,
            source=card.source,
            notes=card.notes,
        ),
        current_user=user,
        db=db,
    )
    changes: dict = {}
    if card.status is not SAVED:
        changes["status"] = card.status
    if card.applied_at is not None:
        changes["applied_at"] = card.applied_at
    if changes:
        update_application(
            application_id=created.id,
            payload=ApplicationUpdate(**changes),
            current_user=user,
            db=db,
        )
    if card.archived:
        archive_application(application_id=created.id, current_user=user, db=db)


def _seed_demo_account(db: Session) -> None:
    """Crée le compte de test et ses données. En cas d'échec en cours de route, le
    compte (et tout ce qui a déjà été créé) est supprimé : pas de demi-jeu de
    données, qui bloquerait l'exécution suivante sans --reset."""
    user = User(
        email=DEMO_EMAIL,
        hashed_password=hash_password(DEMO_PASSWORD),
        is_verified=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    try:
        board_ids = {
            name: create_board(payload=BoardCreate(name=name), current_user=user, db=db).id
            for name in BOARD_NAMES
        }
        # Chaque arrivée se fait EN HAUT : l'ordre inverse donne l'ordre affiché.
        for card in reversed(CARDS):
            _add_card(db, user, board_ids[card.board], card)
    except BaseException:
        db.rollback()
        try:
            _delete_demo_account(db, user)
        except Exception as cleanup_error:  # noqa: BLE001 — l'erreur d'origine prime
            print(
                f"Échec du nettoyage du compte de test ({type(cleanup_error).__name__}) : "
                "relancez avec --reset.",
                file=sys.stderr,
            )
        raise


def _database_label(engine: Engine) -> str:
    """Fichier SQLite visé, en chemin absolu (une URL SQLite ne porte aucun secret)."""
    database = engine.url.database
    if not database or database == ":memory:":
        return "base SQLite en mémoire"
    return str(Path(database).resolve())


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python -m scripts.seed_dev",
        description=(
            f"Remplit une base SQLite de dev avec le compte de test {DEMO_EMAIL} "
            "et des données factices."
        ),
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help=f"supprime le compte {DEMO_EMAIL} et ses données, puis le recrée",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None, *, engine: Engine | None = None) -> int:
    """Point d'entrée ; renvoie le code de sortie (0 succès, 1 refus ou arrêt).

    `engine` : la base de l'application par défaut (app.database.engine, lue à
    l'appel) ; les tests y passent leur base en mémoire."""
    args = _parse_args(argv)
    if engine is None:
        engine = app.database.engine

    refusal = _sqlite_refusal(engine)
    if refusal is not None:
        print(refusal, file=sys.stderr)
        return 1

    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    with session_factory() as db:
        existing = _find_demo_account(db)
        if existing is not None and not args.reset:
            print(
                f"Le compte de test {DEMO_EMAIL} existe déjà : rien n'a été écrit. "
                "Relancez avec --reset pour le supprimer et le recréer.",
                file=sys.stderr,
            )
            return 1
        if existing is not None:
            _delete_demo_account(db, existing)
            print(f"Compte de test {DEMO_EMAIL} supprimé, avec ses données.")
        _seed_demo_account(db)

    archived = sum(card.archived for card in CARDS)
    print(
        f"Compte de test créé dans {_database_label(engine)} :\n"
        f"  email        : {DEMO_EMAIL}\n"
        f"  mot de passe : {DEMO_PASSWORD}  (dev uniquement, public)\n"
        f"  {len(BOARD_NAMES)} tableaux, {len(CARDS) - archived} candidatures actives, "
        f"{archived} archivées."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
