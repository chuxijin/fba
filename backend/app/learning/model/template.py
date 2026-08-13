from decimal import Decimal

import sqlalchemy as sa

from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.learning.enums import LearningActionType, LearningResourceType, LearningTemplateStatus
from backend.common.model import Base, UniversalText, UserMixin, id_key

CompatibleJSONB = sa.JSON().with_variant(JSONB, 'postgresql')


class LearningPlanTemplate(Base, UserMixin):
    """可重复实例化的学习计划模板。"""

    __tablename__ = 'learning_plan_template'
    __table_args__ = (
        sa.UniqueConstraint('code', name='uq_learning_plan_template_code'),
        sa.Index('idx_learning_template_status_exam', 'status', 'exam_type'),
        sa.CheckConstraint("status IN ('draft','active','archived')", name='ck_learning_template_status'),
        sa.CheckConstraint('version >= 1', name='ck_learning_template_version'),
        sa.CheckConstraint('duration_days >= 1', name='ck_learning_template_duration'),
        sa.CheckConstraint('default_daily_minutes >= 0', name='ck_learning_template_daily_minutes'),
        {'comment': '学习计划模板'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    code: Mapped[str] = mapped_column(sa.String(64), comment='模板编码')
    name: Mapped[str] = mapped_column(sa.String(255), comment='模板名称')
    exam_type: Mapped[str | None] = mapped_column(sa.String(64), default=None, comment='适用考试类型')
    version: Mapped[int] = mapped_column(sa.Integer, default=1, comment='模板版本')
    duration_days: Mapped[int] = mapped_column(sa.Integer, default=30, comment='计划周期天数')
    default_daily_minutes: Mapped[int] = mapped_column(sa.Integer, default=120, comment='默认每日学习分钟数')
    status: Mapped[str] = mapped_column(sa.String(16), default=LearningTemplateStatus.draft.value, comment='模板状态')
    description: Mapped[str | None] = mapped_column(UniversalText, default=None, comment='模板说明')
    settings: Mapped[dict | None] = mapped_column(CompatibleJSONB, default=None, comment='模板扩展设置')


class LearningPlanTemplateStage(Base):
    """计划模板阶段。"""

    __tablename__ = 'learning_plan_template_stage'
    __table_args__ = (
        sa.UniqueConstraint('template_id', 'name', name='uq_learning_template_stage_name'),
        sa.Index('idx_learning_template_stage_order', 'template_id', 'order_index'),
        sa.CheckConstraint('start_day >= 1', name='ck_learning_template_stage_start'),
        sa.CheckConstraint('end_day >= start_day', name='ck_learning_template_stage_dates'),
        sa.CheckConstraint('order_index >= 0', name='ck_learning_template_stage_order'),
        {'comment': '学习计划模板阶段'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    template_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('learning_plan_template.id', ondelete='CASCADE'),
        comment='模板 ID',
    )
    name: Mapped[str] = mapped_column(sa.String(128), comment='阶段名称')
    start_day: Mapped[int] = mapped_column(sa.Integer, comment='起始相对天数')
    end_day: Mapped[int] = mapped_column(sa.Integer, comment='结束相对天数')
    order_index: Mapped[int] = mapped_column(sa.Integer, default=0, comment='排序')
    description: Mapped[str | None] = mapped_column(UniversalText, default=None, comment='阶段说明')


class LearningPlanTemplateTask(Base):
    """计划模板任务。"""

    __tablename__ = 'learning_plan_template_task'
    __table_args__ = (
        sa.Index('idx_learning_template_task_day', 'template_id', 'relative_day', 'order_index'),
        sa.Index('idx_learning_template_task_stage', 'stage_id'),
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
        {'comment': '学习计划模板任务'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    template_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('learning_plan_template.id', ondelete='CASCADE'),
        comment='模板 ID',
    )
    relative_day: Mapped[int] = mapped_column(sa.Integer, comment='相对计划开始的第几天')
    title: Mapped[str] = mapped_column(sa.String(255), comment='任务标题')
    stage_id: Mapped[int | None] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('learning_plan_template_stage.id', ondelete='SET NULL'),
        default=None,
        comment='模板阶段 ID',
    )
    order_index: Mapped[int] = mapped_column(sa.Integer, default=0, comment='当日排序')
    action_type: Mapped[str] = mapped_column(
        sa.String(20), default=LearningActionType.custom.value, comment='学习行为类型'
    )
    resource_type: Mapped[str] = mapped_column(
        sa.String(24), default=LearningResourceType.none.value, comment='资源类型'
    )
    resource_id: Mapped[int | None] = mapped_column(sa.BigInteger, default=None, comment='外部资源 ID')
    resource_key: Mapped[str | None] = mapped_column(sa.String(128), default=None, comment='外部资源业务键')
    resource_version_id: Mapped[int | None] = mapped_column(sa.BigInteger, default=None, comment='外部资源版本 ID')
    resource_config: Mapped[dict | None] = mapped_column(CompatibleJSONB, default=None, comment='资源启动参数')
    expected_minutes: Mapped[int] = mapped_column(sa.Integer, default=15, comment='预计用时分钟')
    description: Mapped[str | None] = mapped_column(UniversalText, default=None, comment='任务说明')


class LearningPlanTemplateTaskKnowledgePoint(Base):
    """模板任务知识点关联。"""

    __tablename__ = 'learning_plan_template_task_knowledge_point'
    __table_args__ = (
        sa.UniqueConstraint('template_task_id', 'knowledge_point_id', name='uq_learning_template_task_kpoint'),
        sa.ForeignKeyConstraint(
            ['knowledge_system_id', 'knowledge_point_id'],
            ['qbank_v2_knowledge_point.system_id', 'qbank_v2_knowledge_point.id'],
            name='fk_learning_template_task_kpoint_system',
            ondelete='RESTRICT',
        ),
        sa.CheckConstraint("role IN ('primary','secondary')", name='ck_learning_template_task_kpoint_role'),
        sa.CheckConstraint('weight > 0 AND weight <= 1', name='ck_learning_template_task_kpoint_weight'),
        sa.Index('idx_learning_template_task_kpoint', 'knowledge_point_id', 'template_task_id'),
        {'comment': '学习计划模板任务知识点关联'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    template_task_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('learning_plan_template_task.id', ondelete='CASCADE'),
        comment='模板任务 ID',
    )
    knowledge_system_id: Mapped[int] = mapped_column(sa.BigInteger, comment='知识体系 ID')
    knowledge_point_id: Mapped[int] = mapped_column(sa.BigInteger, comment='知识点 ID')
    role: Mapped[str] = mapped_column(sa.String(16), default='primary', comment='知识点角色')
    include_descendants: Mapped[bool] = mapped_column(default=False, comment='是否包含下级知识点')
    weight: Mapped[Decimal] = mapped_column(sa.Numeric(5, 4), default=Decimal('1.0000'), comment='归属权重')


class LearningPlanTemplateTaskGoal(Base):
    """模板任务完成目标。"""

    __tablename__ = 'learning_plan_template_task_goal'
    __table_args__ = (
        sa.CheckConstraint("operator IN ('gte','lte','eq')", name='ck_learning_template_task_goal_operator'),
        sa.Index('idx_learning_template_task_goal', 'template_task_id', 'is_required'),
        {'comment': '学习计划模板任务目标'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    template_task_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('learning_plan_template_task.id', ondelete='CASCADE'),
        comment='模板任务 ID',
    )
    metric: Mapped[str] = mapped_column(sa.String(32), comment='目标指标')
    operator: Mapped[str] = mapped_column(sa.String(8), default='gte', comment='比较运算符')
    target_value: Mapped[Decimal | None] = mapped_column(sa.Numeric(14, 4), default=None, comment='目标值')
    unit: Mapped[str | None] = mapped_column(sa.String(24), default=None, comment='单位')
    is_required: Mapped[bool] = mapped_column(default=True, comment='是否为必需目标')
    config: Mapped[dict | None] = mapped_column(CompatibleJSONB, default=None, comment='复杂目标配置')
