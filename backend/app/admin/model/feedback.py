#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime

import sqlalchemy as sa

from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from backend.common.model import Base, TimeZone, id_key

CompatibleJSONB = sa.JSON().with_variant(JSONB, 'postgresql')


class FeedbackType:
    """反馈类型"""

    BUG = 'bug'
    CONTENT_ERROR = 'content_error'
    PRODUCT_SUGGESTION = 'product_suggestion'
    FEATURE_REQUEST = 'feature_request'
    EXPERIENCE = 'experience'
    OTHER = 'other'


class FeedbackStatus:
    """反馈状态"""

    PENDING = 'pending'
    PROCESSING = 'processing'
    RESOLVED = 'resolved'
    REJECTED = 'rejected'


class Feedback(Base):
    """系统反馈表"""

    __tablename__ = 'sys_feedback'
    __table_args__ = (
        sa.Index('idx_feedback_status_created', 'status', 'created_time'),
        sa.Index('idx_feedback_source', 'source_app', 'source_platform'),
        sa.Index('idx_feedback_target', 'target_type', 'target_id'),
        sa.Index('idx_feedback_user_created', 'user_id', 'created_time'),
        {'comment': '系统反馈表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)

    content: Mapped[str] = mapped_column(sa.Text, comment='反馈内容')
    feedback_type: Mapped[str] = mapped_column(sa.String(32), default=FeedbackType.OTHER, comment='反馈类型')
    contact: Mapped[str | None] = mapped_column(sa.String(128), default=None, comment='联系方式')
    images: Mapped[list[str] | None] = mapped_column(CompatibleJSONB, default=None, comment='图片列表')

    source_app: Mapped[str | None] = mapped_column(sa.String(32), default=None, comment='来源应用')
    source_platform: Mapped[str | None] = mapped_column(sa.String(32), default=None, comment='来源平台')
    page_path: Mapped[str | None] = mapped_column(sa.String(512), default=None, comment='页面路径')
    target_type: Mapped[str | None] = mapped_column(sa.String(32), default=None, comment='关联目标类型')
    target_id: Mapped[str | None] = mapped_column(sa.String(64), default=None, comment='关联目标 ID')
    target_text: Mapped[str | None] = mapped_column(sa.String(255), default=None, comment='关联目标描述')

    status: Mapped[str] = mapped_column(sa.String(20), default=FeedbackStatus.PENDING, comment='处理状态')
    reply_content: Mapped[str | None] = mapped_column(sa.Text, default=None, comment='处理回复')
    read_time: Mapped[datetime | None] = mapped_column(TimeZone, default=None, comment='首次查看时间')
    handled_by: Mapped[int | None] = mapped_column(sa.BigInteger, default=None, comment='处理人 ID')
    handled_time: Mapped[datetime | None] = mapped_column(TimeZone, default=None, comment='处理时间')

    ip_address: Mapped[str | None] = mapped_column(sa.String(64), default=None, comment='IP 地址')
    user_agent: Mapped[str | None] = mapped_column(sa.String(512), default=None, comment='用户代理')
    user_id: Mapped[int | None] = mapped_column(sa.BigInteger, default=None, comment='提交用户 ID（匿名为空）')
