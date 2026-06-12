"""Configuration de la base de données.

SQLite pour démarrer (zéro config), migration vers PostgreSQL prévue
quand on déploiera en production — SQLAlchemy rend ce changement quasi
transparent : seule DATABASE_URL changera.
"""

import os

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./cockpit.db")

# check_same_thread=False : spécifique à SQLite, nécessaire car FastAPI
# peut traiter les requêtes sur plusieurs threads.
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


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
