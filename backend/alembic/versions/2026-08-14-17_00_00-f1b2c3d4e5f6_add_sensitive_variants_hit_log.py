"""add sensitive word variants and hit log

Revision ID: f1b2c3d4e5f6
Revises: f0a1b2c3d4e5
Create Date: 2026-08-14 17:00:00.000000
"""

import sqlalchemy as sa

from alembic import op
from sqlalchemy.dialects import postgresql

revision = 'f1b2c3d4e5f6'
down_revision = 'f0a1b2c3d4e5'
branch_labels = None
depends_on = None


def _base_columns() -> list[sa.Column]:
    return [
        sa.Column('created_time', sa.DateTime(timezone=True), nullable=False, comment='创建时间'),
        sa.Column('updated_time', sa.DateTime(timezone=True), nullable=True, comment='更新时间'),
        sa.Column('deleted', sa.BigInteger(), server_default='0', nullable=False, comment='是否已删除'),
        sa.Column('deleted_time', sa.DateTime(timezone=True), nullable=True, comment='删除时间'),
    ]


def upgrade() -> None:
    op.add_column(
        'sensitive_word',
        sa.Column(
            'variants',
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment='变体词库（拼音/谐音/缩写）',
        ),
    )

    op.create_table(
        'sensitive_hit_log',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.BigInteger(), nullable=False, comment='触发者用户 ID'),
        sa.Column('word', sa.String(128), nullable=False, comment='敏感词快照'),
        sa.Column('keyword', sa.String(128), nullable=False, comment='实际命中的词/变体'),
        sa.Column('word_id', sa.BigInteger(), nullable=True, comment='敏感词 ID'),
        sa.Column('action', sa.String(16), server_default='replace', nullable=False),
        sa.Column('replacement', sa.String(128), nullable=True, comment='替换词快照'),
        sa.Column('hit_count', sa.Integer(), server_default='1', nullable=False),
        sa.Column('target_type', sa.String(32), nullable=True, comment='命中内容类型，如 memory_card'),
        sa.Column('target_id', sa.BigInteger(), nullable=True, comment='命中内容 ID'),
        sa.Column('snippet', sa.String(512), nullable=True, comment='命中内容摘要'),
        *_base_columns(),
        sa.ForeignKeyConstraint(['word_id'], ['sensitive_word.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        comment='敏感词命中日志表',
    )
    op.create_index('ix_sensitive_hit_log_id', 'sensitive_hit_log', ['id'], unique=True)
    op.create_index('ix_sensitive_hit_user_time', 'sensitive_hit_log', ['user_id', 'created_time'])
    op.create_index('ix_sensitive_hit_word', 'sensitive_hit_log', ['word_id'])
    op.create_index('ix_sensitive_hit_target', 'sensitive_hit_log', ['target_type', 'target_id'])


def downgrade() -> None:
    op.drop_table('sensitive_hit_log')
    op.drop_column('sensitive_word', 'variants')
