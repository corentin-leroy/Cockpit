"""remove rejected status

Retire la valeur REJECTED de l'enum `applicationstatus` (sous-lot 2b : le statut
« Refusée » disparaît du modèle). PostgreSQL n'a pas de `DROP VALUE` pour un enum
natif : on RECRÉE le type, dans UNE transaction (DDL transactionnel) :

  1. LOCK TABLE ... ACCESS EXCLUSIVE : plus aucune écriture concurrente entre le
     garde-fou et le DDL (sinon une ligne REJECTED pourrait apparaître entre les
     deux) ;
  2. garde-fou : refuse d'aller plus loin s'il reste une ligne REJECTED ;
  3. ALTER TYPE ... RENAME TO ..._old : libère le nom ;
  4. CREATE TYPE au nouveau jeu de valeurs ;
  5. ALTER COLUMN ... TYPE ... USING status::text::... : convertit chaque ligne
     par son libellé (échouerait sur une ligne REJECTED) ;
  6. DROP TYPE ..._old : échoue s'il reste un objet dépendant, jamais en silence.

Un échec à n'importe quelle étape annule TOUT : la base reste dans son état
d'origine (pas de type _old orphelin). Sous SQLite, l'enum est un VARCHAR sans
contrainte : seul le garde-fou s'exécute.

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-26
"""
from typing import Sequence, Union

from alembic import context, op
import sqlalchemy as sa


# Identifiants de révision, utilisés par Alembic.
revision: str = '0002'
down_revision: Union[str, Sequence[str], None] = '0001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Noms des membres de l'enum Python (SQLAlchemy stocke les NOMS, pas les valeurs).
# Liste EN DUR et non importée de app.models : une migration décrit un état
# figé du schéma, elle ne doit pas changer quand le modèle évolue.
_VALUES_WITHOUT_REJECTED = ('SAVED', 'APPLIED', 'FOLLOWED_UP', 'INTERVIEW', 'ACCEPTED')
_VALUES_WITH_REJECTED = (
    'SAVED', 'APPLIED', 'FOLLOWED_UP', 'INTERVIEW', 'REJECTED', 'ACCEPTED',
)


def _is_postgresql() -> bool:
    return op.get_bind().dialect.name == 'postgresql'


def _recreate_status_type(values: Sequence[str]) -> None:
    """Remplace le type `applicationstatus` par un type portant exactement `values`
    (dans cet ordre), et y reconvertit la colonne applications.status.

    `values` vient des constantes ci-dessus, jamais d'une saisie : l'interpolation
    dans le SQL est sûre."""
    labels = ', '.join(f"'{value}'" for value in values)
    op.execute("ALTER TYPE applicationstatus RENAME TO applicationstatus_old")
    op.execute(f"CREATE TYPE applicationstatus AS ENUM ({labels})")
    op.execute(
        "ALTER TABLE applications ALTER COLUMN status "
        "TYPE applicationstatus USING status::text::applicationstatus"
    )
    op.execute("DROP TYPE applicationstatus_old")


def upgrade() -> None:
    if _is_postgresql():
        op.execute("LOCK TABLE applications IN ACCESS EXCLUSIVE MODE")

    # Garde-fou. En mode `--sql` (aucune connexion) il ne peut pas s'exécuter : le
    # SQL émis sert alors uniquement à la relecture.
    if not context.is_offline_mode():
        remaining = op.get_bind().execute(
            sa.text(
                "SELECT count(*) FROM applications "
                "WHERE CAST(status AS TEXT) = 'REJECTED'"
            )
        ).scalar_one()
        if remaining:
            raise RuntimeError(
                f"Migration 0002 interrompue : {remaining} candidature(s) en statut "
                "REJECTED. Retirer ce statut supprime la valeur de l'enum : ces "
                "lignes deviendraient illisibles. Aucune modification n'a été "
                "appliquée. Décide d'abord vers quel statut les réaffecter (ex. "
                "UPDATE applications SET status = 'APPLIED' WHERE status = "
                "'REJECTED'), puis relance la migration."
            )

    if _is_postgresql():
        _recreate_status_type(_VALUES_WITHOUT_REJECTED)


def downgrade() -> None:
    # Sans perte : les 5 valeurs du type actuel existent toutes dans le type à 6
    # valeurs, la conversion réussit pour chaque ligne. Aucune ligne ne devient
    # REJECTED. Les candidatures réaffectées avant l'upgrade ne sont PAS rétablies.
    if _is_postgresql():
        op.execute("LOCK TABLE applications IN ACCESS EXCLUSIVE MODE")
        _recreate_status_type(_VALUES_WITH_REJECTED)
