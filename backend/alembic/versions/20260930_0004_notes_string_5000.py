"""notes string 5000

Lot 3e : passe `applications.notes` de TEXT (sans limite en base) à VARCHAR(5000).
Jusqu'ici la borne de 5000 caractères n'était appliquée que par Pydantic, au
niveau de l'API : tout ce qui la contourne (script de maintenance, SQL manuel,
futur import) n'était pas protégé. Désormais la base impose elle-même la limite,
comme pour les autres champs texte.

Dans UNE transaction (DDL transactionnel sous PostgreSQL) :

  1. LOCK TABLE ... ACCESS EXCLUSIVE : plus aucune écriture concurrente entre le
     garde-fou et le DDL (sinon une note trop longue pourrait apparaître entre
     les deux) ;
  2. garde-fou : refuse d'aller plus loin si une note dépasse déjà 5000
     caractères. Il ne TRONQUE JAMAIS : perdre le bout d'une note en silence
     serait une perte de données, la décision de la raccourcir revient à
     l'utilisateur ;
  3. ALTER COLUMN ... TYPE VARCHAR(5000).

Un échec à n'importe quelle étape annule TOUT : la base reste dans son état
d'origine. Sous SQLite, les longueurs de VARCHAR ne sont pas appliquées (le mode
batch recrée la table) : seul le garde-fou protège, et le schéma est aligné sur
les modèles pour `alembic check`.

La valeur 5000 est écrite EN DUR, jamais importée de app.limits : une migration
décrit un état figé du schéma, elle ne doit pas changer quand une constante
évolue. Si MAX_NOTES_LENGTH change, `alembic check` échoue (le modèle ne
correspond plus au schéma migré) et impose une nouvelle révision.

Le downgrade revient à TEXT : sans perte possible, tout VARCHAR(5000) tient dans
un TEXT.

Revision ID: 0004
Revises: 0003
Create Date: 2026-09-30
"""
from typing import Sequence, Union

from alembic import context, op
import sqlalchemy as sa


# Identifiants de révision, utilisés par Alembic.
revision: str = '0004'
down_revision: Union[str, Sequence[str], None] = '0003'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# En dur, voir la docstring : état figé du schéma, pas la constante de limits.py.
_NOTES_MAX_LENGTH = 5000


def upgrade() -> None:
    if op.get_bind().dialect.name == 'postgresql':
        op.execute("LOCK TABLE applications IN ACCESS EXCLUSIVE MODE")

    # Garde-fou. En mode `--sql` (aucune connexion) il ne peut pas s'exécuter : le
    # SQL émis sert alors uniquement à la relecture. length() compte des
    # CARACTÈRES sous PostgreSQL comme sous SQLite, comme la borne Pydantic.
    if not context.is_offline_mode():
        too_long, longest = op.get_bind().execute(
            sa.text(
                "SELECT count(*), max(length(notes)) FROM applications "
                f"WHERE length(notes) > {_NOTES_MAX_LENGTH}"
            )
        ).one()
        if too_long:
            raise RuntimeError(
                f"Migration 0004 interrompue : {too_long} candidature(s) ont des "
                f"notes de plus de {_NOTES_MAX_LENGTH} caractères (la plus longue : "
                f"{longest}). La colonne passerait à VARCHAR({_NOTES_MAX_LENGTH}) : "
                "ces notes ne tiendraient plus, et les tronquer en silence serait "
                "une perte de données. Aucune modification n'a été appliquée. "
                "Raccourcis d'abord ces notes (repère-les avec : SELECT id, "
                "length(notes) FROM applications WHERE length(notes) > "
                f"{_NOTES_MAX_LENGTH}), puis relance la migration."
            )

    with op.batch_alter_table('applications', schema=None) as batch_op:
        batch_op.alter_column(
            'notes',
            existing_type=sa.Text(),
            type_=sa.String(length=_NOTES_MAX_LENGTH),
            existing_nullable=True,
        )


def downgrade() -> None:
    with op.batch_alter_table('applications', schema=None) as batch_op:
        batch_op.alter_column(
            'notes',
            existing_type=sa.String(length=_NOTES_MAX_LENGTH),
            type_=sa.Text(),
            existing_nullable=True,
        )
