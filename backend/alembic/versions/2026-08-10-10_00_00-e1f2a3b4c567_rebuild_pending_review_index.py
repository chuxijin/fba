"""rebuild pending review queue index

Revision ID: e1f2a3b4c567
Revises: d0e1f2a3b456
Create Date: 2026-08-10 10:00:00.000000

"""

import sqlalchemy as sa

from alembic import op

revision = 'e1f2a3b4c567'
down_revision = 'd0e1f2a3b456'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """待复盘队列口径变更：从未复盘，或上次复盘后又重新答错。

    旧 partial index 只覆盖 review_count = 0，新口径需要覆盖
    review_count = 0 OR last_wrong_time > last_reviewed_time。
    """
    if op.get_bind().dialect.name != 'postgresql':
        return

    with op.get_context().autocommit_block():
        op.drop_index(
            'ix_qbv2_wrong_unreviewed',
            table_name='qbank_v2_wrong_question_state',
            if_exists=True,
            postgresql_concurrently=True,
        )
        op.create_index(
            'ix_qbv2_wrong_unreviewed',
            'qbank_v2_wrong_question_state',
            ['user_id', 'last_wrong_time', 'id'],
            if_not_exists=True,
            postgresql_where=sa.text(
                "deleted = 0 AND status = 'active' "
                "AND (review_count = 0 OR (last_reviewed_time IS NOT NULL AND last_wrong_time > last_reviewed_time))"
            ),
            postgresql_concurrently=True,
        )


def downgrade() -> None:
    """恢复旧口径索引（只覆盖从未复盘）。"""
    if op.get_bind().dialect.name != 'postgresql':
        return

    with op.get_context().autocommit_block():
        op.drop_index(
            'ix_qbv2_wrong_unreviewed',
            table_name='qbank_v2_wrong_question_state',
            if_exists=True,
            postgresql_concurrently=True,
        )
        op.create_index(
            'ix_qbv2_wrong_unreviewed',
            'qbank_v2_wrong_question_state',
            ['user_id', 'last_wrong_time', 'id'],
            if_not_exists=True,
            postgresql_where=sa.text("deleted = 0 AND review_count = 0 AND status = 'active'"),
            postgresql_concurrently=True,
        )
