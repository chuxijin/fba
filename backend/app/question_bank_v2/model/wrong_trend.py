"""掌握转换事实与统计覆盖起点，不从可变的 resolved_time 回填历史。"""

from datetime import datetime

import sqlalchemy as sa

from sqlalchemy.orm import Mapped, mapped_column

from backend.common.model import Base, TimeZone, UserMixin, id_key


class QbWrongMasteryEvent(Base, UserMixin):
    __tablename__ = 'qbank_v2_wrong_mastery_event'
    __table_args__ = (
        sa.ForeignKeyConstraint(
            ['user_id', 'question_id', 'wrong_state_id'],
            [
                'qbank_v2_wrong_question_state.user_id',
                'qbank_v2_wrong_question_state.question_id',
                'qbank_v2_wrong_question_state.id',
            ],
            name='fk_qbv2_mastery_event_state',
            ondelete='RESTRICT',
        ),
        sa.ForeignKeyConstraint(
            ['user_id', 'question_id', 'source_attempt_id'],
            [
                'qbank_v2_question_attempt.user_id',
                'qbank_v2_question_attempt.question_id',
                'qbank_v2_question_attempt.id',
            ],
            name='fk_qbv2_mastery_event_attempt',
            ondelete='RESTRICT',
        ),
        sa.UniqueConstraint('user_id', 'source_attempt_id', name='uq_qbv2_mastery_event_attempt'),
        sa.CheckConstraint("source IN ('attempt','manual')", name='ck_qbv2_mastery_event_source'),
        sa.Index('ix_qbv2_mastery_event_user_time', 'user_id', 'occurred_time'),
        {'comment': '错题实际达到掌握状态的不可变事件'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    user_id: Mapped[int] = mapped_column(sa.BigInteger, sa.ForeignKey('sys_user.id', ondelete='CASCADE'))
    question_id: Mapped[int] = mapped_column(sa.BigInteger)
    wrong_state_id: Mapped[int] = mapped_column(sa.BigInteger)
    occurred_time: Mapped[datetime] = mapped_column(TimeZone)
    source: Mapped[str] = mapped_column(sa.String(16))
    source_attempt_id: Mapped[int | None] = mapped_column(sa.BigInteger, default=None)


class QbWrongTrendCoverage(Base):
    """由迁移写入唯一记录；缺失时掌握数仍未知，不按首条事件推断零。"""

    __tablename__ = 'qbank_v2_wrong_trend_coverage'
    __table_args__ = (sa.CheckConstraint('id = 1', name='ck_qbv2_trend_coverage_singleton'),)

    id: Mapped[id_key] = mapped_column(init=False)
    started_time: Mapped[datetime] = mapped_column(TimeZone)
