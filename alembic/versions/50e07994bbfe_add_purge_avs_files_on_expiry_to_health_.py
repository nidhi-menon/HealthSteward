"""add purge_avs_files_on_expiry to health_profiles

Opt-in flag, set at soft-delete time, for whether a profile's
data/avs/<profile_id>/ subfolder should be removed once the profile
actually purges (issue #49, DEC-030).

Revision ID: 50e07994bbfe
Revises: c8f2b41d7e93
Create Date: 2026-08-05 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '50e07994bbfe'
down_revision: Union[str, Sequence[str], None] = 'c8f2b41d7e93'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # server_default='0' so existing rows backfill to the safe default (keep
    # files) without a separate data migration; the column is still declared
    # NOT NULL going forward like the ORM model expects.
    op.add_column(
        'health_profiles',
        sa.Column(
            'purge_avs_files_on_expiry',
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('health_profiles', 'purge_avs_files_on_expiry')
