#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime

import sqlalchemy as sa

from sqlalchemy.orm import Mapped, mapped_column

from backend.common.model import Base, TimeZone, UniversalText, UserMixin, id_key


class Quest(Base, UserMixin):
    """悬赏任务表"""

    __tablename__ = 'quest_task'
    __table_args__ = (
        sa.Index('idx_quest_task_status_sort', 'status', 'sort'),
        {'comment': '悬赏任务表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    code: Mapped[str] = mapped_column(sa.String(64), unique=True, index=True, comment='任务码')
    name: Mapped[str] = mapped_column(sa.String(128), comment='任务名称')
    brief: Mapped[str] = mapped_column(sa.String(255), comment='任务简介')
    info: Mapped[str | None] = mapped_column(sa.String(500), default=None, comment='任务信息')
    detail: Mapped[str | None] = mapped_column(UniversalText, default=None, comment='任务详情')
    cover_image: Mapped[str | None] = mapped_column(sa.String(500), default=None, comment='封面图 URL')
    start_time: Mapped[datetime | None] = mapped_column(TimeZone, default=None, comment='开始时间')
    end_time: Mapped[datetime | None] = mapped_column(TimeZone, default=None, comment='结束时间')
    status: Mapped[int] = mapped_column(
        sa.SmallInteger,
        default=0,
        comment='状态(0 草稿 1 进行中 2 已暂停 3 已结束)',
    )
    total_quota: Mapped[int] = mapped_column(default=0, comment='总名额(0 不限)')
    claimed_count: Mapped[int] = mapped_column(default=0, comment='已领取数')
    max_claims_per_user: Mapped[int] = mapped_column(default=1, comment='单用户最大领取次数')
    claim_expire_seconds: Mapped[int] = mapped_column(default=0, comment='领取后完成期限秒数(0 不限)')
    submission_required: Mapped[bool] = mapped_column(default=True, comment='是否需要提交内容')
    review_required: Mapped[bool] = mapped_column(default=True, comment='是否需要人工审核')
    reward_type: Mapped[str] = mapped_column(sa.String(32), default='points', comment='奖励类型(vip/points/feature)')
    reward_data: Mapped[dict | None] = mapped_column(sa.JSON, default=None, comment='奖励数据')
    trigger_type: Mapped[str | None] = mapped_column(
        sa.String(64),
        default=None,
        index=True,
        comment='自动触发类型(None=人工领取, 如 invite.accepted/groupbuy.team_success)',
    )
    trigger_target: Mapped[int] = mapped_column(
        default=0,
        comment='自动触发达成阈值(0 当 trigger_type 为空时无意义)',
    )
    trigger_payload: Mapped[dict | None] = mapped_column(
        sa.JSON,
        default=None,
        comment='自动触发匹配条件(预留扩展, 如 channel 限定)',
    )
    sort: Mapped[int] = mapped_column(default=0, comment='排序(数字越小越靠前)')
