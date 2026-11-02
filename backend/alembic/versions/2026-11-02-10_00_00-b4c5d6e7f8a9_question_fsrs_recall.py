"""Reuse wrong state for FSRS and existing message/session for recall batches.

Revision ID: b4c5d6e7f8a9
Revises: a3b4c5d6e7f8
"""

import sqlalchemy as sa

from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = 'b4c5d6e7f8a9'
down_revision = 'a3b4c5d6e7f8'
branch_labels = None
depends_on = None


def _due_indexes(*, fsrs: bool) -> None:
    if op.get_bind().dialect.name != 'postgresql':
        return
    status = "status IN ('active','resolved')" if fsrs else "status = 'active'"
    with op.get_context().autocommit_block():
        for name, columns in (
            ('ix_qbv2_wrong_push_due', ['next_practice_time', 'user_id', 'id']),
            ('ix_qbv2_wrong_user_due', ['user_id', 'next_practice_time', 'id']),
        ):
            op.drop_index(
                name, table_name='qbank_v2_wrong_question_state', if_exists=True, postgresql_concurrently=True
            )
            op.create_index(
                name,
                'qbank_v2_wrong_question_state',
                columns,
                postgresql_where=sa.text(f'deleted = 0 AND {status} AND next_practice_time IS NOT NULL'),
                postgresql_concurrently=True,
            )


def upgrade() -> None:
    op.add_column(
        'qbank_v2_wrong_question_state',
        sa.Column(
            'fsrs_data', sa.JSON().with_variant(JSONB(), 'postgresql'), nullable=False, server_default=sa.text("'{}'")
        ),
    )
    # 历史已掌握且复盘过的题仍需验证；不把旧阶梯/复盘转换为虚假的FSRS成功记录。
    # 首次回测分散到未来1-7天；保持暂停/删除、现有排期与用户提醒开关不变。
    if op.get_bind().dialect.name == 'postgresql':
        op.execute("""
            UPDATE qbank_v2_wrong_question_state
            SET next_practice_time = CURRENT_TIMESTAMP + (1 + id % 7) * INTERVAL '1 day'
            WHERE deleted = 0 AND status IN ('active','resolved')
              AND review_count > 0 AND next_practice_time IS NULL
        """)
    _due_indexes(fsrs=True)


def downgrade() -> None:
    _due_indexes(fsrs=False)
    op.drop_column('qbank_v2_wrong_question_state', 'fsrs_data')
