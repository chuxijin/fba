"""Preserve source timing and optionally exclude answer-entry time.

Revision ID: e7f8a9b0c1d2
Revises: d6e7f8a9b0c1
"""

import sqlalchemy as sa

from alembic import op

revision = 'e7f8a9b0c1d2'
down_revision = 'd6e7f8a9b0c1'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'gongkao_practice_log',
        sa.Column('exclude_source_timing', sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column('gongkao_practice_log', sa.Column('manual_duration_seconds', sa.Integer(), nullable=True))
    op.add_column('gongkao_practice_module', sa.Column('manual_duration_seconds', sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column('gongkao_practice_module', 'manual_duration_seconds')
    op.drop_column('gongkao_practice_log', 'manual_duration_seconds')
    op.drop_column('gongkao_practice_log', 'exclude_source_timing')
