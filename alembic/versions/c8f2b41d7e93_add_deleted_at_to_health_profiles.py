"""add deleted_at to health_profiles

Soft-delete with a 30-day recovery window (issue #50, DEC-027).

Revision ID: c8f2b41d7e93
Revises: b7c4e2a91d38
Create Date: 2026-08-04 09:40:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c8f2b41d7e93'
down_revision: Union[str, Sequence[str], None] = 'b7c4e2a91d38'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Nullable with no server_default: NULL is exactly the value existing rows
    # should have (every profile that exists today is live, by definition),
    # so no backfill is needed and no default has to be dropped afterwards.
    op.add_column(
        'health_profiles',
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema.

    Note: downgrading makes any soft-deleted profile visible again rather
    than deleting it. That is the safe direction — the alternative would be
    hard-deleting real patient data during a schema rollback.
    """
    op.drop_column('health_profiles', 'deleted_at')
