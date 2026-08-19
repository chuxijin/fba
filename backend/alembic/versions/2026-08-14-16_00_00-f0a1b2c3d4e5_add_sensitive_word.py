"""add sensitive word table

Revision ID: f0a1b2c3d4e5
Revises: e8f9a0b1c234
Create Date: 2026-08-14 16:00:00.000000
"""

import sqlalchemy as sa

from alembic import op

revision = 'f0a1b2c3d4e5'
down_revision = 'e8f9a0b1c234'
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
        'sensitive_word',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('word', sa.String(128), nullable=False, comment='敏感词'),
        sa.Column('replacement', sa.String(128), nullable=True, comment='替换词（action=replace 时生效）'),
        sa.Column('action', sa.String(16), server_default='replace', nullable=False),
        sa.Column('status', sa.String(16), server_default='active', nullable=False),
        sa.Column('remark', sa.String(255), nullable=True, comment='备注'),
        sa.Column('sort_order', sa.Integer(), server_default='0', nullable=False),
        *_base_columns(with_user_mixin=True),
        sa.CheckConstraint("action IN ('replace','block','reject')", name='ck_sensitive_word_action'),
        sa.CheckConstraint("status IN ('active','disabled')", name='ck_sensitive_word_status'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('word', 'deleted', name='uq_sensitive_word'),
        comment='敏感词表',
    )
    op.create_index('ix_sensitive_word_id', 'sensitive_word', ['id'], unique=True)
    op.create_index('ix_sensitive_word_status', 'sensitive_word', ['status'])


def downgrade() -> None:
    op.drop_table('sensitive_word')
