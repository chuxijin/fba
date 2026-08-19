"""add memory card module

Revision ID: d6e7f8a9b012
Revises: c5d6e7f8a901
Create Date: 2026-08-14 10:00:00.000000
"""

import sqlalchemy as sa

from alembic import op
from sqlalchemy.dialects import postgresql

revision = 'd6e7f8a9b012'
down_revision = 'c5d6e7f8a901'
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
        'memory_card_deck',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('code', sa.String(64), nullable=False, comment='稳定业务编码'),
        sa.Column('name', sa.String(120), nullable=False, comment='卡组名称'),
        sa.Column('description', sa.Text(), nullable=True, comment='卡组描述'),
        sa.Column('scope', sa.String(16), server_default='system', nullable=False),
        sa.Column('owner_id', sa.BigInteger(), nullable=True, comment='私人卡组所有者，公共卡组为空'),
        sa.Column('status', sa.String(16), server_default='active', nullable=False),
        sa.Column('daily_new_limit', sa.Integer(), server_default='20', nullable=False),
        sa.Column('daily_review_limit', sa.Integer(), server_default='200', nullable=False),
        sa.Column('sort_order', sa.Integer(), server_default='0', nullable=False),
        sa.Column('settings', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        *_base_columns(with_user_mixin=True),
        sa.CheckConstraint("scope IN ('system','personal')", name='ck_memory_deck_scope'),
        sa.CheckConstraint("status IN ('active','disabled','archived')", name='ck_memory_deck_status'),
        sa.ForeignKeyConstraint(['owner_id'], ['sys_user.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('code', 'deleted', name='uq_memory_deck_code'),
        comment='记忆卡组表',
    )
    op.create_index('ix_memory_card_deck_id', 'memory_card_deck', ['id'], unique=True)
    op.create_index('ix_memory_deck_scope_status', 'memory_card_deck', ['scope', 'status'])
    op.create_index('ix_memory_deck_owner', 'memory_card_deck', ['owner_id'])

    op.create_table(
        'memory_card',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('deck_id', sa.BigInteger(), nullable=False, comment='卡组 ID'),
        sa.Column('code', sa.String(64), nullable=False, comment='稳定业务编码'),
        sa.Column('title', sa.String(255), nullable=False, comment='卡片标题'),
        sa.Column('card_type', sa.String(16), server_default='cloze', nullable=False),
        sa.Column('response_mode', sa.String(16), server_default='input', nullable=False),
        sa.Column('current_revision_id', sa.BigInteger(), nullable=True, comment='当前发布版本 ID'),
        sa.Column('status', sa.String(16), server_default='active', nullable=False),
        sa.Column('sort_order', sa.Integer(), server_default='0', nullable=False),
        *_base_columns(with_user_mixin=True),
        sa.CheckConstraint("card_type IN ('cloze','correction')", name='ck_memory_card_type'),
        sa.CheckConstraint(
            "response_mode IN ('reveal','input','choice','select_replace')",
            name='ck_memory_card_response_mode',
        ),
        sa.CheckConstraint("status IN ('active','disabled','archived')", name='ck_memory_card_status'),
        sa.ForeignKeyConstraint(['deck_id'], ['memory_card_deck.id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('code', 'deleted', name='uq_memory_card_code'),
        comment='记忆卡表',
    )
    op.create_index('ix_memory_card_id', 'memory_card', ['id'], unique=True)
    op.create_index('ix_memory_card_deck_status', 'memory_card', ['deck_id', 'status'])

    op.create_table(
        'memory_card_revision',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('card_id', sa.BigInteger(), nullable=False, comment='卡片 ID'),
        sa.Column('revision_no', sa.Integer(), nullable=False, comment='版本号，从 1 递增'),
        sa.Column('content', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('content_hash', sa.String(64), nullable=False),
        sa.Column('status', sa.String(16), server_default='published', nullable=False),
        sa.Column('published_by', sa.BigInteger(), nullable=True, comment='发布人 ID'),
        sa.Column('published_time', sa.DateTime(timezone=True), nullable=True, comment='发布时间'),
        *_base_columns(with_user_mixin=True),
        sa.CheckConstraint('revision_no > 0', name='ck_memory_revision_no'),
        sa.CheckConstraint("status IN ('draft','published','retired')", name='ck_memory_revision_status'),
        sa.ForeignKeyConstraint(['card_id'], ['memory_card.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['published_by'], ['sys_user.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('card_id', 'revision_no', name='uq_memory_revision_no'),
        comment='记忆卡不可变内容版本表',
    )
    op.create_index('ix_memory_card_revision_id', 'memory_card_revision', ['id'], unique=True)
    op.create_index('ix_memory_revision_card_status', 'memory_card_revision', ['card_id', 'status', 'revision_no'])
    op.create_index('ix_memory_revision_hash', 'memory_card_revision', ['content_hash'])

    op.create_table(
        'memory_card_subscription',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.BigInteger(), nullable=False, comment='用户 ID'),
        sa.Column('deck_id', sa.BigInteger(), nullable=False, comment='卡组 ID'),
        sa.Column('status', sa.String(16), server_default='active', nullable=False),
        sa.Column('daily_new_limit', sa.Integer(), nullable=True),
        sa.Column('daily_review_limit', sa.Integer(), nullable=True),
        *_base_columns(),
        sa.CheckConstraint("status IN ('active','paused')", name='ck_memory_subscription_status'),
        sa.ForeignKeyConstraint(['user_id'], ['sys_user.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['deck_id'], ['memory_card_deck.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'deck_id', 'deleted', name='uq_memory_subscription'),
        comment='用户卡组订阅表',
    )
    op.create_index('ix_memory_card_subscription_id', 'memory_card_subscription', ['id'], unique=True)
    op.create_index('ix_memory_subscription_user', 'memory_card_subscription', ['user_id', 'status'])

    op.create_table(
        'memory_card_user_state',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.BigInteger(), nullable=False, comment='用户 ID'),
        sa.Column('card_id', sa.BigInteger(), nullable=False, comment='卡片 ID'),
        sa.Column('due', sa.DateTime(timezone=True), nullable=False, comment='下次到期时间'),
        sa.Column('status', sa.String(16), server_default='active', nullable=False),
        sa.Column('state', sa.SmallInteger(), server_default='0', nullable=False),
        sa.Column('step', sa.SmallInteger(), server_default='0', nullable=True),
        sa.Column('stability', sa.Float(), nullable=True),
        sa.Column('difficulty', sa.Float(), nullable=True),
        sa.Column('last_review', sa.DateTime(timezone=True), nullable=True, comment='上次复习时间'),
        sa.Column('learned_revision_id', sa.BigInteger(), nullable=True, comment='记忆状态基于的卡片版本 ID'),
        sa.Column('review_count', sa.Integer(), server_default='0', nullable=False),
        sa.Column('lapse_count', sa.Integer(), server_default='0', nullable=False),
        sa.Column('last_rating', sa.SmallInteger(), nullable=True, comment='最近评分 1-4'),
        *_base_columns(),
        sa.CheckConstraint("status IN ('active','suspended')", name='ck_memory_state_status'),
        sa.CheckConstraint('state BETWEEN 0 AND 3', name='ck_memory_state_fsrs'),
        sa.CheckConstraint('review_count >= 0 AND lapse_count >= 0', name='ck_memory_state_counts'),
        sa.CheckConstraint('last_rating IS NULL OR last_rating BETWEEN 1 AND 4', name='ck_memory_state_rating'),
        sa.ForeignKeyConstraint(['user_id'], ['sys_user.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['card_id'], ['memory_card.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'card_id', 'deleted', name='uq_memory_user_card'),
        comment='用户卡片 FSRS 记忆状态表',
    )
    op.create_index('ix_memory_card_user_state_id', 'memory_card_user_state', ['id'], unique=True)
    op.create_index('ix_memory_state_user_due', 'memory_card_user_state', ['user_id', 'status', 'due'])

    op.create_table(
        'memory_card_review_log',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.BigInteger(), nullable=False, comment='用户 ID'),
        sa.Column('card_id', sa.BigInteger(), nullable=False, comment='卡片 ID'),
        sa.Column('idempotency_key', sa.String(128), nullable=False, comment='客户端幂等键'),
        sa.Column('rating', sa.SmallInteger(), nullable=False, comment='评分(1 Again 2 Hard 3 Good 4 Easy)'),
        sa.Column('revision_id', sa.BigInteger(), nullable=True, comment='复习时的卡片版本 ID'),
        sa.Column('session_key', sa.String(64), nullable=True, comment='学习会话标识'),
        sa.Column('check_result', sa.String(16), server_default='undetermined', nullable=False),
        sa.Column('response_data', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('revealed', sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column('duration_ms', sa.BigInteger(), server_default='0', nullable=False),
        sa.Column('prev_state', sa.SmallInteger(), nullable=True),
        sa.Column('next_state', sa.SmallInteger(), server_default='0', nullable=False),
        sa.Column('prev_due', sa.DateTime(timezone=True), nullable=True),
        sa.Column('next_due', sa.DateTime(timezone=True), nullable=True),
        sa.Column('prev_stability', sa.Float(), nullable=True),
        sa.Column('next_stability', sa.Float(), nullable=True),
        sa.Column('prev_difficulty', sa.Float(), nullable=True),
        sa.Column('next_difficulty', sa.Float(), nullable=True),
        sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=False, comment='复习时间'),
        *_base_columns(),
        sa.CheckConstraint("check_result IN ('correct','wrong','undetermined')", name='ck_memory_review_check_result'),
        sa.CheckConstraint('rating BETWEEN 1 AND 4', name='ck_memory_review_rating'),
        sa.CheckConstraint('duration_ms >= 0', name='ck_memory_review_duration'),
        sa.ForeignKeyConstraint(['user_id'], ['sys_user.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['card_id'], ['memory_card.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'idempotency_key', 'deleted', name='uq_memory_review_idempotency'),
        comment='记忆卡复习日志表',
    )
    op.create_index('ix_memory_card_review_log_id', 'memory_card_review_log', ['id'], unique=True)
    op.create_index('ix_memory_review_user_time', 'memory_card_review_log', ['user_id', 'reviewed_at'])
    op.create_index('ix_memory_review_user_card', 'memory_card_review_log', ['user_id', 'card_id'])


def downgrade() -> None:
    op.drop_table('memory_card_review_log')
    op.drop_table('memory_card_user_state')
    op.drop_table('memory_card_subscription')
    op.drop_table('memory_card_revision')
    op.drop_table('memory_card')
    op.drop_table('memory_card_deck')
