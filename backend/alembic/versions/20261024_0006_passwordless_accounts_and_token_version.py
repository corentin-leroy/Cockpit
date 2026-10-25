"""passwordless accounts and token version

Prépare la connexion avec Google (lot 1 : backend seul, rien de propre à Google) :

- `users.hashed_password` devient NULLABLE : NULL = compte sans mot de passe (créé
  ou lié par Google aux lots suivants ; aucun n'existe après ce lot). Un tel compte
  n'en retrouve jamais.
- `users.google_sub` (VARCHAR(255), NULL, index UNIQUE `ix_users_google_sub`) :
  identifiant Google du compte. L'index unique admet plusieurs NULL (PostgreSQL
  comme SQLite).
- `users.token_version` (INTEGER NOT NULL DEFAULT 0) : version des sessions,
  recopiée dans le JWT et comparée à chaque requête ; l'incrémenter révoque toutes
  les sessions du compte. Le défaut EN BASE (server_default) est indispensable : la
  version PRÉCÉDENTE du code sert encore pendant le déploiement et insère des
  utilisateurs sans cette colonne. `alembic check` ne compare pas les défauts :
  tests/test_migrations.py le garde.

Compatible avec la version précédente du code : elle ignore les deux nouvelles
colonnes et n'écrit jamais NULL dans hashed_password. Aucun verrou à l'upgrade :
aucune donnée n'est contrôlée ni réécrite. Sous PostgreSQL, dans une transaction :
DROP NOT NULL, deux ADD COLUMN (défaut constant : métadonnées seules depuis
PostgreSQL 11), CREATE UNIQUE INDEX.

Sous SQLite, le mode batch RECRÉE `users` : sans la garde d'alembic/env.py (clés
étrangères coupées), le DROP de l'ancienne table viderait boards, applications et
security_tokens par ON DELETE CASCADE.

Downgrade REFUSÉ tant qu'un compte n'a pas de mot de passe : NOT NULL ne pourrait
pas être rétabli, et l'ancien code planterait sur ce compte. Sinon, il supprime
google_sub (les liaisons Google sont perdues) et token_version : les sessions
révoquées REDEVIENNENT VALABLES pour l'ancien code, jusqu'à leur expiration (12 h
au plus).

Revision ID: 0006
Revises: 0005
Create Date: 2026-10-24
"""
from typing import Sequence, Union

from alembic import context, op
import sqlalchemy as sa


# Identifiants de révision, utilisés par Alembic.
revision: str = '0006'
down_revision: Union[str, Sequence[str], None] = '0005'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('google_sub', sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column('token_version', sa.Integer(), server_default=sa.text('0'), nullable=False))
        batch_op.alter_column('hashed_password',
               existing_type=sa.VARCHAR(length=255),
               nullable=True)
        batch_op.create_index(batch_op.f('ix_users_google_sub'), ['google_sub'], unique=True)


def downgrade() -> None:
    # Verrou AVANT le comptage : l'ancien code ne crée pas de compte sans mot de
    # passe, mais le nouveau, qui sert encore pendant un retour en arrière, si.
    if op.get_bind().dialect.name == 'postgresql':
        op.execute("LOCK TABLE users IN ACCESS EXCLUSIVE MODE")

    # Garde-fou. En mode `--sql` (aucune connexion) il ne peut pas s'exécuter : le
    # SQL émis sert alors uniquement à la relecture.
    if not context.is_offline_mode():
        passwordless = op.get_bind().execute(
            sa.text("SELECT count(*) FROM users WHERE hashed_password IS NULL")
        ).scalar_one()
        if passwordless:
            raise RuntimeError(
                f"Downgrade de 0006 interrompu : {passwordless} compte(s) sans mot de "
                "passe (connexion avec Google). La colonne hashed_password ne peut "
                "pas redevenir NOT NULL, et l'ancien code planterait sur ces comptes. "
                "Aucune modification n'a été appliquée."
            )

    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_users_google_sub'))
        batch_op.alter_column('hashed_password',
               existing_type=sa.VARCHAR(length=255),
               nullable=False)
        batch_op.drop_column('token_version')
        batch_op.drop_column('google_sub')
