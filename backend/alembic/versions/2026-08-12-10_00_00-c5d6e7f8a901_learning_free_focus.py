"""learning free focus session

Revision ID: c5d6e7f8a901
Revises: b4c5d6e7f890
Create Date: 2026-08-12 10:00:00.000000
"""

import sqlalchemy as sa

from alembic import op

revision = 'c5d6e7f8a901'
down_revision = 'b4c5d6e7f890'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 自由专注：不关联任务也要计入专注时长，因此 task_id 允许为空
    op.alter_column(
        'learning_focus_session',
        'task_id',
        existing_type=sa.BigInteger(),
        nullable=True,
        existing_comment='学习任务 ID',
        comment='学习任务 ID，空表示自由专注',
    )


def downgrade() -> None:
    # 回退前先清理无归属的专注记录，否则非空约束加不回去
    op.execute('DELETE FROM learning_focus_session WHERE task_id IS NULL')
    op.alter_column(
        'learning_focus_session',
        'task_id',
        existing_type=sa.BigInteger(),
        nullable=False,
        existing_comment='学习任务 ID，空表示自由专注',
        comment='学习任务 ID',
    )
