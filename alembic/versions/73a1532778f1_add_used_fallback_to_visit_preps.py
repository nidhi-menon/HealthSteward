"""add used_fallback to visit_preps

Revision ID: 73a1532778f1
Revises: a1b2c3d4e5f6
Create Date: 2026-07-20 17:34:35.593505

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '73a1532778f1'
down_revision: Union[str, Sequence[str], None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # NOT `appointments.id` NOT NULL — that's spurious autogenerate noise
    # from SQLite's PK-column reflection, unrelated to this migration.
    #
    # server_default='0' backfills existing rows (none of which used the
    # fallback path, since the column didn't exist yet); dropped after so
    # the ORM's Python-side default (not a DB default) governs new rows.
    op.add_column(
        'visit_preps',
        sa.Column('used_fallback', sa.Boolean(), nullable=False, server_default='0'),
    )
    with op.batch_alter_table('visit_preps') as batch_op:
        batch_op.alter_column('used_fallback', server_default=None)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('visit_preps', 'used_fallback')
