"""Configuration de la base de données.

Le backend fonctionne avec SQLite ET PostgreSQL, selon la seule valeur de
DATABASE_URL :
  - dev / tests : sqlite:///./cockpit.db (zéro config, fichier local)
  - production  : postgresql+psycopg://user:motdepasse@hote:5432/base

Aucun code métier n'a à savoir laquelle est active : SQLAlchemy absorbe la
différence. Ce module concentre les deux seuls points qui, eux, en dépendent —
la normalisation de l'URL et les options de connexion propres à chaque moteur.
"""

import os
import sqlite3

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker


def normalize_database_url(url: str) -> str:
    """Ramène une URL PostgreSQL au format attendu par SQLAlchemy + psycopg v3.

    Deux réécritures, pour deux raisons distinctes :

    1. `postgres://` → beaucoup d'hébergeurs (Railway, Heroku, Render…) exposent
       une DATABASE_URL avec ce préfixe. C'est un alias historique que SQLAlchemy
       ne reconnaît PLUS depuis la 1.4 : tel quel, le démarrage échoue sur
       « Can't load plugin: sqlalchemy.dialects:postgres ». On ne peut donc pas
       se contenter de brancher l'URL fournie par l'hébergeur.

    2. `postgresql://` → préfixe valide, mais SANS driver explicite SQLAlchemy
       retombe sur son défaut historique, psycopg2, qui n'est pas installé ici
       (on installe psycopg v3). On force donc `+psycopg`.

    Une URL déjà explicite (`postgresql+psycopg://`, `sqlite://`, ou tout autre
    driver choisi sciemment) est renvoyée INCHANGÉE : on ne remplace jamais un
    driver que l'appelant a demandé.
    """
    if url.startswith("postgres://"):
        return "postgresql+psycopg://" + url.removeprefix("postgres://")
    if url.startswith("postgresql://"):
        return "postgresql+psycopg://" + url.removeprefix("postgresql://")
    return url


DATABASE_URL = normalize_database_url(
    os.getenv("DATABASE_URL", "sqlite:///./cockpit.db")
)

# Détection du moteur par le préfixe de l'URL, après normalisation.
IS_SQLITE = DATABASE_URL.startswith("sqlite")

# Options passées telles quelles au driver : elles sont SPÉCIFIQUES à chacun.
# `check_same_thread` appartient au module sqlite3 de la stdlib ; la passer à
# psycopg ferait échouer la connexion (paramètre inconnu). D'où le branchement.
# Côté SQLite elle reste nécessaire : FastAPI peut servir les requêtes depuis
# plusieurs threads, et sqlite3 refuse par défaut qu'une connexion en change.
_connect_args: dict = {"check_same_thread": False} if IS_SQLITE else {}

# pool_pre_ping : uniquement utile hors SQLite. Les hébergeurs managés coupent
# les connexions PostgreSQL restées inactives ; sans ce test préalable, la
# première requête après une période creuse échoue sur une connexion morte
# ("server closed the connection unexpectedly"). Le ping la remplace en silence.
_engine_kwargs: dict = {} if IS_SQLITE else {"pool_pre_ping": True}

engine = create_engine(DATABASE_URL, connect_args=_connect_args, **_engine_kwargs)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@event.listens_for(Engine, "connect")
def _enable_sqlite_foreign_keys(dbapi_connection, connection_record) -> None:
    """Active la vérification des clés étrangères sur chaque connexion SQLITE.

    SQLite embarque le support des clés étrangères mais le laisse DÉSACTIVÉ par
    défaut, pour compatibilité historique — et le réglage est propre à chaque
    connexion, jamais persisté dans le fichier. Sans ce PRAGMA, une contrainte
    `ON DELETE CASCADE` déclarée dans le schéma est purement décorative : SQLite
    l'accepte, la stocke… et ne l'applique pas.

    Ce n'était sans conséquence que tant que la cascade vivait uniquement dans
    SQLAlchemy. Depuis que les relations parentes portent `passive_deletes=True`,
    l'ORM n'émet plus les DELETE des enfants et DÉLÈGUE à la base : sans ce
    PRAGMA, supprimer un utilisateur laisserait en silence ses tableaux, ses
    candidatures et ses jetons orphelins, avec des `user_id` pointant dans le
    vide. La production (PostgreSQL, qui applique toujours ses contraintes) irait
    bien, les tests passeraient à côté du bug : exactement le genre d'écart entre
    moteurs que ce module a pour rôle d'absorber.

    L'écouteur est posé sur la CLASSE Engine, pas sur l'instance `engine`
    ci-dessus : le moteur de test (tests/conftest.py) en crée un second, qui doit
    bénéficier du même réglage sans avoir à le savoir. Le test isinstance limite
    l'exécution aux connexions SQLite — PostgreSQL applique nativement ses clés
    étrangères et ne connaît pas cette instruction.
    """
    if isinstance(dbapi_connection, sqlite3.Connection):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


class Base(DeclarativeBase):
    """Classe de base dont héritent tous les modèles ORM."""


def get_db():
    """Dépendance FastAPI : fournit une session DB par requête, puis la ferme.

    Usage dans un endpoint :  db: Session = Depends(get_db)
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
