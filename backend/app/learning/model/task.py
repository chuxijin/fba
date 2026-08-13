from datetime import date, datetime
from decimal import Decimal

import sqlalchemy as sa

from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.learning.enums import LearningActionType, LearningResourceType, LearningTaskStatus
from backend.common.model import Base, TimeZone, UniversalText, UserMixin, id_key

CompatibleJSONB = sa.JSON().with_variant(JSONB, 'postgresql')


class LearningTask(Base, UserMixin):
    """计划中的每日可执行学习任务。"""

    __tablename__ = 'learning_task'
    __table_args__ = (
        sa.Index('idx_learning_task_plan_date_order', 'plan_id', 'plan_date', 'order_index'),
        sa.Index('idx_learning_task_user_date_status', 'user_id', 'plan_date', 'status'),
        sa.Index('idx_learning_task_delivery', 'delivery_id'),
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
        {'comment': '学习任务'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    plan_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('learning_plan.id', ondelete='CASCADE'),
        comment='所属计划 ID',
    )
    user_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('sys_user.id', ondelete='CASCADE'),
        comment='用户 ID',
    )
    plan_date: Mapped[date] = mapped_column(sa.Date, comment='计划日期')
    title: Mapped[str] = mapped_column(sa.String(255), comment='任务标题')
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
    due_at: Mapped[datetime | None] = mapped_column(TimeZone, default=None, comment='截止时间')
    remind_at: Mapped[datetime | None] = mapped_column(TimeZone, default=None, comment='提醒时间')
    status: Mapped[str] = mapped_column(sa.String(16), default=LearningTaskStatus.pending.value, comment='任务状态')
    delivery_id: Mapped[int | None] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('learning_plan_delivery.id', ondelete='SET NULL'),
        default=None,
        comment='来源交付单 ID',
    )
    description: Mapped[str | None] = mapped_column(UniversalText, default=None, comment='任务说明')


class LearningTaskKnowledgePoint(Base):
    """学习任务与题库 V2 知识点的关联。"""

    __tablename__ = 'learning_task_knowledge_point'
    __table_args__ = (
        sa.UniqueConstraint('task_id', 'knowledge_point_id', name='uq_learning_task_kpoint'),
        sa.ForeignKeyConstraint(
            ['knowledge_system_id', 'knowledge_point_id'],
            ['qbank_v2_knowledge_point.system_id', 'qbank_v2_knowledge_point.id'],
            name='fk_learning_task_kpoint_system',
            ondelete='RESTRICT',
        ),
        sa.CheckConstraint("role IN ('primary','secondary')", name='ck_learning_task_kpoint_role'),
        sa.CheckConstraint('weight > 0 AND weight <= 1', name='ck_learning_task_kpoint_weight'),
        sa.Index('idx_learning_task_kpoint_point', 'knowledge_point_id', 'task_id'),
        {'comment': '学习任务知识点关联'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    task_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('learning_task.id', ondelete='CASCADE'),
        comment='学习任务 ID',
    )
    knowledge_system_id: Mapped[int] = mapped_column(sa.BigInteger, comment='知识体系 ID')
    knowledge_point_id: Mapped[int] = mapped_column(sa.BigInteger, comment='知识点 ID')
    role: Mapped[str] = mapped_column(sa.String(16), default='primary', comment='知识点角色')
    include_descendants: Mapped[bool] = mapped_column(default=False, comment='是否包含下级知识点')
    weight: Mapped[Decimal] = mapped_column(sa.Numeric(5, 4), default=Decimal('1.0000'), comment='归属权重')


class LearningTaskGoal(Base):
    """学习任务完成目标。"""

    __tablename__ = 'learning_task_goal'
    __table_args__ = (
        sa.CheckConstraint("operator IN ('gte','lte','eq')", name='ck_learning_task_goal_operator'),
        sa.Index('idx_learning_task_goal_task', 'task_id', 'is_required'),
        {'comment': '学习任务目标'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    task_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('learning_task.id', ondelete='CASCADE'),
        comment='学习任务 ID',
    )
    metric: Mapped[str] = mapped_column(sa.String(32), comment='目标指标')
    operator: Mapped[str] = mapped_column(sa.String(8), default='gte', comment='比较运算符')
    target_value: Mapped[Decimal | None] = mapped_column(sa.Numeric(14, 4), default=None, comment='目标值')
    unit: Mapped[str | None] = mapped_column(sa.String(24), default=None, comment='单位')
    is_required: Mapped[bool] = mapped_column(default=True, comment='是否为必需目标')
    config: Mapped[dict | None] = mapped_column(CompatibleJSONB, default=None, comment='复杂目标配置')
