#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import datetime

import sqlalchemy as sa

from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.mydrive.model.account import CompatibleJSONB
from backend.common.model import Base, TimeZone, UserMixin, id_key


class MyDriveResource(Base, UserMixin):
    """MyDrive 资源表"""

    __tablename__ = 'mydrive_resource'
    __table_args__ = (
        sa.Index('idx_mydrive_resource_owner_status', 'owner_id', 'status'),
        sa.Index('idx_mydrive_resource_category_type', 'category_id', 'resource_type'),
        sa.Index('idx_mydrive_resource_hot', 'hot'),
        {'comment': 'MyDrive 资源表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    owner_id: Mapped[int] = mapped_column(sa.BigInteger, index=True, comment='所属用户 ID')
    category_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('sys_category.id', ondelete='CASCADE'),
        comment='分类 ID',
    )
    title: Mapped[str] = mapped_column(sa.String(255), comment='资源标题')
    resource_type: Mapped[str] = mapped_column(sa.String(50), comment='资源类型')
    description: Mapped[str] = mapped_column(sa.Text, default='', comment='资源介绍')
    images: Mapped[list] = mapped_column(CompatibleJSONB, default_factory=list, comment='资源图片列表')
    org_name: Mapped[str] = mapped_column(sa.String(100), default='', comment='机构或老师名称')
    tags: Mapped[list[str]] = mapped_column(CompatibleJSONB, default_factory=list, comment='资源标签')
    content: Mapped[str] = mapped_column(sa.Text, default='', comment='搜索内容')
    view_count: Mapped[int] = mapped_column(sa.BigInteger, default=0, comment='平台浏览量')
    search_count: Mapped[int] = mapped_column(sa.BigInteger, default=0, comment='平台搜索次数')
    hot: Mapped[int] = mapped_column(sa.Integer, default=0, comment='热点值')
    last_viewed_at: Mapped[datetime | None] = mapped_column(TimeZone, default=None, comment='最近浏览时间')
    last_searched_at: Mapped[datetime | None] = mapped_column(TimeZone, default=None, comment='最近搜索时间')
    status: Mapped[str] = mapped_column(sa.String(32), default='enabled', comment='状态')
    audit_status: Mapped[str] = mapped_column(sa.String(32), default='approved', comment='审核状态')
    temp_policy: Mapped[int] = mapped_column(sa.Integer, default=0, comment='临时策略(0无操作 1定时删除 2定时刷新 3定时更新)')
    sort: Mapped[int] = mapped_column(sa.Integer, default=0, comment='排序')
    resource_expired_at: Mapped[datetime | None] = mapped_column(TimeZone, default=None, comment='资源过期时间')

    share: Mapped[MyDriveResourceShare | None] = relationship(
        init=False,
        back_populates='resource',
        lazy='noload',
        uselist=False,
        cascade='all, delete-orphan',
    )
    view_history: Mapped[list[MyDriveResourceViewHistory]] = relationship(
        init=False,
        back_populates='resource',
        lazy='noload',
        cascade='all, delete-orphan',
    )


class MyDriveResourceShare(Base):
    """MyDrive 资源分享表"""

    __tablename__ = 'mydrive_resource_share'
    __table_args__ = (
        sa.UniqueConstraint('resource_id', name='uq_mydrive_resource_share_resource'),
        sa.Index('idx_mydrive_resource_share_provider_status', 'provider', 'share_status'),
        sa.Index('idx_mydrive_resource_share_key', 'share_key'),
        {'comment': 'MyDrive 资源分享表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    resource_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('mydrive_resource.id', ondelete='CASCADE'),
        comment='资源 ID',
    )
    provider: Mapped[str] = mapped_column(sa.String(64), comment='网盘驱动标识')
    account_id: Mapped[int | None] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('mydrive_account.id', ondelete='SET NULL'),
        default=None,
        comment='网盘账户 ID',
    )
    source_type: Mapped[str] = mapped_column(sa.String(32), default='imported_link', comment='来源类型')
    source_ref: Mapped[dict] = mapped_column(CompatibleJSONB, default_factory=dict, comment='来源定位信息')
    share_url: Mapped[str] = mapped_column(sa.String(1000), default='', comment='分享链接')
    share_id: Mapped[str] = mapped_column(sa.String(255), default='', comment='分享 ID')
    share_key: Mapped[str] = mapped_column(sa.String(255), default='', comment='分享唯一标识')
    extract_code: Mapped[str] = mapped_column(sa.String(50), default='', comment='提取码')
    share_title: Mapped[str] = mapped_column(sa.String(255), default='', comment='网盘分享标题')
    share_status: Mapped[str] = mapped_column(sa.String(32), default='unknown', comment='分享状态')
    share_audit_status: Mapped[str] = mapped_column(sa.String(32), default='unknown', comment='分享审核状态')
    share_expired_at: Mapped[datetime | None] = mapped_column(TimeZone, default=None, comment='分享过期时间')
    expires_in_days: Mapped[int] = mapped_column(sa.Integer, default=0, comment='有效期天数')
    share_meta: Mapped[dict] = mapped_column(CompatibleJSONB, default_factory=dict, comment='分享原始信息')
    file_id: Mapped[str] = mapped_column(sa.String(255), default='', comment='文件 ID')
    file_name: Mapped[str] = mapped_column(sa.String(512), default='', comment='文件名称')
    file_path: Mapped[str] = mapped_column(sa.String(1024), default='', comment='文件路径')
    is_directory: Mapped[bool] = mapped_column(default=False, comment='是否目录')
    file_size: Mapped[int | None] = mapped_column(sa.BigInteger, default=None, comment='文件大小')
    file_type: Mapped[str] = mapped_column(sa.String(50), default='', comment='文件类型')

    resource: Mapped[MyDriveResource] = relationship(init=False, back_populates='share', lazy='noload')


class MyDriveResourceViewHistory(Base):
    """MyDrive 资源浏览历史表"""

    __tablename__ = 'mydrive_resource_view_history'
    __table_args__ = (
        sa.Index('idx_mydrive_resource_view_resource_time', 'resource_id', 'record_time'),
        {'comment': 'MyDrive 资源浏览历史表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    resource_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('mydrive_resource.id', ondelete='CASCADE'),
        comment='资源 ID',
    )
    view_count: Mapped[int] = mapped_column(sa.BigInteger, default=0, comment='当时浏览量')
    record_time: Mapped[datetime] = mapped_column(TimeZone, default_factory=datetime.now, comment='记录时间')

    resource: Mapped[MyDriveResource] = relationship(init=False, back_populates='view_history', lazy='noload')
