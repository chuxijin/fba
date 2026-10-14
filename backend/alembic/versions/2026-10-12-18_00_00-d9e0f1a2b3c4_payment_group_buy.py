"""add payment group buying and durable business tasks

Revision ID: d9e0f1a2b3c4
Revises: c8d9e0f1a2b3
"""

import sqlalchemy as sa

from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = 'd9e0f1a2b3c4'
down_revision = 'c8d9e0f1a2b3'
branch_labels = None
depends_on = None


def _base(*, creator: bool = False) -> list:
    columns = [
        sa.Column('id', sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column('created_time', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_time', sa.DateTime(timezone=True), nullable=True),
        sa.Column('deleted', sa.BigInteger(), nullable=False, server_default='0'),
        sa.Column('deleted_time', sa.DateTime(timezone=True), nullable=True),
    ]
    if creator:
        columns.extend([
            sa.Column('created_by', sa.BigInteger(), nullable=False),
            sa.Column('updated_by', sa.BigInteger(), nullable=True),
        ])
    return columns


def upgrade() -> None:
    op.add_column('pay_order', sa.Column('purchase_mode', sa.String(16), nullable=False, server_default='direct'))
    op.create_check_constraint('ck_pay_order_purchase_mode', 'pay_order', "purchase_mode IN ('direct','group_buy')")
    op.create_table(
        'pay_group_buy_activity',
        *_base(creator=True),
        sa.Column('name', sa.String(128), nullable=False),
        sa.Column('template_code', sa.String(64), nullable=False),
        sa.Column('starts_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('ends_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('rules', JSONB(), nullable=False),
        sa.Column('status', sa.String(16), nullable=False),
        sa.Column('revision', sa.Integer(), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.CheckConstraint("status IN ('draft','active','disabled')", name='ck_pay_gb_activity_status'),
        sa.CheckConstraint('starts_at < ends_at', name='ck_pay_gb_activity_period'),
    )
    op.create_table(
        'pay_group_buy_tier',
        *_base(),
        sa.Column(
            'activity_id',
            sa.BigInteger(),
            sa.ForeignKey('pay_group_buy_activity.id', ondelete='RESTRICT'),
            nullable=False,
        ),
        sa.Column('people', sa.Integer(), nullable=False),
        sa.Column('price_cents', sa.Integer(), nullable=False),
        sa.Column('rewards', JSONB(), nullable=False),
        sa.UniqueConstraint('activity_id', 'people', name='uq_pay_gb_tier_people'),
        sa.CheckConstraint('people IN (3,4,5)', name='ck_pay_gb_tier_people'),
        sa.CheckConstraint('price_cents > 0', name='ck_pay_gb_tier_price'),
    )
    op.create_table(
        'pay_group_buy_team',
        *_base(creator=True),
        sa.Column(
            'activity_id',
            sa.BigInteger(),
            sa.ForeignKey('pay_group_buy_activity.id', ondelete='RESTRICT'),
            nullable=False,
        ),
        sa.Column('leader_user_id', sa.BigInteger(), nullable=False),
        sa.Column('share_code', sa.String(32), nullable=False, unique=True),
        sa.Column('request_key', sa.String(64), nullable=False),
        sa.Column('people', sa.Integer(), nullable=False),
        sa.Column('snapshot', JSONB(), nullable=False),
        sa.Column('draft_until', sa.DateTime(timezone=True), nullable=False),
        sa.Column('status', sa.String(16), nullable=False),
        sa.Column('deadline', sa.DateTime(timezone=True)),
        sa.Column('started_at', sa.DateTime(timezone=True)),
        sa.Column('succeeded_at', sa.DateTime(timezone=True)),
        sa.UniqueConstraint('leader_user_id', 'request_key', name='uq_pay_gb_team_request'),
        sa.CheckConstraint(
            "status IN ('draft','forming','succeeded','expired','cancelled')", name='ck_pay_gb_team_status'
        ),
        sa.CheckConstraint('people IN (3,4,5)', name='ck_pay_gb_team_people'),
    )
    op.create_index('idx_pay_gb_team_due', 'pay_group_buy_team', ['status', 'deadline'])
    op.create_table(
        'pay_group_buy_member',
        *_base(),
        sa.Column(
            'team_id', sa.BigInteger(), sa.ForeignKey('pay_group_buy_team.id', ondelete='RESTRICT'), nullable=False
        ),
        sa.Column(
            'activity_id',
            sa.BigInteger(),
            sa.ForeignKey('pay_group_buy_activity.id', ondelete='RESTRICT'),
            nullable=False,
        ),
        sa.Column('user_id', sa.BigInteger(), nullable=False),
        sa.Column('reserved_until', sa.DateTime(timezone=True), nullable=False),
        sa.Column('order_id', sa.BigInteger(), sa.ForeignKey('pay_order.id', ondelete='RESTRICT')),
        sa.Column('status', sa.String(16), nullable=False),
        sa.Column('inviter_user_id', sa.BigInteger()),
        sa.Column('paid_at', sa.DateTime(timezone=True)),
        sa.UniqueConstraint('team_id', 'user_id', name='uq_pay_gb_member_user'),
        sa.UniqueConstraint('order_id', name='uq_pay_gb_member_order'),
        sa.CheckConstraint(
            "status IN ('reserved','paid','expired','refund_pending','refunded')", name='ck_pay_gb_member_status'
        ),
    )
    op.create_index('idx_pay_gb_member_activity_user', 'pay_group_buy_member', ['activity_id', 'user_id'])
    op.create_table(
        'pay_group_buy_task',
        *_base(),
        sa.Column('key', sa.String(128), nullable=False, unique=True),
        sa.Column('kind', sa.String(24), nullable=False),
        sa.Column('order_id', sa.BigInteger(), sa.ForeignKey('pay_order.id', ondelete='RESTRICT'), nullable=False),
        sa.Column(
            'team_id', sa.BigInteger(), sa.ForeignKey('pay_group_buy_team.id', ondelete='RESTRICT'), nullable=False
        ),
        sa.Column('payload', JSONB(), nullable=False),
        sa.Column('status', sa.String(24), nullable=False),
        sa.Column('attempts', sa.Integer(), nullable=False),
        sa.Column('available_at', sa.DateTime(timezone=True)),
        sa.Column('lease_until', sa.DateTime(timezone=True)),
        sa.Column('error', sa.String(512)),
        sa.CheckConstraint("kind IN ('payment','base','reward','refund','notify_goods')", name='ck_pay_gb_task_kind'),
        sa.CheckConstraint(
            "status IN ('pending','running','done','failed','manual_review')", name='ck_pay_gb_task_status'
        ),
    )
    op.create_index('idx_pay_gb_task_due', 'pay_group_buy_task', ['status', 'available_at'])
    op.create_index('ix_pay_group_buy_task_order_id', 'pay_group_buy_task', ['order_id'])


def downgrade() -> None:
    # 新交易存在时禁止通过降级丢失订单及补偿任务。
    if (
        op
        .get_bind()
        .execute(sa.text("SELECT EXISTS(SELECT 1 FROM pay_order WHERE purchase_mode='group_buy')"))
        .scalar()
    ):
        raise RuntimeError('存在拼团交易，请保留表及任务，不可删除交易记录')
    for table in [
        'pay_group_buy_task',
        'pay_group_buy_member',
        'pay_group_buy_team',
        'pay_group_buy_tier',
        'pay_group_buy_activity',
    ]:
        op.drop_table(table)
    op.drop_constraint('ck_pay_order_purchase_mode', 'pay_order', type_='check')
    op.drop_column('pay_order', 'purchase_mode')
