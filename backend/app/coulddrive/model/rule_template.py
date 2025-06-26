#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import String, Text, Integer, Boolean, DateTime, JSON
from sqlalchemy.orm import Mapped, mapped_column

from backend.common.model import Base, UserMixin, id_key


class RuleTemplate(Base, UserMixin):
    """规则模板表"""
    
    __tablename__ = "rule_template"
    
    id: Mapped[id_key] = mapped_column(init=False)
    template_name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True, comment="模板名称")
    template_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True, comment="模板类型")
    description: Mapped[str | None] = mapped_column(String(500), nullable=True, comment="模板描述")
    
    # 规则配置
    rule_config: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, comment="规则配置")
    
    # 分类和标签
    category: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True, comment="分类")
    tags: Mapped[list[str] | None] = mapped_column(JSON, nullable=True, comment="标签")
    
    # 状态字段
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, comment="是否启用", init=False)
    is_system: Mapped[bool] = mapped_column(Boolean, default=False, comment="是否系统内置模板", init=False)
    
    # 使用统计
    usage_count: Mapped[int] = mapped_column(Integer, default=0, comment="使用次数", init=False)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, comment="最后使用时间", init=False)
    
    def __repr__(self) -> str:
        return f"<RuleTemplate(id={self.id}, template_name={self.template_name}, template_type={self.template_type})>"
