#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import JSON, BigInteger, DateTime, ForeignKey, Index, String, UniqueConstraint, select
from sqlalchemy.orm import Mapped, column_property, mapped_column, relationship

from backend.app.social.model.metric import SocialWorkMetric
from backend.common.model import Base, UserMixin, id_key

if TYPE_CHECKING:
    from backend.app.social.model.account import SocialAccount
    from backend.app.social.model.metric import SocialWorkMetric


class SocialWork(Base, UserMixin):
    """作品表"""

    __tablename__ = "social_work"

    id: Mapped[id_key] = mapped_column(init=False)

    account_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("social_account.id", ondelete="CASCADE", use_alter=True), comment="账号ID"
    )
    external_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True, comment="平台作品ID")
    work_url: Mapped[str] = mapped_column(String(700), unique=True, comment="作品地址")
    copywriting: Mapped[dict[str, object] | None] = mapped_column(JSON, default=None, comment="文案(JSON) —— {title, content, topics}")
    published_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), default=None, comment="发布时间")

    account: Mapped[SocialAccount] = relationship(init=False, back_populates="works", lazy='noload')
    metrics: Mapped[list[SocialWorkMetric]] = relationship(
        init=False, back_populates="work", cascade="all, delete-orphan", lazy='noload'
    )

    # 最新快照指标（通过相关子查询计算）
    latest_view_count: Mapped[int | None] = column_property(
        select(SocialWorkMetric.view_count)
        .where(SocialWorkMetric.work_id == id)
        .order_by(SocialWorkMetric.record_time.desc())
        .limit(1)
        .correlate_except(SocialWorkMetric)
        .scalar_subquery()
    )
    latest_like_count: Mapped[int | None] = column_property(
        select(SocialWorkMetric.like_count)
        .where(SocialWorkMetric.work_id == id)
        .order_by(SocialWorkMetric.record_time.desc())
        .limit(1)
        .correlate_except(SocialWorkMetric)
        .scalar_subquery()
    )
    latest_favorite_count: Mapped[int | None] = column_property(
        select(SocialWorkMetric.favorite_count)
        .where(SocialWorkMetric.work_id == id)
        .order_by(SocialWorkMetric.record_time.desc())
        .limit(1)
        .correlate_except(SocialWorkMetric)
        .scalar_subquery()
    )
    latest_comment_count: Mapped[int | None] = column_property(
        select(SocialWorkMetric.comment_count)
        .where(SocialWorkMetric.work_id == id)
        .order_by(SocialWorkMetric.record_time.desc())
        .limit(1)
        .correlate_except(SocialWorkMetric)
        .scalar_subquery()
    )
    latest_share_count: Mapped[int | None] = column_property(
        select(SocialWorkMetric.share_count)
        .where(SocialWorkMetric.work_id == id)
        .order_by(SocialWorkMetric.record_time.desc())
        .limit(1)
        .correlate_except(SocialWorkMetric)
        .scalar_subquery()
    )

    __table_args__ = (
        Index("idx_social_work_account_id", "account_id"),
        UniqueConstraint("account_id", "external_id", name="uk_social_work_account_external_id"),
    )

