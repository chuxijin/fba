from datetime import date, datetime
from typing import Any, Literal

from pydantic import ConfigDict, Field, field_validator

from backend.common.schema import SchemaBase


class CreateSiteParam(SchemaBase):
    name: str = Field(min_length=1, max_length=100, description='站点名称')
    domains: list[str] = Field(min_length=1, max_length=20, description='允许上报的域名')
    timezone: str = Field('Asia/Shanghai', max_length=64, description='统计时区')
    is_public: bool = Field(False, description='是否开放公开计数器')
    heatmap_enabled: bool = Field(True, description='是否采集热力图')
    replay_enabled: bool = Field(True, description='是否采集会话回放')
    replay_sample_rate: float = Field(0.05, ge=0, le=1, description='回放采样率')
    event_retention_days: int = Field(180, ge=1, le=3650, description='事件保留天数')
    replay_retention_days: int = Field(30, ge=1, le=365, description='回放保留天数')

    @field_validator('domains')
    @classmethod
    def normalize_domains(cls, value: list[str]) -> list[str]:
        domains = []
        for domain in value:
            normalized = domain.strip().lower().rstrip('.')
            if '://' in normalized or '/' in normalized or not normalized:
                raise ValueError('域名不能包含协议或路径')
            domains.append(normalized)
        return list(dict.fromkeys(domains))


class UpdateSiteParam(SchemaBase):
    name: str | None = Field(None, min_length=1, max_length=100, description='站点名称')
    domains: list[str] | None = Field(None, min_length=1, max_length=20, description='允许上报的域名')
    timezone: str | None = Field(None, max_length=64, description='统计时区')
    is_active: bool | None = Field(None, description='是否启用')
    is_public: bool | None = Field(None, description='是否开放公开计数器')
    heatmap_enabled: bool | None = Field(None, description='是否采集热力图')
    replay_enabled: bool | None = Field(None, description='是否采集会话回放')
    replay_sample_rate: float | None = Field(None, ge=0, le=1, description='回放采样率')
    event_retention_days: int | None = Field(None, ge=1, le=3650, description='事件保留天数')
    replay_retention_days: int | None = Field(None, ge=1, le=365, description='回放保留天数')

    @field_validator('domains')
    @classmethod
    def normalize_domains(cls, value: list[str] | None) -> list[str] | None:
        return CreateSiteParam.normalize_domains(value) if value is not None else None


class SiteDetail(SchemaBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    site_key: str
    name: str
    domains: list[str]
    timezone: str
    is_active: bool
    is_public: bool
    heatmap_enabled: bool
    replay_enabled: bool
    replay_sample_rate: float
    event_retention_days: int
    replay_retention_days: int
    created_time: datetime
    updated_time: datetime | None = None


class AnalyticsEventParam(SchemaBase):
    id: str = Field(min_length=8, max_length=64, description='客户端事件 ID')
    type: Literal['pageview', 'heartbeat', 'click', 'scroll', 'web_vital', 'custom']
    name: str | None = Field(None, max_length=128, description='自定义事件名')
    path: str = Field('/', min_length=1, max_length=2048, description='页面地址或路径')
    title: str | None = Field(None, max_length=512, description='页面标题')
    referrer: str | None = Field(None, max_length=4096, description='来源页面')
    timestamp: datetime | None = Field(None, description='客户端发生时间')
    properties: dict[str, Any] | None = Field(None, description='事件属性')
    screen_width: int | None = Field(None, ge=0, le=20000)
    screen_height: int | None = Field(None, ge=0, le=20000)
    viewport_width: int | None = Field(None, ge=0, le=20000)
    viewport_height: int | None = Field(None, ge=0, le=20000)


class CollectBatchParam(SchemaBase):
    site: str = Field(min_length=8, max_length=32, description='站点公开标识')
    visitor: str = Field(min_length=8, max_length=128, description='匿名访客标识')
    session: str = Field(min_length=8, max_length=64, description='匿名会话标识')
    events: list[AnalyticsEventParam] = Field(min_length=1, max_length=50, description='事件批次')


class CollectResult(SchemaBase):
    accepted: int
    duplicate: int


class OverviewDetail(SchemaBase):
    pv: int = 0
    uv: int = 0
    ip: int = 0
    sessions: int = 0
    events: int = 0
    bounces: int = 0
    bounce_rate: float = 0
    duration_seconds: int = 0
    average_duration_seconds: float = 0
    active_visitors: int = 0


class DailyTrendDetail(SchemaBase):
    date: date
    pv: int
    uv: int
    sessions: int
    events: int
    bounces: int
    duration_seconds: int


class CounterDetail(SchemaBase):
    site_pv: int
    site_uv: int
    page_pv: int | None = None


class HeatmapPointDetail(SchemaBase):
    x_ratio: float
    y_ratio: float
    count: int


class DimensionDetail(SchemaBase):
    name: str
    value: int


class ReplayChunkParam(SchemaBase):
    site: str = Field(min_length=8, max_length=32)
    visitor: str = Field(min_length=8, max_length=128)
    session: str = Field(min_length=8, max_length=64)
    replay: str = Field(min_length=8, max_length=64)
    sequence: int = Field(ge=0, le=10000)
    path: str = Field('/', min_length=1, max_length=2048)
    timestamp: datetime | None = None
    events: list[dict[str, Any]] = Field(min_length=1, max_length=5000)


class ReplayDetail(SchemaBase):
    model_config = ConfigDict(from_attributes=True)

    replay_key: str
    session_key: str
    path: str
    started_at: datetime
    last_event_at: datetime
    chunk_count: int
    total_bytes: int
