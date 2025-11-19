#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime

import sqlalchemy as sa

from sqlalchemy.orm import Mapped, mapped_column

from backend.common.model import Base, TimeZone, id_key


class BiliWork(Base):
    """B 站作品表"""

    __tablename__ = 'bili_work'

    id: Mapped[id_key] = mapped_column(init=False)
    work_id: Mapped[str] = mapped_column(sa.String(128), unique=True, index=True, comment='B 站作品 ID(BV 号/专栏 ID 等)')
    title: Mapped[str] = mapped_column(sa.String(256), comment='标题')
    work_type: Mapped[str] = mapped_column(
        sa.String(32), index=True, comment='作品类型(video 视频/dynamic 动态/article 文章/column 专栏)'
    )
    aid: Mapped[int | None] = mapped_column(sa.BigInteger, default=None, index=True, comment='视频 AID（用于评论 API）')
    url: Mapped[str | None] = mapped_column(sa.String(512), default=None, comment='作品链接')
    view_count: Mapped[int] = mapped_column(default=0, comment='播放量/阅读量')
    like_count: Mapped[int] = mapped_column(default=0, comment='点赞数')
    comment_count: Mapped[int] = mapped_column(default=0, comment='评论数')
    coin_count: Mapped[int] = mapped_column(default=0, comment='投币数')
    share_count: Mapped[int] = mapped_column(default=0, comment='分享数')
    favorite_count: Mapped[int] = mapped_column(default=0, comment='收藏数')
    publish_time: Mapped[datetime | None] = mapped_column(TimeZone, init=False, default=None, comment='发布时间')
    mid: Mapped[str | None] = mapped_column(sa.String(64), default=None, index=True, comment='所属 B 站用户 MID')
