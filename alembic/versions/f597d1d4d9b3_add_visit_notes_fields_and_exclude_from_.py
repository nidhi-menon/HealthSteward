"""Add visit notes fields and exclude_from_prep_context

Revision ID: f597d1d4d9b3
Revises: 1579e0bef709
Create Date: 2026-02-06 15:21:29.193628

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f597d1d4d9b3'
down_revision: Union[str, Sequence[str], None] = '1579e0bef709'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add new columns to appointments
    op.add_column('appointments', sa.Column('prep_notes', sa.Text(), nullable=True))
    op.add_column('appointments', sa.Column('visit_notes', sa.Text(), nullable=True))
    op.add_column('appointments', sa.Column('visit_notes_updated_at', sa.DateTime(), nullable=True))

    # Migrate existing 'notes' data to 'prep_notes'
    op.execute("UPDATE appointments SET prep_notes = notes WHERE notes IS NOT NULL")

    # Drop old notes column
    op.drop_column('appointments', 'notes')

    # Add exclude_from_prep_context to doctors with default value
    op.add_column('doctors', sa.Column('exclude_from_prep_context', sa.Boolean(), nullable=False, server_default='0'))
    # ### end Alembic commands ###


def downgrade() -> None:
    """Downgrade schema."""
    # Remove exclude_from_prep_context from doctors
    op.drop_column('doctors', 'exclude_from_prep_context')

    # Add back the notes column
    op.add_column('appointments', sa.Column('notes', sa.TEXT(), nullable=True))

    # Migrate prep_notes data back to notes
    op.execute("UPDATE appointments SET notes = prep_notes WHERE prep_notes IS NOT NULL")

    # Drop the new columns
    op.drop_column('appointments', 'visit_notes_updated_at')
    op.drop_column('appointments', 'visit_notes')
    op.drop_column('appointments', 'prep_notes')
    # ### end Alembic commands ###
