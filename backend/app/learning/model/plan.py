from datetime import date, datetime

import sqlalchemy as sa

from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.learning.enums import (
    LearningDeliverySource,
    LearningDeliveryStatus,
    LearningPlanSource,
    LearningPlanStatus,
)
from backend.common.model import Base, TimeZone, UniversalText, UserMixin, id_key

CompatibleJSONB = sa.JSON().with_variant(JSONB, 'postgresql')


class LearningPlanDelivery(Base, UserMixin):
    """外部成交或人工创建的学习计划交付单。"""

    __tablename__ = 'learning_plan_delivery'
    __table_args__ = (
        sa.UniqueConstraint('delivery_no', name='uq_learning_delivery_no'),
        sa.Index('idx_learning_delivery_user_status', 'user_id', 'status'),
        sa.Index('idx_learning_delivery_external', 'source_channel', 'external_order_no'),
        sa.CheckConstraint(
            "source_type IN ('external_order','manual','gift','internal','other')",
            name='ck_learning_delivery_source',
        ),
        sa.CheckConstraint(
            "status IN ('pending','drafting','validated','delivered','canceled')",
            name='ck_learning_delivery_status',
        ),
        {'comment': '学习计划交付单'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    delivery_no: Mapped[str] = mapped_column(sa.String(64), comment='内部交付编号')
    user_id: Mapped[int | None] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('sys_user.id', ondelete='SET NULL'),
        default=None,
        comment='接收用户 ID',
    )
    source_type: Mapped[str] = mapped_column(
        sa.String(24), default=LearningDeliverySource.external_order.value, comment='交付来源类型'
    )
    source_channel: Mapped[str | None] = mapped_column(sa.String(32), default=None, comment='外部来源渠道')
    external_order_no: Mapped[str | None] = mapped_column(sa.String(128), default=None, comment='外部订单号')
    external_customer_ref: Mapped[str | None] = mapped_column(
        sa.String(128), default=None, comment='外部客户标识或备注'
    )
    requirements: Mapped[dict | None] = mapped_column(CompatibleJSONB, default=None, comment='用户定制需求')
    source_meta: Mapped[dict | None] = mapped_column(CompatibleJSONB, default=None, comment='来源扩展信息')
    status: Mapped[str] = mapped_column(sa.String(16), default=LearningDeliveryStatus.pending.value, comment='交付状态')
    assigned_to: Mapped[int | None] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('sys_user.id', ondelete='SET NULL'),
        default=None,
        comment='负责人 ID',
    )
    delivered_by: Mapped[int | None] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('sys_user.id', ondelete='SET NULL'),
        default=None,
        comment='交付人 ID',
    )
    delivered_at: Mapped[datetime | None] = mapped_column(TimeZone, default=None, comment='交付时间')
    remark: Mapped[str | None] = mapped_column(UniversalText, default=None, comment='备注')


class LearningPlan(Base, UserMixin):
    """用户实际执行的学习计划。"""

    __tablename__ = 'learning_plan'
    __table_args__ = (
        sa.Index('idx_learning_plan_user_status', 'user_id', 'status'),
        sa.Index('idx_learning_plan_dates', 'user_id', 'start_date', 'end_date'),
        sa.Index('idx_learning_plan_delivery', 'delivery_id'),
        sa.Index('idx_learning_plan_template', 'template_id'),
        sa.CheckConstraint(
            "source_type IN ('system','user','admin_custom','ai')",
            name='ck_learning_plan_source',
        ),
        sa.CheckConstraint(
            "status IN ('draft','active','paused','completed','archived')",
            name='ck_learning_plan_status',
        ),
        sa.CheckConstraint('end_date IS NULL OR end_date >= start_date', name='ck_learning_plan_dates'),
        {'comment': '学习计划'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    user_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('sys_user.id', ondelete='CASCADE'),
        comment='用户 ID',
    )
    title: Mapped[str] = mapped_column(sa.String(255), comment='计划标题')
    start_date: Mapped[date] = mapped_column(sa.Date, comment='开始日期')
    source_type: Mapped[str] = mapped_column(sa.String(20), default=LearningPlanSource.user.value, comment='计划来源')
    end_date: Mapped[date | None] = mapped_column(sa.Date, default=None, comment='结束日期')
    status: Mapped[str] = mapped_column(sa.String(16), default=LearningPlanStatus.draft.value, comment='计划状态')
    delivery_id: Mapped[int | None] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('learning_plan_delivery.id', ondelete='SET NULL'),
        default=None,
        comment='来源交付单 ID',
    )
    template_id: Mapped[int | None] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('learning_plan_template.id', ondelete='SET NULL'),
        default=None,
        comment='来源计划模板 ID',
    )
    description: Mapped[str | None] = mapped_column(UniversalText, default=None, comment='计划说明')
    settings: Mapped[dict | None] = mapped_column(CompatibleJSONB, default=None, comment='计划扩展设置')
