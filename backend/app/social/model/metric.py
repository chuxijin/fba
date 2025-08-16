#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.common.model import Base, UserMixin, id_key
from backend.utils.timezone import timezone


class SocialWorkMetric(Base, UserMixin):
    """作品数据表"""

    __tablename__ = "social_work_metric"

    id: Mapped[id_key] = mapped_column(init=False)

    work_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("social_work.id", ondelete="CASCADE", use_alter=True), index=True, comment="作品ID"
    )
    view_count: Mapped[int] = mapped_column(BigInteger, default=0, comment="浏览量")
    like_count: Mapped[int] = mapped_column(BigInteger, default=0, comment="点赞数")
    favorite_count: Mapped[int] = mapped_column(BigInteger, default=0, comment="收藏数")
    comment_count: Mapped[int] = mapped_column(BigInteger, default=0, comment="评论数")
    share_count: Mapped[int] = mapped_column(BigInteger, default=0, comment="转发/分享数")
    record_time: Mapped[DateTime] = mapped_column(DateTime(timezone=True), default_factory=timezone.now, comment="记录时间")

    work: Mapped[SocialWork] = relationship(init=False, back_populates="metrics")

    __table_args__ = (
        Index("idx_social_work_metric_work_time", "work_id", "record_time"),
        UniqueConstraint("work_id", "record_time", name="uk_social_work_metric_work_time"),
    )


