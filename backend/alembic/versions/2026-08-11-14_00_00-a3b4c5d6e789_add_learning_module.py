"""add learning module

Revision ID: a3b4c5d6e789
Revises: f2a3b4c5d678
Create Date: 2026-08-11 14:00:00.000000
"""

import sqlalchemy as sa

from alembic import op
from sqlalchemy.dialects import postgresql

revision = 'a3b4c5d6e789'
down_revision = 'f2a3b4c5d678'
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
        'learning_plan_delivery',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('delivery_no', sa.String(64), nullable=False, comment='内部交付编号'),
        sa.Column('user_id', sa.BigInteger(), nullable=True, comment='接收用户 ID'),
        sa.Column('source_type', sa.String(24), server_default='external_order', nullable=False),
        sa.Column('source_channel', sa.String(32), nullable=True),
        sa.Column('external_order_no', sa.String(128), nullable=True),
        sa.Column('external_customer_ref', sa.String(128), nullable=True),
        sa.Column('requirements', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('source_meta', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('status', sa.String(16), server_default='pending', nullable=False),
        sa.Column('assigned_to', sa.BigInteger(), nullable=True),
        sa.Column('delivered_by', sa.BigInteger(), nullable=True),
        sa.Column('delivered_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('remark', sa.Text(), nullable=True),
        *_base_columns(with_user_mixin=True),
        sa.CheckConstraint(
            "source_type IN ('external_order','manual','gift','internal','other')",
            name='ck_learning_delivery_source',
        ),
        sa.CheckConstraint(
            "status IN ('pending','drafting','validated','delivered','canceled')",
            name='ck_learning_delivery_status',
        ),
        sa.ForeignKeyConstraint(['user_id'], ['sys_user.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['assigned_to'], ['sys_user.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['delivered_by'], ['sys_user.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('delivery_no', name='uq_learning_delivery_no'),
        comment='学习计划交付单',
    )
    op.create_index('ix_learning_plan_delivery_id', 'learning_plan_delivery', ['id'], unique=True)
    op.create_index('idx_learning_delivery_user_status', 'learning_plan_delivery', ['user_id', 'status'])
    op.create_index(
        'idx_learning_delivery_external',
        'learning_plan_delivery',
        ['source_channel', 'external_order_no'],
    )
    op.create_index(
        'uq_learning_delivery_external_order',
        'learning_plan_delivery',
        ['source_channel', 'external_order_no'],
        unique=True,
        postgresql_where=sa.text('external_order_no IS NOT NULL AND deleted = 0'),
    )

    op.create_table(
        'learning_plan',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.BigInteger(), nullable=False),
        sa.Column('title', sa.String(255), nullable=False),
        sa.Column('start_date', sa.Date(), nullable=False),
        sa.Column('source_type', sa.String(20), server_default='user', nullable=False),
        sa.Column('end_date', sa.Date(), nullable=True),
        sa.Column('status', sa.String(16), server_default='draft', nullable=False),
        sa.Column('delivery_id', sa.BigInteger(), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('settings', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        *_base_columns(with_user_mixin=True),
        sa.CheckConstraint("source_type IN ('system','user','admin_custom','ai')", name='ck_learning_plan_source'),
        sa.CheckConstraint(
            "status IN ('draft','active','paused','completed','archived')",
            name='ck_learning_plan_status',
        ),
        sa.CheckConstraint('end_date IS NULL OR end_date >= start_date', name='ck_learning_plan_dates'),
        sa.ForeignKeyConstraint(['user_id'], ['sys_user.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['delivery_id'], ['learning_plan_delivery.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        comment='学习计划',
    )
    op.create_index('ix_learning_plan_id', 'learning_plan', ['id'], unique=True)
    op.create_index('idx_learning_plan_user_status', 'learning_plan', ['user_id', 'status'])
    op.create_index('idx_learning_plan_dates', 'learning_plan', ['user_id', 'start_date', 'end_date'])
    op.create_index('idx_learning_plan_delivery', 'learning_plan', ['delivery_id'])

    op.create_table(
        'learning_task',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('plan_id', sa.BigInteger(), nullable=False),
        sa.Column('user_id', sa.BigInteger(), nullable=False),
        sa.Column('plan_date', sa.Date(), nullable=False),
        sa.Column('title', sa.String(255), nullable=False),
        sa.Column('order_index', sa.Integer(), server_default='0', nullable=False),
        sa.Column('action_type', sa.String(20), server_default='custom', nullable=False),
        sa.Column('resource_type', sa.String(24), server_default='none', nullable=False),
        sa.Column('resource_id', sa.BigInteger(), nullable=True),
        sa.Column('resource_key', sa.String(128), nullable=True),
        sa.Column('resource_version_id', sa.BigInteger(), nullable=True),
        sa.Column('resource_config', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('expected_minutes', sa.Integer(), server_default='15', nullable=False),
        sa.Column('due_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('remind_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('status', sa.String(16), server_default='pending', nullable=False),
        sa.Column('delivery_id', sa.BigInteger(), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        *_base_columns(with_user_mixin=True),
        sa.CheckConstraint(
            "action_type IN ('learn','read','practice','wrong_review','ability','review','custom')",
            name='ck_learning_task_action',
        ),
        sa.CheckConstraint(
            "resource_type IN ('content','course','course_lesson','question_bank','ability','external','none')",
            name='ck_learning_task_resource',
        ),
        sa.CheckConstraint(
            "status IN ('pending','in_progress','completed','skipped','canceled')",
            name='ck_learning_task_status',
        ),
        sa.CheckConstraint('expected_minutes >= 0', name='ck_learning_task_minutes'),
        sa.CheckConstraint('order_index >= 0', name='ck_learning_task_order'),
        sa.ForeignKeyConstraint(['plan_id'], ['learning_plan.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['sys_user.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['delivery_id'], ['learning_plan_delivery.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        comment='学习任务',
    )
    op.create_index('ix_learning_task_id', 'learning_task', ['id'], unique=True)
    op.create_index('idx_learning_task_plan_date_order', 'learning_task', ['plan_id', 'plan_date', 'order_index'])
    op.create_index('idx_learning_task_user_date_status', 'learning_task', ['user_id', 'plan_date', 'status'])
    op.create_index('idx_learning_task_delivery', 'learning_task', ['delivery_id'])

    op.create_table(
        'learning_task_knowledge_point',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('task_id', sa.BigInteger(), nullable=False),
        sa.Column('knowledge_system_id', sa.BigInteger(), nullable=False),
        sa.Column('knowledge_point_id', sa.BigInteger(), nullable=False),
        sa.Column('role', sa.String(16), server_default='primary', nullable=False),
        sa.Column('include_descendants', sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column('weight', sa.Numeric(5, 4), server_default='1.0000', nullable=False),
        *_base_columns(),
        sa.CheckConstraint("role IN ('primary','secondary')", name='ck_learning_task_kpoint_role'),
        sa.CheckConstraint('weight > 0 AND weight <= 1', name='ck_learning_task_kpoint_weight'),
        sa.ForeignKeyConstraint(['task_id'], ['learning_task.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(
            ['knowledge_system_id', 'knowledge_point_id'],
            ['qbank_v2_knowledge_point.system_id', 'qbank_v2_knowledge_point.id'],
            name='fk_learning_task_kpoint_system',
            ondelete='RESTRICT',
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('task_id', 'knowledge_point_id', name='uq_learning_task_kpoint'),
        comment='学习任务知识点关联',
    )
    op.create_index('ix_learning_task_knowledge_point_id', 'learning_task_knowledge_point', ['id'], unique=True)
    op.create_index(
        'idx_learning_task_kpoint_point',
        'learning_task_knowledge_point',
        ['knowledge_point_id', 'task_id'],
    )

    op.create_table(
        'learning_task_goal',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('task_id', sa.BigInteger(), nullable=False),
        sa.Column('metric', sa.String(32), nullable=False),
        sa.Column('operator', sa.String(8), server_default='gte', nullable=False),
        sa.Column('target_value', sa.Numeric(14, 4), nullable=True),
        sa.Column('unit', sa.String(24), nullable=True),
        sa.Column('is_required', sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column('config', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        *_base_columns(),
        sa.CheckConstraint("operator IN ('gte','lte','eq')", name='ck_learning_task_goal_operator'),
        sa.ForeignKeyConstraint(['task_id'], ['learning_task.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        comment='学习任务目标',
    )
    op.create_index('ix_learning_task_goal_id', 'learning_task_goal', ['id'], unique=True)
    op.create_index('idx_learning_task_goal_task', 'learning_task_goal', ['task_id', 'is_required'])

    op.create_table(
        'learning_focus_session',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('task_id', sa.BigInteger(), nullable=False),
        sa.Column('user_id', sa.BigInteger(), nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('mode', sa.String(16), server_default='pomodoro', nullable=False),
        sa.Column('status', sa.String(16), server_default='running', nullable=False),
        sa.Column('planned_minutes', sa.Integer(), server_default='25', nullable=False),
        sa.Column('focused_seconds', sa.Integer(), server_default='0', nullable=False),
        sa.Column('paused_seconds', sa.Integer(), server_default='0', nullable=False),
        sa.Column('interrupt_count', sa.Integer(), server_default='0', nullable=False),
        sa.Column('paused_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('ended_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('remark', sa.Text(), nullable=True),
        *_base_columns(),
        sa.CheckConstraint("mode IN ('pomodoro','countdown','stopwatch')", name='ck_learning_focus_mode'),
        sa.CheckConstraint(
            "status IN ('running','paused','completed','canceled')",
            name='ck_learning_focus_status',
        ),
        sa.ForeignKeyConstraint(['task_id'], ['learning_task.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['sys_user.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        comment='学习专注记录',
    )
    op.create_index('ix_learning_focus_session_id', 'learning_focus_session', ['id'], unique=True)
    op.create_index('idx_learning_focus_user_status', 'learning_focus_session', ['user_id', 'status'])
    op.create_index('idx_learning_focus_task_started', 'learning_focus_session', ['task_id', 'started_at'])

    op.create_table(
        'learning_completion_record',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('task_id', sa.BigInteger(), nullable=False),
        sa.Column('user_id', sa.BigInteger(), nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('completion_source', sa.String(32), server_default='manual', nullable=False),
        sa.Column('duration_seconds', sa.Integer(), server_default='0', nullable=False),
        sa.Column('actual_metrics', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('extra_data', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        *_base_columns(),
        sa.ForeignKeyConstraint(['task_id'], ['learning_task.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['sys_user.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        comment='学习任务完成记录',
    )
    op.create_index('ix_learning_completion_record_id', 'learning_completion_record', ['id'], unique=True)
    op.create_index(
        'idx_learning_completion_task_time',
        'learning_completion_record',
        ['task_id', 'completed_at'],
    )
    op.create_index(
        'idx_learning_completion_user_time',
        'learning_completion_record',
        ['user_id', 'completed_at'],
    )


def downgrade() -> None:
    op.drop_table('learning_completion_record')
    op.drop_table('learning_focus_session')
    op.drop_table('learning_task_goal')
    op.drop_table('learning_task_knowledge_point')
    op.drop_table('learning_task')
    op.drop_table('learning_plan')
    op.drop_table('learning_plan_delivery')
