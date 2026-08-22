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


class AgentGradingFeedback(Base):
    """申论批改人工纠正表"""

    __tablename__ = 'agent_grading_feedback'
    __table_args__ = (
        sa.UniqueConstraint('run_id', 'point_key', 'scope', name='uq_agent_grading_feedback_point'),
        sa.Index('idx_agent_grading_feedback_question', 'question_id', 'scope', 'created_time'),
        {'comment': '申论批改人工纠正表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    run_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('agent_run.id', ondelete='CASCADE'),
        comment='Agent 运行 ID',
    )
    user_id: Mapped[int] = mapped_column(sa.BigInteger, comment='操作用户 ID')
    question_id: Mapped[int] = mapped_column(sa.BigInteger, comment='题库 V2 题目 ID')
    point_key: Mapped[str] = mapped_column(sa.String(80), comment='采分点稳定键')
    corrected_status: Mapped[str] = mapped_column(sa.String(16), comment='hit/partial/miss')
    scope: Mapped[str] = mapped_column(sa.String(16), default='report', comment='report/question')
    corrected_quote: Mapped[str] = mapped_column(UniversalText, default='', comment='纠正后的答案证据')
    note: Mapped[str] = mapped_column(UniversalText, default='', comment='纠正说明')
    before_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict, comment='纠正前采分点快照')
    after_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict, comment='纠正后采分点快照')
