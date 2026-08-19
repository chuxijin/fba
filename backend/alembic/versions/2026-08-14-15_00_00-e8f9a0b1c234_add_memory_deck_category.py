"""add memory deck category

Revision ID: e8f9a0b1c234
Revises: e7f8a9b0c123
Create Date: 2026-08-14 15:00:00.000000
"""

import sqlalchemy as sa

from alembic import op

revision = 'e8f9a0b1c234'
down_revision = 'e7f8a9b0c123'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'memory_card_deck',
        sa.Column(
            'category_id',
            sa.BigInteger(),
            nullable=True,
            comment='所属领域分类 ID（考公/考研等）',
        ),
    )
    op.create_foreign_key(
        'fk_memory_deck_category',
        'memory_card_deck',
        'sys_category',
        ['category_id'],
        ['id'],
        ondelete='SET NULL',
    )
    op.create_index('ix_memory_deck_category', 'memory_card_deck', ['category_id'])


def downgrade() -> None:
    op.drop_index('ix_memory_deck_category', table_name='memory_card_deck')
    op.drop_constraint('fk_memory_deck_category', 'memory_card_deck', type_='foreignkey')
    op.drop_column('memory_card_deck', 'category_id')
