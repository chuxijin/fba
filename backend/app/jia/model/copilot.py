#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Optional

from sqlalchemy import ForeignKey, String, Text, Integer, Float
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import JSONB

from backend.common.model import Base, id_key


class JiaCopilotSession(Base):
    """Copilot 会话表"""
    __tablename__ = 'jia_copilot_session'

    id: Mapped[id_key] = mapped_column(init=False)
    user_id: Mapped[int] = mapped_column(comment='用户ID', index=True)
    
    title: Mapped[str | None] = mapped_column(String(255), default="新对话", comment='会话标题')
    model: Mapped[str] = mapped_column(String(50), default="gpt-5.1", comment='模型名称')
    assistant_type: Mapped[str] = mapped_column(String(50), default="home", comment='助手类型: home/food/exercise/item')
    
    # 上下文参数
    context_count: Mapped[int] = mapped_column(default=10, comment='上下文轮数')
    temperature: Mapped[float] = mapped_column(Float, default=0.7, comment='随机性')
    
    # 关联消息
    messages: Mapped[list["JiaCopilotMessage"]] = relationship(
        init=False, back_populates="session", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<CopilotSession {self.title}>"


class JiaCopilotMessage(Base):
    """Copilot 消息表 (标准化为单条消息)"""
    __tablename__ = 'jia_copilot_message'

    id: Mapped[id_key] = mapped_column(init=False)
    session_id: Mapped[int] = mapped_column(ForeignKey('jia_copilot_session.id'), comment='会话ID', index=True)
    
    role: Mapped[str] = mapped_column(String(20), comment='角色: user/assistant/system/tool')
    content: Mapped[str | None] = mapped_column(Text, nullable=True, comment='消息内容')

    # 多模态支持 [{"type": "image", "url": "..."}]
    attachments: Mapped[list[dict] | None] = mapped_column(JSONB, default=None, comment='附件(图片/文件)')
    
    # Tool Calling 支持
    tool_calls: Mapped[list[dict] | None] = mapped_column(JSONB, default=None, comment='工具调用请求')
    tool_call_id: Mapped[str | None] = mapped_column(String(100), default=None, comment='工具调用结果ID')
    
    # 结构化数据/元数据 (用于存储生成的计划JSON、推荐列表等)
    meta: Mapped[dict | None] = mapped_column(JSONB, default=None, comment='结构化元数据')
    
    # 关联会话
    session: Mapped["JiaCopilotSession"] = relationship(init=False, back_populates="messages")
