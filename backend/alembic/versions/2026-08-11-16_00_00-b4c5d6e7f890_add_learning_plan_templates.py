"""add learning plan templates

Revision ID: b4c5d6e7f890
Revises: a3b4c5d6e789
Create Date: 2026-08-11 16:00:00.000000
"""

import sqlalchemy as sa

from alembic import op
from sqlalchemy.dialects import postgresql

revision = 'b4c5d6e7f890'
down_revision = 'a3b4c5d6e789'
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


def _ensure_plan_template_reference() -> None:
    inspector = sa.inspect(op.get_bind())
    columns = {item['name'] for item in inspector.get_columns('learning_plan')}
    if 'template_id' not in columns:
        op.add_column(
            'learning_plan',
            sa.Column('template_id', sa.BigInteger(), nullable=True, comment='来源计划模板 ID'),
        )
        op.create_foreign_key(
            'fk_learning_plan_template',
            'learning_plan',
            'learning_plan_template',
            ['template_id'],
            ['id'],
            ondelete='SET NULL',
        )
        op.create_index('idx_learning_plan_template', 'learning_plan', ['template_id'])
        return

    foreign_keys = {item.get('name') for item in inspector.get_foreign_keys('learning_plan')}
    if 'fk_learning_plan_template' not in foreign_keys:
        op.create_foreign_key(
            'fk_learning_plan_template',
            'learning_plan',
            'learning_plan_template',
            ['template_id'],
            ['id'],
            ondelete='SET NULL',
        )
    indexes = {item['name'] for item in inspector.get_indexes('learning_plan')}
    if 'idx_learning_plan_template' not in indexes:
        op.create_index('idx_learning_plan_template', 'learning_plan', ['template_id'])


def upgrade() -> None:
    expected_tables = {
        'learning_plan_template',
        'learning_plan_template_stage',
        'learning_plan_template_task',
        'learning_plan_template_task_goal',
        'learning_plan_template_task_knowledge_point',
    }
    existing_tables = set(sa.inspect(op.get_bind()).get_table_names())
    existing_template_tables = expected_tables & existing_tables
    if existing_template_tables == expected_tables:
        _ensure_plan_template_reference()
        return
    if existing_template_tables:
        names = ', '.join(sorted(existing_template_tables))
        raise RuntimeError(f'检测到不完整的学习计划模板表结构，请先处理：{names}')

    op.create_table(
        'learning_plan_template',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('code', sa.String(64), nullable=False, comment='模板编码'),
        sa.Column('name', sa.String(255), nullable=False, comment='模板名称'),
        sa.Column('exam_type', sa.String(64), nullable=True, comment='适用考试类型'),
        sa.Column('version', sa.Integer(), server_default='1', nullable=False, comment='模板版本'),
        sa.Column('duration_days', sa.Integer(), server_default='30', nullable=False, comment='计划周期天数'),
        sa.Column(
            'default_daily_minutes',
            sa.Integer(),
            server_default='120',
            nullable=False,
            comment='默认每日学习分钟数',
        ),
        sa.Column('status', sa.String(16), server_default='draft', nullable=False, comment='模板状态'),
        sa.Column('description', sa.Text(), nullable=True, comment='模板说明'),
        sa.Column('settings', postgresql.JSONB(astext_type=sa.Text()), nullable=True, comment='模板扩展设置'),
        *_base_columns(with_user_mixin=True),
        sa.CheckConstraint("status IN ('draft','active','archived')", name='ck_learning_template_status'),
        sa.CheckConstraint('version >= 1', name='ck_learning_template_version'),
        sa.CheckConstraint('duration_days >= 1', name='ck_learning_template_duration'),
        sa.CheckConstraint('default_daily_minutes >= 0', name='ck_learning_template_daily_minutes'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('code', name='uq_learning_plan_template_code'),
        comment='学习计划模板',
    )
    op.create_index('ix_learning_plan_template_id', 'learning_plan_template', ['id'], unique=True)
    op.create_index('idx_learning_template_status_exam', 'learning_plan_template', ['status', 'exam_type'])

    op.create_table(
        'learning_plan_template_stage',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('template_id', sa.BigInteger(), nullable=False, comment='模板 ID'),
        sa.Column('name', sa.String(128), nullable=False, comment='阶段名称'),
        sa.Column('start_day', sa.Integer(), nullable=False, comment='起始相对天数'),
        sa.Column('end_day', sa.Integer(), nullable=False, comment='结束相对天数'),
        sa.Column('order_index', sa.Integer(), server_default='0', nullable=False, comment='排序'),
        sa.Column('description', sa.Text(), nullable=True, comment='阶段说明'),
        *_base_columns(),
        sa.CheckConstraint('start_day >= 1', name='ck_learning_template_stage_start'),
        sa.CheckConstraint('end_day >= start_day', name='ck_learning_template_stage_dates'),
        sa.CheckConstraint('order_index >= 0', name='ck_learning_template_stage_order'),
        sa.ForeignKeyConstraint(['template_id'], ['learning_plan_template.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('template_id', 'name', name='uq_learning_template_stage_name'),
        comment='学习计划模板阶段',
    )
    op.create_index('ix_learning_plan_template_stage_id', 'learning_plan_template_stage', ['id'], unique=True)
    op.create_index(
        'idx_learning_template_stage_order',
        'learning_plan_template_stage',
        ['template_id', 'order_index'],
    )

    op.create_table(
        'learning_plan_template_task',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('template_id', sa.BigInteger(), nullable=False, comment='模板 ID'),
        sa.Column('relative_day', sa.Integer(), nullable=False, comment='相对计划开始的第几天'),
        sa.Column('title', sa.String(255), nullable=False, comment='任务标题'),
        sa.Column('stage_id', sa.BigInteger(), nullable=True, comment='模板阶段 ID'),
        sa.Column('order_index', sa.Integer(), server_default='0', nullable=False, comment='当日排序'),
        sa.Column('action_type', sa.String(20), server_default='custom', nullable=False, comment='学习行为类型'),
        sa.Column('resource_type', sa.String(24), server_default='none', nullable=False, comment='资源类型'),
        sa.Column('resource_id', sa.BigInteger(), nullable=True, comment='外部资源 ID'),
        sa.Column('resource_key', sa.String(128), nullable=True, comment='外部资源业务键'),
        sa.Column('resource_version_id', sa.BigInteger(), nullable=True, comment='外部资源版本 ID'),
        sa.Column(
            'resource_config',
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment='资源启动参数',
        ),
        sa.Column('expected_minutes', sa.Integer(), server_default='15', nullable=False, comment='预计用时分钟'),
        sa.Column('description', sa.Text(), nullable=True, comment='任务说明'),
        *_base_columns(),
        sa.CheckConstraint('relative_day >= 1', name='ck_learning_template_task_day'),
        sa.CheckConstraint('expected_minutes >= 0', name='ck_learning_template_task_minutes'),
        sa.CheckConstraint('order_index >= 0', name='ck_learning_template_task_order'),
        sa.CheckConstraint(
            "action_type IN ('learn','read','practice','wrong_review','ability','review','custom')",
            name='ck_learning_template_task_action',
        ),
        sa.CheckConstraint(
            "resource_type IN ('content','course','course_lesson','question_bank','ability','external','none')",
            name='ck_learning_template_task_resource',
        ),
        sa.ForeignKeyConstraint(['template_id'], ['learning_plan_template.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['stage_id'], ['learning_plan_template_stage.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        comment='学习计划模板任务',
    )
    op.create_index('ix_learning_plan_template_task_id', 'learning_plan_template_task', ['id'], unique=True)
    op.create_index(
        'idx_learning_template_task_day',
        'learning_plan_template_task',
        ['template_id', 'relative_day', 'order_index'],
    )
    op.create_index('idx_learning_template_task_stage', 'learning_plan_template_task', ['stage_id'])

    op.create_table(
        'learning_plan_template_task_knowledge_point',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('template_task_id', sa.BigInteger(), nullable=False, comment='模板任务 ID'),
        sa.Column('knowledge_system_id', sa.BigInteger(), nullable=False, comment='知识体系 ID'),
        sa.Column('knowledge_point_id', sa.BigInteger(), nullable=False, comment='知识点 ID'),
        sa.Column('role', sa.String(16), server_default='primary', nullable=False, comment='知识点角色'),
        sa.Column('include_descendants', sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column('weight', sa.Numeric(5, 4), server_default='1.0000', nullable=False, comment='归属权重'),
        *_base_columns(),
        sa.CheckConstraint("role IN ('primary','secondary')", name='ck_learning_template_task_kpoint_role'),
        sa.CheckConstraint('weight > 0 AND weight <= 1', name='ck_learning_template_task_kpoint_weight'),
        sa.ForeignKeyConstraint(
            ['template_task_id'],
            ['learning_plan_template_task.id'],
            ondelete='CASCADE',
        ),
        sa.ForeignKeyConstraint(
            ['knowledge_system_id', 'knowledge_point_id'],
            ['qbank_v2_knowledge_point.system_id', 'qbank_v2_knowledge_point.id'],
            name='fk_learning_template_task_kpoint_system',
            ondelete='RESTRICT',
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'template_task_id',
            'knowledge_point_id',
            name='uq_learning_template_task_kpoint',
        ),
        comment='学习计划模板任务知识点关联',
    )
    op.create_index(
        'ix_learning_plan_template_task_knowledge_point_id',
        'learning_plan_template_task_knowledge_point',
        ['id'],
        unique=True,
    )
    op.create_index(
        'idx_learning_template_task_kpoint',
        'learning_plan_template_task_knowledge_point',
        ['knowledge_point_id', 'template_task_id'],
    )

    op.create_table(
        'learning_plan_template_task_goal',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('template_task_id', sa.BigInteger(), nullable=False, comment='模板任务 ID'),
        sa.Column('metric', sa.String(32), nullable=False, comment='目标指标'),
        sa.Column('operator', sa.String(8), server_default='gte', nullable=False, comment='比较运算符'),
        sa.Column('target_value', sa.Numeric(14, 4), nullable=True, comment='目标值'),
        sa.Column('unit', sa.String(24), nullable=True, comment='单位'),
        sa.Column('is_required', sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column('config', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        *_base_columns(),
        sa.CheckConstraint("operator IN ('gte','lte','eq')", name='ck_learning_template_task_goal_operator'),
        sa.ForeignKeyConstraint(
            ['template_task_id'],
            ['learning_plan_template_task.id'],
            ondelete='CASCADE',
        ),
        sa.PrimaryKeyConstraint('id'),
        comment='学习计划模板任务目标',
    )
    op.create_index(
        'ix_learning_plan_template_task_goal_id',
        'learning_plan_template_task_goal',
        ['id'],
        unique=True,
    )
    op.create_index(
        'idx_learning_template_task_goal',
        'learning_plan_template_task_goal',
        ['template_task_id', 'is_required'],
    )

    _ensure_plan_template_reference()


def downgrade() -> None:
    op.drop_index('idx_learning_plan_template', table_name='learning_plan')
    op.drop_constraint('fk_learning_plan_template', 'learning_plan', type_='foreignkey')
    op.drop_column('learning_plan', 'template_id')
    op.drop_table('learning_plan_template_task_goal')
    op.drop_table('learning_plan_template_task_knowledge_point')
    op.drop_table('learning_plan_template_task')
    op.drop_table('learning_plan_template_stage')
    op.drop_table('learning_plan_template')
