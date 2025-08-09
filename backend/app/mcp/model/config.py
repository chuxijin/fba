#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Any

from sqlalchemy import JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from backend.common.model import Base, UserMixin, id_key


class McpConfig(Base, UserMixin):
    """MCP 配置表"""

    # 与历史表名保持一致（原插件未显式声明表名，默认类名小写）
    __tablename__ = "mcpconfig"

    id: Mapped[id_key] = mapped_column(init=False)
    mcp: Mapped[str] = mapped_column(String(64), unique=True, index=True, comment="MCP 名称")
    config: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, comment="配置 JSON")


