from __future__ import annotations

from datetime import datetime
from typing import Any

import sqlalchemy as sa

from sqlalchemy.dialects.mysql import JSON as MYSQL_JSON
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.common.enums import DataBaseType
from backend.common.model import Base, TimeZone, UniversalText, id_key
from backend.core.conf import settings

JSONType = JSONB if DataBaseType.postgresql == settings.DATABASE_TYPE else MYSQL_JSON


class ShenlunCoachSession(Base):
    """申论教练会话。"""

    __tablename__ = 'agent_shenlun_coach_session'
    __table_args__ = (
        sa.CheckConstraint("status IN ('active','archived')", name='ck_agent_coach_session_status'),
        sa.Index('idx_agent_coach_session_user_status', 'user_id', 'status', 'updated_time'),
        {'comment': '申论教练会话'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    user_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('sys_user.id', ondelete='CASCADE'),
        comment='用户 ID',
    )
    title: Mapped[str] = mapped_column(sa.String(160), default='申论训练教练', comment='会话标题')
    status: Mapped[str] = mapped_column(sa.String(24), default='active', comment='active/archived')
    context_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONType, default_factory=dict, comment='上下文快照')
    last_summary: Mapped[str | None] = mapped_column(UniversalText, default=None, comment='最近会话摘要')

    messages: Mapped[list[ShenlunCoachMessage]] = relationship(
        init=False,
        back_populates='session',
        cascade='all, delete-orphan',
        lazy='noload',
    )


class ShenlunCoachMessage(Base):
    """教练会话消息。"""

    __tablename__ = 'agent_shenlun_coach_message'
    __table_args__ = (
        sa.UniqueConstraint('session_id', 'request_id', name='uq_agent_coach_message_request'),
        sa.CheckConstraint("role IN ('user','coach','system')", name='ck_agent_coach_message_role'),
        sa.Index('idx_agent_coach_message_session_time', 'session_id', 'created_time'),
        {'comment': '申论教练消息'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    session_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('agent_shenlun_coach_session.id', ondelete='CASCADE'),
        comment='会话 ID',
    )
    user_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('sys_user.id', ondelete='CASCADE'),
        comment='用户 ID',
    )
    role: Mapped[str] = mapped_column(sa.String(16), comment='user/coach/system')
    content: Mapped[str] = mapped_column(UniversalText, comment='消息内容')
    request_id: Mapped[str | None] = mapped_column(sa.String(80), default=None, comment='客户端幂等请求 ID')
    metadata_payload: Mapped[dict[str, Any]] = mapped_column(JSONType, default_factory=dict, comment='消息元数据')

    session: Mapped[ShenlunCoachSession] = relationship(
        init=False,
        back_populates='messages',
        lazy='noload',
    )


class ShenlunCoachMemory(Base):
    """可修正的长期训练记忆。"""

    __tablename__ = 'agent_shenlun_coach_memory'
    __table_args__ = (
        sa.UniqueConstraint('user_id', 'memory_key', 'deleted', name='uq_agent_coach_memory_user_key'),
        sa.CheckConstraint(
            "memory_type IN ('weakness','strength','preference','goal')",
            name='ck_agent_coach_memory_type',
        ),
        sa.CheckConstraint('confidence BETWEEN 0 AND 1', name='ck_agent_coach_memory_confidence'),
        sa.Index('idx_agent_coach_memory_user_type', 'user_id', 'memory_type', 'updated_time'),
        {'comment': '申论教练长期记忆'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    user_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('sys_user.id', ondelete='CASCADE'),
        comment='用户 ID',
    )
    memory_key: Mapped[str] = mapped_column(sa.String(120), comment='稳定记忆键')
    memory_type: Mapped[str] = mapped_column(sa.String(32), comment='weakness/strength/preference/goal')
    content: Mapped[str] = mapped_column(UniversalText, comment='记忆内容')
    confidence: Mapped[float] = mapped_column(sa.Float, default=0.5, comment='置信度')
    source_ref: Mapped[str | None] = mapped_column(sa.String(160), default=None, comment='来源引用')
    evidence: Mapped[dict[str, Any]] = mapped_column(JSONType, default_factory=dict, comment='证据快照')
    last_seen_time: Mapped[datetime | None] = mapped_column(TimeZone, default=None, comment='最近验证时间')


class ShenlunTrainingPlan(Base):
    """申论训练计划。"""

    __tablename__ = 'agent_shenlun_training_plan'
    __table_args__ = (
        sa.CheckConstraint(
            "status IN ('draft','active','completed','archived')",
            name='ck_agent_training_plan_status',
        ),
        sa.UniqueConstraint('user_id', 'request_id', 'deleted', name='uq_agent_training_plan_user_request'),
        sa.Index('idx_agent_training_plan_user_status', 'user_id', 'status', 'created_time'),
        {'comment': '申论训练计划'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    user_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('sys_user.id', ondelete='CASCADE'),
        comment='用户 ID',
    )
    title: Mapped[str] = mapped_column(sa.String(160), comment='计划标题')
    goal: Mapped[str] = mapped_column(UniversalText, comment='训练目标')
    request_id: Mapped[str | None] = mapped_column(sa.String(80), default=None, comment='客户端幂等请求 ID')
    status: Mapped[str] = mapped_column(sa.String(24), default='active', comment='draft/active/completed/archived')
    start_date: Mapped[datetime | None] = mapped_column(TimeZone, default=None, comment='开始时间')
    end_date: Mapped[datetime | None] = mapped_column(TimeZone, default=None, comment='结束时间')
    summary: Mapped[dict[str, Any]] = mapped_column(JSONType, default_factory=dict, comment='计划摘要')

    items: Mapped[list[ShenlunTrainingPlanItem]] = relationship(
        init=False,
        back_populates='plan',
        cascade='all, delete-orphan',
        lazy='noload',
    )


class ShenlunTrainingPlanItem(Base):
    """训练计划中的每日/阶段任务。"""

    __tablename__ = 'agent_shenlun_training_plan_item'
    __table_args__ = (
        sa.CheckConstraint(
            "task_type IN ('practice','review','reflection')",
            name='ck_agent_training_plan_item_type',
        ),
        sa.CheckConstraint(
            "status IN ('pending','in_progress','completed','skipped')",
            name='ck_agent_training_plan_item_status',
        ),
        sa.Index('idx_agent_training_plan_item_plan_due', 'plan_id', 'due_date', 'status'),
        {'comment': '申论训练计划项'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    plan_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('agent_shenlun_training_plan.id', ondelete='CASCADE'),
        comment='计划 ID',
    )
    user_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('sys_user.id', ondelete='CASCADE'),
        comment='用户 ID',
    )
    task_type: Mapped[str] = mapped_column(sa.String(32), comment='practice/review/reflection')
    title: Mapped[str] = mapped_column(sa.String(200), comment='任务标题')
    instruction: Mapped[str] = mapped_column(UniversalText, comment='任务说明')
    due_date: Mapped[datetime | None] = mapped_column(TimeZone, default=None, comment='截止时间')
    target: Mapped[dict[str, Any]] = mapped_column(JSONType, default_factory=dict, comment='任务目标')
    status: Mapped[str] = mapped_column(
        sa.String(24),
        default='pending',
        comment='pending/in_progress/completed/skipped',
    )
    completed_time: Mapped[datetime | None] = mapped_column(TimeZone, default=None, comment='完成时间')

    plan: Mapped[ShenlunTrainingPlan] = relationship(init=False, back_populates='items', lazy='noload')
