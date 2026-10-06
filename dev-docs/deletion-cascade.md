# Cascade de suppression (schéma + ORM)
- Déclarée à DEUX niveaux, complémentaires et non redondants :
  - SCHÉMA : `ondelete="CASCADE"` sur chaque ForeignKey (board.user_id →
    users.id, application.board_id → boards.id, security_token.user_id →
    users.id). C'est la BASE qui garantit qu'aucune ligne ne survit à son parent,
    quel que soit le chemin : ORM, script de maintenance, psql, migration. Sans
    cela, toute suppression contournant l'ORM échouait en PostgreSQL sur une
    violation de contrainte (le défaut d'une FK est NO ACTION, qui REFUSE de
    supprimer un parent encore référencé).
  - ORM : `cascade="all, delete-orphan"` sur les relations parentes. Toujours
    nécessaire — il porte la sémantique ORPHELIN (retirer un enfant de la
    collection de son parent le supprime), que la base ne connaît pas.
- `passive_deletes=True` sur ces mêmes relations articule les deux : SQLAlchemy
  ne charge plus les enfants pour les supprimer un par un, il émet UN SEUL DELETE
  sur le parent et laisse la base propager. Supprimer un user passait de
  1 SELECT par board + 1 DELETE par ligne à un unique `DELETE FROM users`.
  Comportement observable inchangé (test de non-régression dans
  test_account_deletion.py).
- SQLite n'applique PAS les clés étrangères par défaut, et le réglage est propre
  à CHAQUE CONNEXION. `app/database.py` pose donc un écouteur `connect` qui
  exécute `PRAGMA foreign_keys=ON` sur toute connexion SQLite. Sans lui, la
  cascade serait purement décorative en dev et dans les tests : supprimer un user
  laisserait des orphelins EN SILENCE, alors que la prod (PostgreSQL) irait bien.
  L'écouteur est posé sur la CLASSE `Engine`, pas sur l'instance : le moteur de
  test créé par tests/conftest.py en bénéficie sans le savoir.
- ⚠ CHANGEMENT DE SCHÉMA : toute modification de models.py exige une migration
  Alembic (cf. « Migrations »). Un changement de contrainte ou de colonne ne
  s'applique JAMAIS tout seul à une table existante, et rien ne le signale.
  Vérifié le 2026-09-25 : la prod PostgreSQL porte bien les `ON DELETE CASCADE`
  ci-dessus (les 3 FK), au même titre que cockpit.db.
