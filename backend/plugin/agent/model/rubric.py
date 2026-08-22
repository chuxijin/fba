from __future__ import annotations

from typing import Any

import sqlalchemy as sa

from sqlalchemy.dialects.mysql import JSON as MYSQL_JSON
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from backend.common.enums import DataBaseType
from backend.common.model import Base, UniversalText, id_key
from backend.core.conf import settings

JSONType = JSONB if DataBaseType.postgresql == settings.DATABASE_TYPE else MYSQL_JSON


class AgentRubric(Base):
    """申论题目评分基准缓存表"""

    __tablename__ = 'agent_rubric'
    __table_args__ = (
        sa.UniqueConstraint(
            'agent_key',
            'question_id',
            'reference_set_hash',
            'source_hash',
            'rubric_version',
            name='uq_agent_rubric_source',
        ),
        sa.Index('idx_agent_rubric_question', 'agent_key', 'question_id', 'status'),
        {'comment': 'Agent 可复用评分基准表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    agent_key: Mapped[str] = mapped_column(sa.String(64), comment='Agent 稳定键')
    question_id: Mapped[int] = mapped_column(sa.BigInteger, comment='题库 V2 题目 ID')
    reference_set_hash: Mapped[str] = mapped_column(sa.String(64), comment='参考答案集合指纹')
    source_hash: Mapped[str] = mapped_column(sa.String(64), comment='题干和材料来源指纹')
    rubric_version: Mapped[str] = mapped_column(sa.String(64), comment='评分基准版本')
    status: Mapped[str] = mapped_column(sa.String(24), default='ready', comment='ready/stale/failed')
    provider: Mapped[str | None] = mapped_column(sa.String(128), default=None, comment='模型供应商')
    model_name: Mapped[str | None] = mapped_column(sa.String(128), default=None, comment='模型名称')
    rubric_payload: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict, comment='评分基准内容')
    error_message: Mapped[str | None] = mapped_column(UniversalText, default=None, comment='构建错误')
