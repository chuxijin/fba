#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Any

import sqlalchemy as sa

from sqlalchemy.dialects.mysql import JSON as MySQLJSON
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from backend.common.enums import DataBaseType
from backend.common.model import Base, UniversalText, id_key
from backend.core.conf import settings

JSONType = JSONB if DataBaseType.postgresql == settings.DATABASE_TYPE else MySQLJSON


class AgentTask(Base):
    """Agent 任务表"""

    __tablename__ = 'plugin_agents_task'
    __table_args__ = (
        sa.Index('idx_plugin_agents_task_status', 'status'),
        sa.Index('idx_plugin_agents_task_user_id', 'user_id'),
        sa.Index('idx_plugin_agents_task_agent_type', 'agent_type'),
        {'comment': 'Agent 任务表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    agent_type: Mapped[str] = mapped_column(sa.String(64), comment='agent 类型 shenlun/english_essay/xingce/interview')
    user_id: Mapped[int] = mapped_column(sa.BigInteger, comment='提交用户 ID')
    provider_id: Mapped[int] = mapped_column(sa.BigInteger, comment='AI 供应商 ID')
    model_id: Mapped[str] = mapped_column(sa.String(128), comment='主力模型 ID')
    input_payload: Mapped[dict[str, Any]] = mapped_column(JSONType, comment='输入参数')
    status: Mapped[str] = mapped_column(sa.String(32), default='pending', comment='任务状态')
    stage: Mapped[str | None] = mapped_column(sa.String(64), default=None, comment='当前阶段')
    progress: Mapped[float] = mapped_column(sa.Float, default=0.0, comment='进度 0-1')
    state_snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSONType, default=None, comment='中间快照')
    report: Mapped[dict[str, Any] | None] = mapped_column(JSONType, default=None, comment='最终报告')
    traces: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONType, default=None, comment='执行轨迹')
    quota_consumed: Mapped[bool] = mapped_column(sa.Boolean, default=False, comment='是否已扣权益')
    error_code: Mapped[str | None] = mapped_column(sa.String(64), default=None, comment='错误码')
    error_message: Mapped[str | None] = mapped_column(UniversalText, default=None, comment='错误信息')
