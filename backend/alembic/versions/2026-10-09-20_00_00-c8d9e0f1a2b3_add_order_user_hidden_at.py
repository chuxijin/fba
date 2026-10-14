"""add per-user order visibility without deleting financial records

Revision ID: c8d9e0f1a2b3
Revises: b7c8d9e0f1a2
"""

import sqlalchemy as sa

from alembic import op

revision = 'c8d9e0f1a2b3'
down_revision = 'b7c8d9e0f1a2'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'pay_order',
        sa.Column(
            'user_hidden_at', sa.DateTime(timezone=True), nullable=True, comment='用户移除列表记录的时间，不删除交易'
        ),
    )


def downgrade() -> None:
    op.drop_column('pay_order', 'user_hidden_at')
