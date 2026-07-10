"""Add app_settings table (DEC-016)

Revision ID: a1b2c3d4e5f6
Revises: 956a4ae83ec1
Create Date: 2026-07-09 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = '956a4ae83ec1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('app_settings',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('llm_provider', sa.String(length=20), nullable=True),
    sa.Column('anthropic_api_key', sa.String(length=255), nullable=True),
    sa.Column('anthropic_model', sa.String(length=100), nullable=True),
    sa.Column('ollama_base_url', sa.String(length=255), nullable=True),
    sa.Column('ollama_model', sa.String(length=100), nullable=True),
    sa.Column('custom_llm_base_url', sa.String(length=255), nullable=True),
    sa.Column('custom_llm_api_key', sa.String(length=255), nullable=True),
    sa.Column('custom_llm_model', sa.String(length=100), nullable=True),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('app_settings')
