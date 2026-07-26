"""optimize question bank queries

Revision ID: a1b2c3d4e5f6
Revises: f6a7b8c9d012
Create Date: 2026-07-26 12:00:00.000000

"""

import sqlalchemy as sa

from alembic import op

revision = 'a1b2c3d4e5f6'
down_revision = 'f6a7b8c9d012'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """为题目筛选和答题时间统计增加 PostgreSQL 索引"""
    if op.get_bind().dialect.name != 'postgresql':
        return

    with op.get_context().autocommit_block():
        op.create_index(
            'idx_question_knowledge_point_gin',
            'study_question',
            ['knowledge_point'],
            unique=False,
            if_not_exists=True,
            postgresql_ops={'knowledge_point': 'jsonb_path_ops'},
            postgresql_using='gin',
            postgresql_concurrently=True,
        )
        op.create_index(
            'idx_session_question_valid_answer_time',
            'study_session_question',
            ['question_id', 'answer_time'],
            unique=False,
            if_not_exists=True,
            postgresql_where=sa.text('user_answer IS NOT NULL AND is_correct IS NOT NULL AND answer_time >= 3'),
            postgresql_concurrently=True,
        )


def downgrade() -> None:
    """删除题目筛选和答题时间统计索引"""
    if op.get_bind().dialect.name != 'postgresql':
        return

    with op.get_context().autocommit_block():
        op.drop_index(
            'idx_session_question_valid_answer_time',
            table_name='study_session_question',
            if_exists=True,
            postgresql_concurrently=True,
        )
        op.drop_index(
            'idx_question_knowledge_point_gin',
            table_name='study_question',
            if_exists=True,
            postgresql_concurrently=True,
        )
