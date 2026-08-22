from __future__ import annotations

from datetime import datetime
from typing import Any

import sqlalchemy as sa

from sqlalchemy.dialects.mysql import JSON as MYSQL_JSON
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from backend.common.enums import DataBaseType
from backend.common.model import Base, TimeZone, UniversalText, id_key
from backend.core.conf import settings

JSONType = JSONB if DataBaseType.postgresql == settings.DATABASE_TYPE else MYSQL_JSON


class AgentRun(Base):
    """Agent 批改运行表"""

    __tablename__ = 'agent_run'
    __table_args__ = (
        sa.UniqueConstraint('idempotency_key', name='uq_agent_run_idempotency_key'),
        sa.Index('idx_agent_run_user_status', 'user_id', 'status', 'created_time'),
        sa.Index('idx_agent_run_subject', 'subject_type', 'subject_id', 'created_time'),
        sa.Index('idx_agent_run_agent_key', 'agent_key', 'workflow_key', 'created_time'),
        {'comment': 'Agent 运行任务表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    agent_key: Mapped[str] = mapped_column(sa.String(64), comment='Agent 稳定键')
    agent_version: Mapped[str] = mapped_column(sa.String(32), comment='Agent 版本')
    workflow_key: Mapped[str] = mapped_column(sa.String(64), comment='工作流键')
    workflow_version: Mapped[str] = mapped_column(sa.String(32), comment='工作流版本')
    user_id: Mapped[int] = mapped_column(sa.BigInteger, comment='用户 ID')
    subject_type: Mapped[str] = mapped_column(sa.String(64), comment='业务对象类型')
    subject_id: Mapped[int] = mapped_column(sa.BigInteger, comment='业务对象 ID')
    idempotency_key: Mapped[str] = mapped_column(sa.String(160), comment='幂等键')
    status: Mapped[str] = mapped_column(
        sa.String(24),
        default='queued',
        comment='queued/running/succeeded/failed/cancelled',
    )
    stage: Mapped[str | None] = mapped_column(sa.String(64), default=None, comment='当前阶段')
    progress: Mapped[float] = mapped_column(sa.Float, default=0.0, comment='进度 0-1')
    input_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict, comment='输入快照')
    result_summary: Mapped[str | None] = mapped_column(UniversalText, default=None, comment='结果摘要')
    result_payload: Mapped[dict[str, Any] | None] = mapped_column(JSONType, default=None, comment='结构化报告')
    config_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict, comment='运行配置')
    error_code: Mapped[str | None] = mapped_column(sa.String(64), default=None, comment='错误码')
    error_message: Mapped[str | None] = mapped_column(UniversalText, default=None, comment='错误信息')
    started_time: Mapped[datetime | None] = mapped_column(TimeZone, default=None, comment='开始时间')
    finished_time: Mapped[datetime | None] = mapped_column(TimeZone, default=None, comment='完成时间')
