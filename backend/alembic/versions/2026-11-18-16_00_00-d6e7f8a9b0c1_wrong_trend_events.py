"""Record real wrong-book mastery transitions; never backfill mutable state.

Revision ID: d6e7f8a9b0c1
Revises: c5d6e7f8a9b0
"""

import sqlalchemy as sa

from alembic import op

from backend.utils.timezone import timezone

revision = 'd6e7f8a9b0c1'
down_revision = 'c5d6e7f8a9b0'
branch_labels = None
depends_on = None


def _base_columns() -> list[sa.Column]:
    return [
        sa.Column('id', sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column('created_time', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_time', sa.DateTime(timezone=True), nullable=True),
        sa.Column('deleted', sa.BigInteger(), nullable=False, server_default='0'),
        sa.Column('deleted_time', sa.DateTime(timezone=True), nullable=True),
    ]


def upgrade() -> None:
    op.create_table(
        'qbank_v2_wrong_mastery_event',
        *_base_columns(),
        sa.Column('user_id', sa.BigInteger(), sa.ForeignKey('sys_user.id', ondelete='CASCADE'), nullable=False),
        sa.Column('question_id', sa.BigInteger(), nullable=False),
        sa.Column('wrong_state_id', sa.BigInteger(), nullable=False),
        sa.Column('occurred_time', sa.DateTime(timezone=True), nullable=False),
        sa.Column('source', sa.String(16), nullable=False),
        sa.Column('source_attempt_id', sa.BigInteger(), nullable=True),
        sa.Column('created_by', sa.Integer(), nullable=False),
        sa.Column('updated_by', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(
            ['user_id', 'question_id', 'wrong_state_id'],
            [
                'qbank_v2_wrong_question_state.user_id',
                'qbank_v2_wrong_question_state.question_id',
                'qbank_v2_wrong_question_state.id',
            ],
            name='fk_qbv2_mastery_event_state',
            ondelete='RESTRICT',
        ),
        sa.ForeignKeyConstraint(
            ['user_id', 'question_id', 'source_attempt_id'],
            [
                'qbank_v2_question_attempt.user_id',
                'qbank_v2_question_attempt.question_id',
                'qbank_v2_question_attempt.id',
            ],
            name='fk_qbv2_mastery_event_attempt',
            ondelete='RESTRICT',
        ),
        sa.UniqueConstraint('user_id', 'source_attempt_id', name='uq_qbv2_mastery_event_attempt'),
        sa.CheckConstraint("source IN ('attempt','manual')", name='ck_qbv2_mastery_event_source'),
        comment='错题实际达到掌握状态的不可变事件',
    )
    op.create_index('ix_qbank_v2_wrong_mastery_event_id', 'qbank_v2_wrong_mastery_event', ['id'], unique=True)
    op.create_index('ix_qbv2_mastery_event_user_time', 'qbank_v2_wrong_mastery_event', ['user_id', 'occurred_time'])
    op.create_table(
        'qbank_v2_wrong_trend_coverage',
        *_base_columns(),
        sa.Column('started_time', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint('id = 1', name='ck_qbv2_trend_coverage_singleton'),
    )
    op.create_index('ix_qbank_v2_wrong_trend_coverage_id', 'qbank_v2_wrong_trend_coverage', ['id'], unique=True)
    # 必须先停止旧 API/worker 写入，迁移后启动新代码；覆盖首日为此时间的次日。
    table = sa.table(
        'qbank_v2_wrong_trend_coverage',
        sa.column('id', sa.BigInteger()),
        sa.column('started_time', sa.DateTime(timezone=True)),
        sa.column('created_time', sa.DateTime(timezone=True)),
        sa.column('updated_time', sa.DateTime(timezone=True)),
        sa.column('deleted', sa.BigInteger()),
    )
    now = timezone.now()
    op.bulk_insert(table, [{'id': 1, 'started_time': now, 'created_time': now, 'updated_time': now, 'deleted': 0}])


def downgrade() -> None:
    op.drop_table('qbank_v2_wrong_mastery_event')
    op.drop_table('qbank_v2_wrong_trend_coverage')
