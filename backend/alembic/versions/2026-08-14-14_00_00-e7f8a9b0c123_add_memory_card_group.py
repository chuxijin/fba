"""add memory card group hierarchy

Revision ID: e7f8a9b0c123
Revises: d6e7f8a9b012
Create Date: 2026-08-14 14:00:00.000000
"""

import sqlalchemy as sa

from alembic import op

revision = 'e7f8a9b0c123'
down_revision = 'd6e7f8a9b012'
branch_labels = None
depends_on = None


def _base_columns(*, with_user_mixin: bool = False) -> list[sa.Column]:
    columns = [
        sa.Column('created_time', sa.DateTime(timezone=True), nullable=False, comment='创建时间'),
        sa.Column('updated_time', sa.DateTime(timezone=True), nullable=True, comment='更新时间'),
        sa.Column('deleted', sa.BigInteger(), server_default='0', nullable=False, comment='是否已删除'),
        sa.Column('deleted_time', sa.DateTime(timezone=True), nullable=True, comment='删除时间'),
    ]
    if with_user_mixin:
        columns[0:0] = [
            sa.Column('created_by', sa.BigInteger(), nullable=False, comment='创建者'),
            sa.Column('updated_by', sa.BigInteger(), nullable=True, comment='修改者'),
        ]
    return columns


def upgrade() -> None:
    op.create_table(
        'memory_card_group',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('deck_id', sa.BigInteger(), nullable=False, comment='卡组 ID'),
        sa.Column('name', sa.String(120), nullable=False, comment='分组名称（章/节）'),
        sa.Column('parent_id', sa.BigInteger(), nullable=True, comment='父分组 ID，空为卡组一级分组'),
        sa.Column('sort_order', sa.Integer(), server_default='0', nullable=False),
        sa.Column('status', sa.String(16), server_default='active', nullable=False),
        *_base_columns(with_user_mixin=True),
        sa.CheckConstraint("status IN ('active','disabled','archived')", name='ck_memory_group_status'),
        sa.ForeignKeyConstraint(['deck_id'], ['memory_card_deck.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['parent_id'], ['memory_card_group.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        comment='记忆卡分组表',
    )
    op.create_index('ix_memory_card_group_id', 'memory_card_group', ['id'], unique=True)
    op.create_index('ix_memory_group_deck_parent', 'memory_card_group', ['deck_id', 'parent_id', 'sort_order'])
    op.create_index('ix_memory_group_parent', 'memory_card_group', ['parent_id'])

    op.add_column(
        'memory_card',
        sa.Column(
            'group_id',
            sa.BigInteger(),
            nullable=True,
            comment='所属分组（章/节）ID，空为卡组根目录',
        ),
    )
    op.create_foreign_key('fk_memory_card_group', 'memory_card', 'memory_card_group', ['group_id'], ['id'], ondelete='SET NULL')
    op.create_index('ix_memory_card_group', 'memory_card', ['deck_id', 'group_id'])


def downgrade() -> None:
    op.drop_index('ix_memory_card_group', table_name='memory_card')
    op.drop_constraint('fk_memory_card_group', 'memory_card', type_='foreignkey')
    op.drop_column('memory_card', 'group_id')
    op.drop_table('memory_card_group')
