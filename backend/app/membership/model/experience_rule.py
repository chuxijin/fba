#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sqlalchemy as sa

from sqlalchemy.orm import Mapped, mapped_column

from backend.common.model import Base, UniversalText, id_key


class MembershipExperienceRule(Base):
    """会员经验规则表"""

    __tablename__ = 'membership_experience_rule'
    __table_args__ = (
        sa.Index('idx_membership_exp_rule_event_status', 'event_code', 'status', 'sort'),
        sa.Index('idx_membership_exp_rule_match', 'event_code', 'family_code', 'cycle_day', 'status'),
        {'comment': '会员经验规则表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    event_code: Mapped[str] = mapped_column(sa.String(32), comment='事件编码')
    name: Mapped[str] = mapped_column(sa.String(64), comment='规则名称')
    exp_delta: Mapped[int] = mapped_column(comment='经验奖励值')
    family_code: Mapped[str | None] = mapped_column(sa.String(16), default=None, comment='等级族群')
    cycle_day: Mapped[int | None] = mapped_column(sa.SmallInteger, default=None, comment='周期第几天')
    min_practice_count: Mapped[int] = mapped_column(default=0, comment='最低做题数')
    min_practice_duration: Mapped[int] = mapped_column(default=0, comment='最低练习时长（秒）')
    sort: Mapped[int] = mapped_column(default=0, comment='排序')
    status: Mapped[int] = mapped_column(default=1, comment='状态(0停用 1启用)')
    description: Mapped[str | None] = mapped_column(UniversalText, default=None, comment='描述')
