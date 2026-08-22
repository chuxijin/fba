from __future__ import annotations

from decimal import Decimal
from typing import Any

import sqlalchemy as sa

from sqlalchemy.dialects.mysql import JSON as MYSQL_JSON
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from backend.common.enums import DataBaseType
from backend.common.model import Base, UniversalText, id_key
from backend.core.conf import settings

JSONType = JSONB if DataBaseType.postgresql == settings.DATABASE_TYPE else MYSQL_JSON


class AgentCalibrationAnchor(Base):
    """申论整卷人工校准锚点表"""

    __tablename__ = 'agent_calibration_anchor'
    __table_args__ = (
        sa.UniqueConstraint(
            'agent_key',
            'session_id',
            name='uq_agent_calibration_anchor_session',
        ),
        sa.Index('idx_agent_calibration_anchor_ready', 'agent_key', 'status', 'bank_revision_id'),
        sa.Index('idx_agent_calibration_anchor_session', 'session_id', 'created_time'),
        {'comment': 'Agent 整卷人工校准锚点表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    agent_key: Mapped[str] = mapped_column(sa.String(64), comment='Agent 稳定键')
    bank_revision_id: Mapped[int] = mapped_column(sa.BigInteger, comment='题库 V2 题库版本 ID')
    session_id: Mapped[int] = mapped_column(sa.BigInteger, comment='题库 V2 考试会话 ID')
    user_id: Mapped[int] = mapped_column(sa.BigInteger, comment='答题用户 ID')
    actual_score_percent: Mapped[Decimal] = mapped_column(sa.Numeric(7, 3), comment='人工实际百分制得分')
    predicted_score_percent: Mapped[Decimal] = mapped_column(sa.Numeric(7, 3), comment='Agent 原始百分制得分')
    actual_total_score: Mapped[Decimal] = mapped_column(sa.Numeric(10, 3), comment='人工实际整卷得分')
    predicted_total_score: Mapped[Decimal] = mapped_column(sa.Numeric(10, 3), comment='Agent 原始整卷得分')
    paper_total_score: Mapped[Decimal] = mapped_column(sa.Numeric(10, 3), comment='试卷总分')
    source_type: Mapped[str] = mapped_column(
        sa.String(32),
        comment='manual_session/manual_attempt_sum',
    )
    source_hash: Mapped[str] = mapped_column(sa.String(64), comment='当前人工结果和 Agent 运行组合指纹')
    status: Mapped[str] = mapped_column(sa.String(16), default='ready', comment='ready/excluded')
    exclusion_reason: Mapped[str | None] = mapped_column(
        UniversalText,
        default=None,
        comment='排除原因',
    )
    metadata_payload: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict, comment='逐题锚点与审计快照')


class AgentCalibrationPolicy(Base):
    """申论批改校准策略版本表"""

    __tablename__ = 'agent_calibration_policy'
    __table_args__ = (
        sa.UniqueConstraint('agent_key', 'source_hash', name='uq_agent_calibration_policy_source'),
        sa.UniqueConstraint('agent_key', 'active_key', name='uq_agent_calibration_policy_active'),
        sa.Index('idx_agent_calibration_policy_scope', 'agent_key', 'scope_type', 'scope_key', 'status'),
        {'comment': 'Agent 校准策略版本表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    agent_key: Mapped[str] = mapped_column(sa.String(64), comment='Agent 稳定键')
    policy_version: Mapped[str] = mapped_column(sa.String(64), comment='策略算法版本')
    scope_type: Mapped[str] = mapped_column(
        sa.String(24),
        comment='global/question_type/bank_revision',
    )
    scope_key: Mapped[str] = mapped_column(sa.String(160), comment='范围稳定键')
    source_hash: Mapped[str] = mapped_column(sa.String(64), comment='拟合输入与范围指纹')
    active_key: Mapped[str | None] = mapped_column(
        sa.String(192),
        default=None,
        comment='仅 active 策略占用的跨数据库唯一键',
    )
    status: Mapped[str] = mapped_column(sa.String(16), default='draft', comment='draft/active/retired')
    anchor_count: Mapped[int] = mapped_column(sa.Integer, default=0, comment='参与拟合的锚点数')
    paper_count: Mapped[int] = mapped_column(sa.Integer, default=0, comment='参与拟合的试卷数')
    policy_payload: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict, comment='可执行策略')
    metrics_payload: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict, comment='验证指标')
