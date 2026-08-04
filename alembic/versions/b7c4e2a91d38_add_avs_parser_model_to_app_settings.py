"""add avs_parser_model to app_settings

Revision ID: b7c4e2a91d38
Revises: 73a1532778f1
Create Date: 2026-08-03 09:40:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b7c4e2a91d38'
down_revision: Union[str, Sequence[str], None] = '73a1532778f1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Nullable with no server_default, matching every other AppSettings
    # overlay column: NULL means "fall back to the env default"
    # (config.py's avs_parser_model), so existing rows need no backfill —
    # they keep behaving exactly as they did before this column existed.
    op.add_column(
        'app_settings',
        sa.Column('avs_parser_model', sa.String(length=100), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('app_settings', 'avs_parser_model')
