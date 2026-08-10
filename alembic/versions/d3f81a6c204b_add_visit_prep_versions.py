"""add visit_prep_versions

Revision ID: d3f81a6c204b
Revises: 50e07994bbfe
Create Date: 2026-08-08 09:40:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd3f81a6c204b'
down_revision: Union[str, Sequence[str], None] = '50e07994bbfe'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema.

    Purely additive (issue #54): a new table, no change to `visit_preps`
    itself, so existing rows and every current reader are untouched. There is
    deliberately no backfill — prior generations were overwritten in place
    before this table existed and are simply gone; inventing a "version 1"
    row from the current content would fabricate a history that never
    happened, which is worse than an empty one.
    """
    op.create_table(
        'visit_prep_versions',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('visit_prep_id', sa.String(length=36), nullable=False),
        sa.Column('version_number', sa.Integer(), nullable=False),
        sa.Column('generated_questions', sa.JSON(), nullable=True),
        sa.Column('context_summary', sa.Text(), nullable=True),
        sa.Column('used_fallback', sa.Boolean(), nullable=False),
        sa.Column('content_updated_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['visit_prep_id'], ['visit_preps.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    # Just the FK column. A composite (visit_prep_id, version_number) index
    # was considered and dropped: the read path returns every version for one
    # prep and there will be a handful of them, so it would buy nothing and
    # would drift from the ORM metadata, which is exactly the kind of
    # difference that makes a future autogenerate diff noisy.
    op.create_index(
        op.f('ix_visit_prep_versions_visit_prep_id'),
        'visit_prep_versions',
        ['visit_prep_id'],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema.

    Drops the table and every snapshot in it. That is real data loss, but the
    alternative (leaving an orphaned table behind) is worse — and the content
    still exists as whatever `visit_preps` currently holds for the newest
    version.
    """
    op.drop_index(op.f('ix_visit_prep_versions_visit_prep_id'), table_name='visit_prep_versions')
    op.drop_table('visit_prep_versions')
