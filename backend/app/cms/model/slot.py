#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime

import sqlalchemy as sa

from sqlalchemy.orm import Mapped, mapped_column

from backend.common.model import Base, TimeZone, UniversalText, id_key


class CmsSlot(Base):
    """内容运营位表"""

    __tablename__ = 'cms_slot'
    __table_args__ = (
        sa.Index('idx_cms_slot_active', 'status', 'scene', 'slot_type', 'priority'),
        sa.Index('idx_cms_slot_window', 'start_time', 'end_time'),
        {'comment': '内容运营位表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    code: Mapped[str] = mapped_column(sa.String(64), unique=True, index=True, comment='业务码')
    name: Mapped[str] = mapped_column(sa.String(128), comment='内部名称')
    slot_type: Mapped[str] = mapped_column(
        sa.String(32),
        comment='形态(curtain/banner/popup/splash/float/notice)',
    )
    scene: Mapped[str] = mapped_column(sa.String(64), comment='触发场景(app_launch/home/...)')
    title: Mapped[str | None] = mapped_column(sa.String(255), default=None, comment='标题')
    subtitle: Mapped[str | None] = mapped_column(sa.String(255), default=None, comment='副标题/摘要')
    image_url: Mapped[str | None] = mapped_column(sa.String(500), default=None, comment='主图 URL')
    detail: Mapped[str | None] = mapped_column(UniversalText, default=None, comment='富文本详情')
    jump_type: Mapped[str] = mapped_column(
        sa.String(32),
        default='none',
        comment='跳转类型(none/url/miniprogram/quest/content/custom)',
    )
    jump_target: Mapped[str | None] = mapped_column(sa.String(500), default=None, comment='跳转目标(URL 或业务 ID)')
    jump_extra: Mapped[dict | None] = mapped_column(sa.JSON, default=None, comment='扩展跳转参数')
    start_time: Mapped[datetime | None] = mapped_column(TimeZone, default=None, comment='投放开始时间')
    end_time: Mapped[datetime | None] = mapped_column(TimeZone, default=None, comment='投放结束时间')
    status: Mapped[int] = mapped_column(
        sa.SmallInteger,
        default=0,
        comment='状态(0 草稿 1 上线 2 已下线)',
    )
    priority: Mapped[int] = mapped_column(default=0, comment='优先级(数字越大越靠前)')
    target_user_type: Mapped[int] = mapped_column(
        sa.SmallInteger,
        default=0,
        comment='目标用户类型(0 全部 1 新用户 2 会员 3 普通用户 99 自定义)',
    )
    target_min_member_level: Mapped[int] = mapped_column(default=0, comment='最低会员等级权重(0 不限)')
    target_extra: Mapped[dict | None] = mapped_column(sa.JSON, default=None, comment='扩展分群条件')
    max_show_per_user: Mapped[int] = mapped_column(default=0, comment='单用户终生最多展示次数(0 不限)')
    max_show_per_day_per_user: Mapped[int] = mapped_column(default=0, comment='单用户每日最多展示次数(0 不限)')
    close_dismiss_count: Mapped[int] = mapped_column(default=0, comment='关闭 N 次后该用户不再展示(0 不限)')
    can_close: Mapped[bool] = mapped_column(default=True, comment='是否允许用户主动关闭')
    extra: Mapped[dict | None] = mapped_column(sa.JSON, default=None, comment='形态特有字段兜底')
    created_by: Mapped[int | None] = mapped_column(sa.BigInteger, default=None, comment='创建者用户 ID')
