from datetime import datetime

import sqlalchemy as sa

from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.learning.enums import LearningFocusMode, LearningFocusStatus
from backend.common.model import Base, TimeZone, UniversalText, id_key
from backend.utils.timezone import timezone

CompatibleJSONB = sa.JSON().with_variant(JSONB, 'postgresql')


class LearningFocusSession(Base):
    """学习任务专注过程记录。"""

    __tablename__ = 'learning_focus_session'
    __table_args__ = (
        sa.Index('idx_learning_focus_user_status', 'user_id', 'status'),
        sa.Index('idx_learning_focus_task_started', 'task_id', 'started_at'),
        sa.CheckConstraint("mode IN ('pomodoro','countdown','stopwatch')", name='ck_learning_focus_mode'),
        sa.CheckConstraint(
            "status IN ('running','paused','completed','canceled')",
            name='ck_learning_focus_status',
        ),
        {'comment': '学习专注记录'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    task_id: Mapped[int | None] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('learning_task.id', ondelete='CASCADE'),
        comment='学习任务 ID，空表示自由专注',
    )
    user_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('sys_user.id', ondelete='CASCADE'),
        comment='用户 ID',
    )
    started_at: Mapped[datetime] = mapped_column(TimeZone, default_factory=timezone.now, comment='开始时间')
    mode: Mapped[str] = mapped_column(sa.String(16), default=LearningFocusMode.pomodoro.value, comment='专注模式')
    status: Mapped[str] = mapped_column(sa.String(16), default=LearningFocusStatus.running.value, comment='专注状态')
    planned_minutes: Mapped[int] = mapped_column(sa.Integer, default=25, comment='计划专注分钟')
    focused_seconds: Mapped[int] = mapped_column(sa.Integer, default=0, comment='有效专注秒数')
    paused_seconds: Mapped[int] = mapped_column(sa.Integer, default=0, comment='暂停秒数')
    interrupt_count: Mapped[int] = mapped_column(sa.Integer, default=0, comment='中断次数')
    paused_at: Mapped[datetime | None] = mapped_column(TimeZone, default=None, comment='暂停时间')
    ended_at: Mapped[datetime | None] = mapped_column(TimeZone, default=None, comment='结束时间')
    remark: Mapped[str | None] = mapped_column(UniversalText, default=None, comment='备注')


class LearningCompletionRecord(Base):
    """学习任务完成结果快照。"""

    __tablename__ = 'learning_completion_record'
    __table_args__ = (
        sa.Index('idx_learning_completion_task_time', 'task_id', 'completed_at'),
        sa.Index('idx_learning_completion_user_time', 'user_id', 'completed_at'),
        {'comment': '学习任务完成记录'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    task_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('learning_task.id', ondelete='CASCADE'),
        comment='学习任务 ID',
    )
    user_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('sys_user.id', ondelete='CASCADE'),
        comment='用户 ID',
    )
    completed_at: Mapped[datetime] = mapped_column(TimeZone, default_factory=timezone.now, comment='完成时间')
    completion_source: Mapped[str] = mapped_column(sa.String(32), default='manual', comment='完成来源')
    duration_seconds: Mapped[int] = mapped_column(sa.Integer, default=0, comment='累计耗时秒数')
    actual_metrics: Mapped[dict | None] = mapped_column(CompatibleJSONB, default=None, comment='实际指标')
    extra_data: Mapped[dict | None] = mapped_column(CompatibleJSONB, default=None, comment='扩展完成数据')
