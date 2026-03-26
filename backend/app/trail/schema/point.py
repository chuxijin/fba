#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime
from typing import Any

from pydantic import Field

from backend.common.schema import SchemaBase


class CreateTrailPointParam(SchemaBase):
    """创建轨迹点参数"""

    longitude: float = Field(description='经度')
    latitude: float = Field(description='纬度')
    accuracy: float | None = Field(None, description='定位精度(米)')
    provider: str | None = Field(None, max_length=16, description='定位来源: gps/wifi/cell')
    speed: float | None = Field(None, description='速度(m/s)')
    bearing: float | None = Field(None, description='方向角(0-360)')
    altitude: float | None = Field(None, description='海拔(米)')
    location_name: str | None = Field(None, max_length=128, description='POI 名称')
    address: str | None = Field(None, max_length=256, description='详细地址')
    aoi_name: str | None = Field(None, max_length=128, description='AOI 名称')
    country: str | None = Field(None, max_length=32, description='国家')
    province: str | None = Field(None, max_length=32, description='省')
    city: str | None = Field(None, max_length=32, description='城市')
    district: str | None = Field(None, max_length=32, description='区')
    street: str | None = Field(None, max_length=64, description='街道')
    street_num: str | None = Field(None, max_length=32, description='门牌号')
    city_code: str | None = Field(None, max_length=16, description='城市编码')
    ad_code: str | None = Field(None, max_length=16, description='区域编码')
    foreground_app: str | None = Field(None, max_length=128, description='前台 App 包名')
    foreground_app_name: str | None = Field(None, max_length=64, description='前台 App 名称')
    battery_level: int | None = Field(None, ge=0, le=100, description='电池电量(0-100)')
    wifi_ssid: str | None = Field(None, max_length=64, description='WiFi 名称')
    step_count: int | None = Field(None, description='当日累计步数')
    weather: str | None = Field(None, max_length=32, description='天气')
    interval_used: int = Field(60, description='本次实际定位间隔(秒)')
    is_moving: bool = Field(False, description='是否在移动中')
    note: str | None = Field(None, max_length=1024, description='用户备注')
    extra_data: dict[str, Any] | None = Field(None, description='扩展数据')
    recorded_at: datetime = Field(description='客户端记录时间')


class BatchCreateTrailPointParam(SchemaBase):
    """批量创建轨迹点参数"""

    points: list[CreateTrailPointParam] = Field(description='轨迹点列表', min_length=1, max_length=500)


class GetTrailPointDetail(SchemaBase):
    """轨迹点详情"""

    model_config = SchemaBase.model_config.copy()
    model_config['from_attributes'] = True

    id: int = Field(description='轨迹点 ID')
    user_id: int = Field(description='用户 ID')
    longitude: float = Field(description='经度')
    latitude: float = Field(description='纬度')
    accuracy: float | None = Field(None, description='定位精度(米)')
    provider: str | None = Field(None, description='定位来源')
    speed: float | None = Field(None, description='速度(m/s)')
    bearing: float | None = Field(None, description='方向角')
    altitude: float | None = Field(None, description='海拔(米)')
    location_name: str | None = Field(None, description='POI 名称')
    address: str | None = Field(None, description='详细地址')
    aoi_name: str | None = Field(None, description='AOI 名称')
    country: str | None = Field(None, description='国家')
    province: str | None = Field(None, description='省')
    city: str | None = Field(None, description='城市')
    district: str | None = Field(None, description='区')
    street: str | None = Field(None, description='街道')
    street_num: str | None = Field(None, description='门牌号')
    city_code: str | None = Field(None, description='城市编码')
    ad_code: str | None = Field(None, description='区域编码')
    foreground_app: str | None = Field(None, description='前台 App 包名')
    foreground_app_name: str | None = Field(None, description='前台 App 名称')
    battery_level: int | None = Field(None, description='电池电量')
    wifi_ssid: str | None = Field(None, description='WiFi 名称')
    step_count: int | None = Field(None, description='当日累计步数')
    weather: str | None = Field(None, description='天气')
    interval_used: int = Field(description='定位间隔(秒)')
    is_moving: bool = Field(description='是否在移动中')
    note: str | None = Field(None, description='用户备注')
    extra_data: dict[str, Any] | None = Field(None, description='扩展数据')
    recorded_at: datetime = Field(description='客户端记录时间')
