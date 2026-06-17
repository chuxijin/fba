#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime

import sqlalchemy as sa

from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from backend.common.model import Base, TimeZone, id_key
from backend.utils.timezone import timezone


class ActcodeBatch(Base):
    """激活码批次表"""

    __tablename__ = 'actcode_batch'

    id: Mapped[id_key] = mapped_column(init=False)
    app_id: Mapped[str] = mapped_column(sa.String(32), index=True, comment='应用 ID')
    batch_no: Mapped[str] = mapped_column(sa.String(64), unique=True, index=True, comment='批次编号')
    name: Mapped[str] = mapped_column(sa.String(128), comment='批次名称')
    reward_type: Mapped[str] = mapped_column(sa.String(32), comment='权益类型(vip,points,feature)')
    reward_data: Mapped[dict] = mapped_column(JSONB, comment='权益数据 JSONB')
    generator_config: Mapped[dict | None] = mapped_column(sa.JSON, default=None, comment='生成器配置 JSON')
    total_count: Mapped[int] = mapped_column(default=0, comment='总数量')
    used_count: Mapped[int] = mapped_column(default=0, comment='已使用数量')
    valid_from: Mapped[datetime | None] = mapped_column(TimeZone, default=None, comment='有效期开始')
    valid_to: Mapped[datetime | None] = mapped_column(TimeZone, default=None, comment='有效期结束')
    max_use_per_code: Mapped[int] = mapped_column(default=1, comment='单码最大使用次数')
    status: Mapped[int] = mapped_column(default=1, comment='状态(0停用 1启用)')


class Actcode(Base):
    """激活码表"""

    __tablename__ = 'actcode'
    __table_args__ = (
        sa.Index('ix_actcode_fk_batch_id', 'batch_id'),
        {'comment': '激活码表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    batch_id: Mapped[int] = mapped_column(sa.BigInteger, comment='批次 ID')
    code: Mapped[str] = mapped_column(sa.String(64), unique=True, index=True, comment='激活码')
    used_count: Mapped[int] = mapped_column(default=0, comment='已使用次数')
    status: Mapped[int] = mapped_column(default=0, index=True, comment='状态(0未使用 1已使用 2已过期)')


class ActcodeUsage(Base):
    """激活码使用记录表"""

    __tablename__ = 'actcode_usage'

    id: Mapped[id_key] = mapped_column(init=False)
    code_id: Mapped[int] = mapped_column(sa.BigInteger, index=True, comment='激活码 ID')
    app_id: Mapped[str] = mapped_column(sa.String(32), index=True, comment='应用 ID')
    user_id: Mapped[str] = mapped_column(sa.String(64), index=True, comment='用户 ID')
    used_time: Mapped[datetime] = mapped_column(TimeZone, init=False, default_factory=timezone.now, comment='使用时间')
    ip_address: Mapped[str | None] = mapped_column(sa.String(64), default=None, comment='IP 地址')
    device_info: Mapped[str | None] = mapped_column(sa.String(256), default=None, comment='设备信息')
