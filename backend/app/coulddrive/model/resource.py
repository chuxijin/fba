#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Numeric, String, Text, Integer, Date, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.common.model import Base, UserMixin, id_key
from backend.utils.timezone import timezone

if TYPE_CHECKING:
    from backend.app.coulddrive.model.user import DriveAccount


class Resource(Base, UserMixin):
    """资源表"""

    __tablename__ = 'yp_resource'

    id: Mapped[id_key] = mapped_column(init=False)
    
    # 必填字段
    domain: Mapped[str] = mapped_column(String(100), comment='领域')
    subject: Mapped[str] = mapped_column(String(100), comment='科目')
    main_name: Mapped[str] = mapped_column(String(200), comment='主要名字')
    title: Mapped[str] = mapped_column(String(255), comment='标题')
    resource_type: Mapped[str] = mapped_column(String(50), comment='资源类型')
    url_type: Mapped[str] = mapped_column(String(50), comment='链接类型')
    url: Mapped[str] = mapped_column(String(500), comment='链接')
    user_id: Mapped[int] = mapped_column(
        ForeignKey('yp_user.id', ondelete='CASCADE'), comment='所属用户ID'
    )
    
    # 可选字段（有默认值）
    description: Mapped[str | None] = mapped_column(Text, default=None, comment='描述')
    resource_intro: Mapped[str | None] = mapped_column(Text, default=None, comment='资源介绍')
    resource_image: Mapped[str | None] = mapped_column(String(500), default=None, comment='资源图片')
    content: Mapped[str | None] = mapped_column(Text, default=None, comment='内容')
    remark: Mapped[str | None] = mapped_column(Text, default=None, comment='备注')
    share_id: Mapped[str | None] = mapped_column(String(200), default=None, comment='分享ID')
    pwd_id: Mapped[str | None] = mapped_column(String(100), default=None, comment='密码ID')
    extract_code: Mapped[str | None] = mapped_column(String(50), default=None, comment='提取码')
    file_id: Mapped[str | None] = mapped_column(String(200), default=None, comment='文件ID')
    file_size: Mapped[int | None] = mapped_column(BigInteger, default=None, comment='文件大小')
    file_only_num: Mapped[str | None] = mapped_column(String(200), default=None, comment='文件唯一编号')
    path_info: Mapped[str | None] = mapped_column(Text, default=None, comment='路径信息')
    price: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), default=None, comment='价格')
    suggested_price: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), default=None, comment='建议价格')
    expired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None, comment='实际过期时间')
    expired_left: Mapped[int | None] = mapped_column(BigInteger, default=None, comment='剩余过期天数')
    uk_uid: Mapped[str | None] = mapped_column(String(200), default=None, comment='用户唯一标识')
    
    # 有默认值的字段
    is_temp_file: Mapped[bool] = mapped_column(Boolean, default=False, comment='是否为临时文件')
    view_count: Mapped[int] = mapped_column(BigInteger, default=0, comment='浏览量')
    sort: Mapped[int] = mapped_column(default=0, comment='排序')
    status: Mapped[int] = mapped_column(default=1, comment='状态(0停用 1正常)')
    audit_status: Mapped[int] = mapped_column(default=0, comment='审核状态(0待审核 1通过 2拒绝)')
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, comment='是否删除')
    expired_type: Mapped[int] = mapped_column(default=0, comment='过期类型(0永久 1定时)')

    # 关系
    user: Mapped[DriveAccount] = relationship(init=False, back_populates='resources')
    view_history: Mapped[list["ResourceViewHistory"]] = relationship(
        init=False,
        back_populates="resource",
        cascade="all, delete-orphan",
        foreign_keys="ResourceViewHistory.pwd_id",
        primaryjoin="Resource.pwd_id == foreign(ResourceViewHistory.pwd_id)"
    )


class ResourceViewHistory(Base):
    """资源浏览量历史记录表"""

    __tablename__ = 'resource_view_history'

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True, comment='主键ID')
    pwd_id: Mapped[str] = mapped_column(String(100), index=True, comment='资源唯一ID')
    view_count: Mapped[int] = mapped_column(Integer, default=0, comment='当时的浏览量')
    record_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default_factory=timezone.now, comment='记录时间'
    )
    
    # 关系
    resource: Mapped[Resource] = relationship(
        init=False, 
        back_populates="view_history",
        foreign_keys="ResourceViewHistory.pwd_id",
        primaryjoin="ResourceViewHistory.pwd_id == Resource.pwd_id"
    )

    # 索引
    __table_args__ = (
        Index('idx_pwd_record_time', 'pwd_id', 'record_time'),
        Index('idx_record_time', 'record_time'),
    ) 