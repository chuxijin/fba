#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from sqlalchemy import String, Text, Integer, JSON
from sqlalchemy.orm import Mapped, mapped_column

from backend.common.model import Base, id_key, UserMixin


class FeedbackType:
    RESOURCE_DEAD = "resource_dead"     # 资源失效
    UPDATE_REQUEST = "update_request"   # 资源催更
    RESOURCE_HELP = "resource_help"     # 帮找资料
    SUGGESTION = "suggestion"           # 功能建议
    CORRECTION = "correction"           # 错误纠正
    CONTRIBUTION = "contribution"       # 集思广益/贡献答案
    OTHER = "other"                     # 其他


class FeedbackStatus:
    PENDING = "pending"       # 待处理
    PROCESSING = "processing" # 处理中
    RESOLVED = "resolved"     # 已解决
    REJECTED = "rejected"     # 已驳回


class GkFeedback(Base, UserMixin):
    """公考反馈表"""
    __tablename__ = 'gk_feedback'

    id: Mapped[id_key] = mapped_column(init=False)
    
    # Core Fields
    type: Mapped[str] = mapped_column(String(50), comment='反馈类型')
    content: Mapped[str] = mapped_column(Text, comment='反馈内容')
    target_source: Mapped[str | None] = mapped_column(String(512), default=None, comment='关联链接/目标')
    
    # Extra Info
    images: Mapped[list | None] = mapped_column(JSON, default=None, comment='图片附件列表')
    contact: Mapped[str | None] = mapped_column(String(100), default=None, comment='联系方式')
    
    # Status
    # default status is PENDING
    status: Mapped[str] = mapped_column(String(20), default=FeedbackStatus.PENDING, comment='处理状态')
    reply: Mapped[str | None] = mapped_column(String(512), default=None, comment='管理员回复/备注')
    
    # Meta
    ip_address: Mapped[str | None] = mapped_column(String(50), default=None, comment='IP地址')
    view_status: Mapped[int] = mapped_column(Integer, default=0, comment='查看状态 0未读 1已读')
