#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Any

from sqlalchemy import JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from backend.common.model import Base, UserMixin, id_key


class McpConfig(Base, UserMixin):
    """MCP 配置表"""

    __tablename__ = 'mcp_config'

    __table_args__ = (UniqueConstraint('mcp', 'field', name='uix_mcp_field'),)

    id: Mapped[id_key] = mapped_column(init=False)
    mcp: Mapped[str] = mapped_column(String(64), index=True, comment='MCP 名称')
    field: Mapped[str] = mapped_column(String(64), index=True, comment='配置字段')
    value: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        comment='配置值(JSON)',
    )
