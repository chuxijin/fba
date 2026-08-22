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


class AgentRunStep(Base):
    """Agent 节点执行轨迹表"""

    __tablename__ = 'agent_run_step'
    __table_args__ = (
        sa.UniqueConstraint('run_id', 'step_no', name='uq_agent_run_step_no'),
        sa.Index('idx_agent_run_step_run', 'run_id', 'step_no'),
        {'comment': 'Agent 节点执行轨迹表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    run_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('agent_run.id', ondelete='CASCADE'),
        index=True,
        comment='Agent 运行 ID',
    )
    step_no: Mapped[int] = mapped_column(sa.Integer, comment='节点序号')
    node_key: Mapped[str] = mapped_column(sa.String(64), comment='节点键')
    status: Mapped[str] = mapped_column(sa.String(24), default='running', comment='running/succeeded/failed')
    input_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict, comment='节点输入摘要')
    output_snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSONType, default=None, comment='节点输出摘要')
    model_name: Mapped[str | None] = mapped_column(sa.String(128), default=None, comment='模型名称')
    tokens_in: Mapped[int] = mapped_column(sa.Integer, default=0, comment='输入 token')
    tokens_out: Mapped[int] = mapped_column(sa.Integer, default=0, comment='输出 token')
    duration_ms: Mapped[int] = mapped_column(sa.Integer, default=0, comment='耗时毫秒')
    error_message: Mapped[str | None] = mapped_column(UniversalText, default=None, comment='节点错误')
    started_time: Mapped[datetime | None] = mapped_column(TimeZone, default=None, comment='开始时间')
    finished_time: Mapped[datetime | None] = mapped_column(TimeZone, default=None, comment='结束时间')
