"""Environnement Alembic : relie les migrations aux modèles et à la base de l'app.

Trois choix structurants, à connaître avant de toucher à ce fichier :

1. L'URL de la base vient de `app.database.DATABASE_URL`, jamais d'alembic.ini.
   C'est la valeur EXACTE que voit l'application, déjà passée par
   `normalize_database_url` : le `postgres://` fourni par Railway est donc réécrit
   ici comme ailleurs, et aucune URL n'est dupliquée dans un fichier versionné.

2. `load_dotenv()` est appelé AVANT d'importer `app.database`, qui lit
   DATABASE_URL à l'import. Normalement c'est `app.main` qui charge le .env, mais
   Alembic n'importe pas `app.main` (il déclencherait tout le câblage FastAPI
   pour rien). Sans cet appel, Alembic viserait le SQLite par défaut au lieu de
   la base du .env. `load_dotenv` n'écrase pas une variable déjà posée : l'URL
   passée dans le shell (ex. la base de prod, le temps d'une commande) prime.

3. Une connexion peut être INJECTÉE via `config.attributes["connection"]` (motif
   documenté par Alembic). C'est ce qui permet à tests/test_migrations.py de
   migrer sa propre base en mémoire, sans variable d'environnement ni fichier.
"""

import sys
from logging.config import fileConfig

from dotenv import load_dotenv

load_dotenv()

from alembic import context  # noqa: E402
from sqlalchemy.engine import Connection, make_url  # noqa: E402

import app.models  # noqa: E402,F401  (enregistre les tables dans Base.metadata)
from app.database import DATABASE_URL, Base, engine  # noqa: E402

config = context.config

# disable_existing_loggers=False : sans cela, appeler Alembic depuis un test ou
# depuis l'app couperait en silence les loggers déjà configurés.
if config.config_file_name is not None:
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = Base.metadata


def _announce_target() -> None:
    """Affiche la base visée (mot de passe masqué) avant toute opération.

    Alembic peut modifier la production depuis un poste de dev si DATABASE_URL
    pointe dessus dans le shell. Voir la cible en clair, à chaque commande, est la
    seule protection contre une erreur de cible : à lire avant de continuer."""
    target = make_url(DATABASE_URL).render_as_string(hide_password=True)
    # Pas d'accent : la console Windows (cp1252) les affiche de travers sur stderr.
    print(f"[alembic] cible : {target}", file=sys.stderr)


def _configure(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        # Détecte aussi les changements de TYPE de colonne (ex. String(50) ->
        # String(100)), ignorés par défaut.
        compare_type=True,
        # SQLite ne sait pas faire la plupart des ALTER TABLE : le mode batch
        # recrée la table. Inutile (et non souhaité) sur PostgreSQL. Le dialecte
        # est lu sur la connexion effective, donc aussi correct en connexion
        # injectée.
        render_as_batch=connection.dialect.name == "sqlite",
    )


def run_migrations_offline() -> None:
    """Mode `--sql` : émet le SQL sur la sortie standard sans se connecter.

    Utile pour relire ce qu'une migration ferait sur PostgreSQL avant de
    l'appliquer. Aucune connexion n'est ouverte."""
    _announce_target()
    context.configure(
        url=DATABASE_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        render_as_batch=DATABASE_URL.startswith("sqlite"),
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Mode normal : se connecte à la base et applique les migrations.

    On réutilise l'`engine` de l'app (pool_pre_ping hors SQLite, PRAGMA des clés
    étrangères sous SQLite) plutôt que d'en recréer un : mêmes options de
    connexion que l'application, aucune divergence à maintenir."""
    injected = config.attributes.get("connection")
    if injected is not None:
        _configure(injected)
        with context.begin_transaction():
            context.run_migrations()
        return

    _announce_target()
    with engine.connect() as connection:
        _configure(connection)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
