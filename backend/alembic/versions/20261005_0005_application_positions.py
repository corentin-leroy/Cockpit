"""application positions

Ajoute `applications.position` (INTEGER, nullable) : le rang d'une carte dans sa
colonne du kanban (même tableau, même statut, active), 0 = en haut. NULL pour une
archivée.

Numérotation initiale : RIEN NE DOIT BOUGER À L'ÉCRAN au déploiement. Jusqu'ici la
liste était triée par `updated_at` décroissant ; chaque colonne est donc numérotée
0..n-1 dans cet ordre exact. `id DESC` ne fait que départager deux `updated_at`
égaux, que l'ancien tri laissait au hasard du moteur. Les archivées restent à NULL.
`updated_at` n'est pas modifié (UPDATE en SQL brut, aucun `onupdate` de l'ORM).

Dans UNE transaction (DDL transactionnel sous PostgreSQL) :

  1. LOCK TABLE ... ACCESS EXCLUSIVE : aucune écriture concurrente (l'ancienne
     version du code sert pendant le pre-deploy) entre l'ajout de la colonne, la
     numérotation et le commit ;
  2. ADD COLUMN position INTEGER (nullable, sans défaut : métadonnées seules) ;
  3. numérotation des actives par ROW_NUMBER() (PostgreSQL et SQLite >= 3.25 ;
     UPDATE ... FROM : SQLite >= 3.33, 3.50 ici).

Volontairement SANS contrainte (ni NOT NULL, ni CHECK « archivée ⟺ NULL », ni
unicité) : la version PRÉCÉDENTE du code continue de servir pendant le déploiement,
et plus longtemps si le nouveau échoue son healthcheck. Elle crée des candidatures
sans position et change des statuts sans renuméroter : une contrainte ferait
échouer ses écritures en 500. Le nouveau code trie les NULL en tête et renumérote
toute colonne qu'il touche : ces lignes se réparent d'elles-mêmes. (L'unicité ne
serait de toute façon pas déclarable : PostgreSQL comme SQLite la vérifient ligne
par ligne, une renumérotation la violerait en cours d'instruction.)

Le downgrade supprime la colonne : aucune autre donnée n'est touchée, seul l'ordre
choisi par l'utilisateur est perdu (inhérent au retour en arrière ; l'ancien code
retrie par updated_at).

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-05
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0005'
down_revision: Union[str, Sequence[str], None] = '0004'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    if op.get_bind().dialect.name == 'postgresql':
        op.execute("LOCK TABLE applications IN ACCESS EXCLUSIVE MODE")

    with op.batch_alter_table('applications', schema=None) as batch_op:
        batch_op.add_column(sa.Column('position', sa.Integer(), nullable=True))

    op.execute(
        """
        UPDATE applications
        SET position = ranked.rank
        FROM (
            SELECT id,
                   ROW_NUMBER() OVER (
                       PARTITION BY board_id, status
                       ORDER BY updated_at DESC, id DESC
                   ) - 1 AS rank
            FROM applications
            WHERE archived_at IS NULL
        ) AS ranked
        WHERE applications.id = ranked.id
        """
    )


def downgrade() -> None:
    with op.batch_alter_table('applications', schema=None) as batch_op:
        batch_op.drop_column('position')
