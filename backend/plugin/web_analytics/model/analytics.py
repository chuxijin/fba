from datetime import date, datetime

import sqlalchemy as sa

from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from backend.common.model import Base, TimeZone, UniversalText, id_key

CompatibleJSON = sa.JSON().with_variant(JSONB, 'postgresql')


class AnalyticsSite(Base):
    """Analytics site configuration."""

    __tablename__ = 'plugin_web_analytics_site'
    __table_args__ = ({'comment': '网站统计站点配置'},)

    id: Mapped[id_key] = mapped_column(init=False)
    site_key: Mapped[str] = mapped_column(sa.String(32), unique=True, index=True, comment='公开站点标识')
    name: Mapped[str] = mapped_column(sa.String(100), comment='站点名称')
    domains: Mapped[list[str]] = mapped_column(CompatibleJSON, comment='允许上报的域名')
    timezone: Mapped[str] = mapped_column(sa.String(64), default='Asia/Shanghai', comment='统计时区')
    is_active: Mapped[bool] = mapped_column(default=True, comment='是否启用')
    is_public: Mapped[bool] = mapped_column(default=False, comment='是否开放计数器')
    heatmap_enabled: Mapped[bool] = mapped_column(default=True, comment='是否采集热力图')
    replay_enabled: Mapped[bool] = mapped_column(default=True, comment='是否采集会话回放')
    replay_sample_rate: Mapped[float] = mapped_column(sa.Float, default=0.05, comment='回放采样率')
    event_retention_days: Mapped[int] = mapped_column(default=180, comment='事件保留天数')
    replay_retention_days: Mapped[int] = mapped_column(default=30, comment='回放保留天数')


class AnalyticsSession(Base):
    """Anonymous visitor session."""

    __tablename__ = 'plugin_web_analytics_session'
    __table_args__ = (
        sa.UniqueConstraint('site_id', 'session_key', name='uq_web_analytics_session_site_key'),
        sa.Index('ix_web_analytics_session_site_started', 'site_id', 'started_at'),
        sa.Index('ix_web_analytics_session_site_visitor', 'site_id', 'visitor_hash'),
        {'comment': '网站统计会话'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    site_id: Mapped[int] = mapped_column(sa.BigInteger, comment='站点 ID')
    session_key: Mapped[str] = mapped_column(sa.String(64), comment='匿名会话标识')
    visitor_hash: Mapped[str] = mapped_column(sa.String(64), comment='匿名访客哈希')
    ip_hash: Mapped[str] = mapped_column(sa.String(64), comment='匿名 IP 哈希')
    started_at: Mapped[datetime] = mapped_column(TimeZone, comment='开始时间')
    last_seen_at: Mapped[datetime] = mapped_column(TimeZone, comment='最后活动时间')
    entry_path: Mapped[str] = mapped_column(sa.String(1024), comment='入口页面')
    exit_path: Mapped[str] = mapped_column(sa.String(1024), comment='退出页面')
    referrer: Mapped[str | None] = mapped_column(sa.String(2048), default=None, comment='来源地址')
    referrer_host: Mapped[str | None] = mapped_column(sa.String(255), default=None, comment='来源域名')
    utm_source: Mapped[str | None] = mapped_column(sa.String(255), default=None, comment='UTM 来源')
    utm_medium: Mapped[str | None] = mapped_column(sa.String(255), default=None, comment='UTM 媒介')
    utm_campaign: Mapped[str | None] = mapped_column(sa.String(255), default=None, comment='UTM 活动')
    country: Mapped[str | None] = mapped_column(sa.String(64), default=None, comment='国家')
    region: Mapped[str | None] = mapped_column(sa.String(64), default=None, comment='省份')
    city: Mapped[str | None] = mapped_column(sa.String(64), default=None, comment='城市')
    browser: Mapped[str | None] = mapped_column(sa.String(128), default=None, comment='浏览器')
    os: Mapped[str | None] = mapped_column(sa.String(128), default=None, comment='操作系统')
    device: Mapped[str | None] = mapped_column(sa.String(128), default=None, comment='设备')
    pageviews: Mapped[int] = mapped_column(default=0, comment='页面浏览数')
    event_count: Mapped[int] = mapped_column(default=0, comment='事件数')
    duration_seconds: Mapped[int] = mapped_column(default=0, comment='活跃时长')


class AnalyticsEvent(Base):
    """Raw analytics event."""

    __tablename__ = 'plugin_web_analytics_event'
    __table_args__ = (
        sa.UniqueConstraint('site_id', 'event_key', name='uq_web_analytics_event_site_key'),
        sa.Index('ix_web_analytics_event_site_time', 'site_id', 'occurred_at'),
        sa.Index('ix_web_analytics_event_site_type_time', 'site_id', 'event_type', 'occurred_at'),
        {'comment': '网站统计原始事件'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    site_id: Mapped[int] = mapped_column(sa.BigInteger, comment='站点 ID')
    event_key: Mapped[str] = mapped_column(sa.String(64), comment='客户端事件标识')
    session_key: Mapped[str] = mapped_column(sa.String(64), comment='匿名会话标识')
    visitor_hash: Mapped[str] = mapped_column(sa.String(64), comment='匿名访客哈希')
    event_type: Mapped[str] = mapped_column(sa.String(32), comment='事件类型')
    path: Mapped[str] = mapped_column(sa.String(1024), comment='页面路径')
    occurred_at: Mapped[datetime] = mapped_column(TimeZone, comment='客户端发生时间')
    received_at: Mapped[datetime] = mapped_column(TimeZone, comment='服务端接收时间')
    event_name: Mapped[str | None] = mapped_column(sa.String(128), default=None, comment='自定义事件名')
    title: Mapped[str | None] = mapped_column(sa.String(512), default=None, comment='页面标题')
    referrer: Mapped[str | None] = mapped_column(sa.String(2048), default=None, comment='来源地址')
    properties: Mapped[dict | None] = mapped_column(CompatibleJSON, default=None, comment='事件属性')
    screen_width: Mapped[int | None] = mapped_column(default=None, comment='屏幕宽度')
    screen_height: Mapped[int | None] = mapped_column(default=None, comment='屏幕高度')
    viewport_width: Mapped[int | None] = mapped_column(default=None, comment='视口宽度')
    viewport_height: Mapped[int | None] = mapped_column(default=None, comment='视口高度')


class AnalyticsDaily(Base):
    """Daily site aggregate."""

    __tablename__ = 'plugin_web_analytics_daily'
    __table_args__ = (
        sa.UniqueConstraint('site_id', 'stats_date', name='uq_web_analytics_daily_site_date'),
        sa.Index('ix_web_analytics_daily_site_date', 'site_id', 'stats_date'),
        {'comment': '网站统计每日汇总'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    site_id: Mapped[int] = mapped_column(sa.BigInteger, comment='站点 ID')
    stats_date: Mapped[date] = mapped_column(sa.Date, comment='统计日期')
    pv: Mapped[int] = mapped_column(default=0, comment='页面浏览量')
    uv: Mapped[int] = mapped_column(default=0, comment='独立访客数')
    sessions: Mapped[int] = mapped_column(default=0, comment='会话数')
    events: Mapped[int] = mapped_column(default=0, comment='事件数')
    bounces: Mapped[int] = mapped_column(default=0, comment='跳出会话数')
    duration_seconds: Mapped[int] = mapped_column(default=0, comment='总活跃时长')


class AnalyticsReplaySession(Base):
    """Session replay metadata."""

    __tablename__ = 'plugin_web_analytics_replay_session'
    __table_args__ = (
        sa.UniqueConstraint('site_id', 'replay_key', name='uq_web_analytics_replay_site_key'),
        sa.Index('ix_web_analytics_replay_site_started', 'site_id', 'started_at'),
        {'comment': '网站会话回放元数据'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    site_id: Mapped[int] = mapped_column(sa.BigInteger, comment='站点 ID')
    replay_key: Mapped[str] = mapped_column(sa.String(64), comment='回放标识')
    session_key: Mapped[str] = mapped_column(sa.String(64), comment='匿名会话标识')
    visitor_hash: Mapped[str] = mapped_column(sa.String(64), comment='匿名访客哈希')
    path: Mapped[str] = mapped_column(sa.String(1024), comment='开始页面')
    started_at: Mapped[datetime] = mapped_column(TimeZone, comment='开始时间')
    last_event_at: Mapped[datetime] = mapped_column(TimeZone, comment='最后事件时间')
    chunk_count: Mapped[int] = mapped_column(default=0, comment='分片数')
    total_bytes: Mapped[int] = mapped_column(default=0, comment='总字节数')


class AnalyticsReplayChunk(Base):
    """Compressed rrweb event chunk."""

    __tablename__ = 'plugin_web_analytics_replay_chunk'
    __table_args__ = (
        sa.UniqueConstraint('site_id', 'replay_key', 'sequence', name='uq_web_analytics_replay_chunk_sequence'),
        sa.Index('ix_web_analytics_replay_chunk_lookup', 'site_id', 'replay_key', 'sequence'),
        {'comment': '网站会话回放分片'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    site_id: Mapped[int] = mapped_column(sa.BigInteger, comment='站点 ID')
    replay_key: Mapped[str] = mapped_column(sa.String(64), comment='回放标识')
    sequence: Mapped[int] = mapped_column(comment='分片序号')
    payload: Mapped[str] = mapped_column(UniversalText, comment='脱敏后的 rrweb 事件')
    occurred_at: Mapped[datetime] = mapped_column(TimeZone, comment='分片发生时间')
    encoding: Mapped[str] = mapped_column(sa.String(16), default='json', comment='内容编码')
    event_count: Mapped[int] = mapped_column(default=0, comment='事件数量')
