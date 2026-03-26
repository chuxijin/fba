#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime

import sqlalchemy as sa

from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from backend.common.model import Base, TimeZone, id_key
from backend.utils.timezone import timezone


class TrailPoint(Base):
    """轨迹点表"""

    __tablename__ = 'trail_point'
    __table_args__ = (
        sa.Index('idx_trail_point_user_time', 'user_id', 'recorded_at'),
        sa.Index('idx_trail_point_location', 'longitude', 'latitude'),
        {'comment': '轨迹点表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    user_id: Mapped[int] = mapped_column(sa.BigInteger, index=True, comment='用户 ID')

    # ========== 核心定位 ==========
    longitude: Mapped[float] = mapped_column(sa.Double, comment='经度')
    latitude: Mapped[float] = mapped_column(sa.Double, comment='纬度')

    # ========== 定位质量 ==========
    accuracy: Mapped[float | None] = mapped_column(sa.Float, default=None, comment='定位精度(米)')
    provider: Mapped[str | None] = mapped_column(sa.String(16), default=None, comment='定位来源: gps/wifi/cell')

    # ========== 运动状态(轨迹回放核心) ==========
    speed: Mapped[float | None] = mapped_column(sa.Float, default=None, comment='速度(m/s)')
    bearing: Mapped[float | None] = mapped_column(sa.Float, default=None, comment='方向角(0-360度, 正北为0)')
    altitude: Mapped[float | None] = mapped_column(sa.Double, default=None, comment='海拔(米)')

    # ========== 位置语义(高德逆地理编码) ==========
    location_name: Mapped[str | None] = mapped_column(sa.String(128), default=None, comment='POI 名称')
    address: Mapped[str | None] = mapped_column(sa.String(256), default=None, comment='详细地址')
    aoi_name: Mapped[str | None] = mapped_column(sa.String(128), default=None, comment='AOI 名称')

    # ========== 地理区域 ==========
    country: Mapped[str | None] = mapped_column(sa.String(32), default=None, comment='国家')
    province: Mapped[str | None] = mapped_column(sa.String(32), default=None, comment='省')
    city: Mapped[str | None] = mapped_column(sa.String(32), default=None, comment='城市')
    district: Mapped[str | None] = mapped_column(sa.String(32), default=None, comment='区')
    street: Mapped[str | None] = mapped_column(sa.String(64), default=None, comment='街道')
    street_num: Mapped[str | None] = mapped_column(sa.String(32), default=None, comment='门牌号')
    city_code: Mapped[str | None] = mapped_column(sa.String(16), default=None, comment='城市编码')
    ad_code: Mapped[str | None] = mapped_column(sa.String(16), default=None, comment='区域编码')

    # ========== App 记录 ==========
    foreground_app: Mapped[str | None] = mapped_column(sa.String(128), default=None, comment='前台 App 包名')
    foreground_app_name: Mapped[str | None] = mapped_column(sa.String(64), default=None, comment='前台 App 名称')

    # ========== 设备环境 ==========
    battery_level: Mapped[int | None] = mapped_column(sa.SmallInteger, default=None, comment='电池电量(0-100)')
    wifi_ssid: Mapped[str | None] = mapped_column(sa.String(64), default=None, comment='WiFi 名称')
    step_count: Mapped[int | None] = mapped_column(default=None, comment='当日累计步数')
    weather: Mapped[str | None] = mapped_column(sa.String(32), default=None, comment='天气')

    # ========== 定位策略 ==========
    interval_used: Mapped[int] = mapped_column(default=60, comment='本次实际定位间隔(秒)')
    is_moving: Mapped[bool] = mapped_column(default=False, comment='是否在移动中')

    # ========== 用户标注 ==========
    note: Mapped[str | None] = mapped_column(sa.String(1024), default=None, comment='用户备注')

    # ========== 扩展字段 ==========
    extra_data: Mapped[dict | None] = mapped_column(JSONB, default=None, comment='扩展数据')

    # ========== 客户端记录时间 ==========
    recorded_at: Mapped[datetime] = mapped_column(
        TimeZone, default_factory=timezone.now, comment='客户端记录时间'
    )
