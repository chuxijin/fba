from __future__ import annotations

from datetime import time
from typing import TYPE_CHECKING, Any

import sqlalchemy as sa

from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.common.model import Base, UserMixin, id_key

from .common import CompatibleJSONB

if TYPE_CHECKING:
    from backend.app.admin.model.category import Category

    from .knowledge import QbKnowledgePoint


class QbUserPracticePreference(Base, UserMixin):
    """Typed high-frequency practice preferences with extensible custom tabs."""

    __tablename__ = 'qbank_v2_user_practice_preference'
    __table_args__ = (
        sa.UniqueConstraint('user_id', 'deleted', name='uq_qbv2_preference_user'),
        sa.CheckConstraint(
            "practice_mode IN ('practice','exercise','exam','mock','memorize','review','adaptive')",
            name='ck_qbv2_preference_mode',
        ),
        sa.CheckConstraint(
            "theme_mode IN ('light','dark','auto')",
            name='ck_qbv2_preference_theme',
        ),
        sa.CheckConstraint(
            "random_practice_year_range IN ('unlimited','last_3_years','last_5_years')",
            name='ck_qbv2_preference_year_range',
        ),
        sa.CheckConstraint('mastery_threshold BETWEEN 1 AND 20', name='ck_qbv2_preference_mastery'),
        sa.CheckConstraint('random_practice_count BETWEEN 10 AND 100', name='ck_qbv2_preference_count'),
        sa.CheckConstraint('review_daily_limit BETWEEN 1 AND 200', name='ck_qbv2_preference_review_limit'),
        sa.Index('ix_qbv2_preference_category', 'current_category_id'),
        {'comment': '用户题库学习偏好表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    user_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('sys_user.id', ondelete='CASCADE'),
        comment='用户 ID',
    )
    current_category_id: Mapped[int | None] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('sys_category.id', ondelete='SET NULL'),
        default=None,
        comment='当前题库业务分类 ID',
    )
    current_knowledge_point_id: Mapped[int | None] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('qbank_v2_knowledge_point.id', ondelete='SET NULL'),
        default=None,
        comment='当前知识点导航根节点 ID',
    )
    practice_mode: Mapped[str] = mapped_column(sa.String(16), default='practice', comment='默认练习模式')
    mastery_threshold: Mapped[int] = mapped_column(sa.SmallInteger, default=3, comment='错题连续答对掌握阈值')
    theme_mode: Mapped[str] = mapped_column(sa.String(16), default='light', comment='light/dark/auto')
    random_practice_count: Mapped[int] = mapped_column(sa.SmallInteger, default=20, comment='默认随机练习题数')
    random_practice_year_range: Mapped[str] = mapped_column(
        sa.String(24),
        default='unlimited',
        comment='随机练习年份范围',
    )
    review_reminder_enabled: Mapped[bool] = mapped_column(default=False, comment='是否启用错题复习提醒')
    review_reminder_time: Mapped[time] = mapped_column(
        sa.Time,
        default=time(20, 0),
        comment='用户本地每日提醒时间',
    )
    review_reminder_timezone: Mapped[str] = mapped_column(
        sa.String(64),
        default='Asia/Shanghai',
        comment='IANA 提醒时区',
    )
    review_daily_limit: Mapped[int] = mapped_column(
        sa.SmallInteger,
        default=30,
        comment='单日复习题数上限',
    )
    custom_tabs: Mapped[dict[str, list[dict[str, Any]]]] = mapped_column(
        CompatibleJSONB,
        default_factory=dict,
        comment='按分类范围隔离的用户自定义导航标签',
    )

    current_category: Mapped[Category | None] = relationship(
        init=False,
        foreign_keys=[current_category_id],
        lazy='noload',
    )
    current_knowledge_point: Mapped[QbKnowledgePoint | None] = relationship(
        init=False,
        foreign_keys=[current_knowledge_point_id],
        lazy='noload',
    )
