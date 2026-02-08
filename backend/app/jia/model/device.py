#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from backend.common.model import Base, TimeZone, id_key


class JiaDevice(Base):
    """用户设备表 - 存储 FCM Token"""

    __tablename__ = 'jia_device'

    id: Mapped[id_key] = mapped_column(init=False)
    user_id: Mapped[int] = mapped_column(sa.BigInteger, index=True, comment='用户 ID')
    fcm_token: Mapped[str] = mapped_column(sa.String(512), unique=True, comment='FCM Token')
    device_name: Mapped[str | None] = mapped_column(sa.String(128), default=None, comment='设备名称')
    device_type: Mapped[str | None] = mapped_column(sa.String(32), default=None, comment='设备类型 (android/ios)')
    is_active: Mapped[bool] = mapped_column(default=True, comment='是否活跃')
    last_active_time: Mapped[datetime | None] = mapped_column(
        TimeZone, init=False, default=None, comment='最后活跃时间'
    )
