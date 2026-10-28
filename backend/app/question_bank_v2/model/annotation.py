import sqlalchemy as sa

from sqlalchemy.orm import Mapped, mapped_column

from backend.app.question_bank_v2.model.common import CompatibleJSONB
from backend.common.model import Base, id_key


class QbQuestionAnnotation(Base):
    """用户在某次练习或复盘中的文字标注集合。"""

    __tablename__ = 'qbank_v2_question_annotation'
    __table_args__ = (
        sa.UniqueConstraint('user_id', 'question_id', 'context_key', name='uq_qbv2_annotation_context'),
        sa.CheckConstraint('save_version >= 1', name='ck_qbv2_annotation_version'),
        {'comment': '用户题干与材料高亮批注'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    user_id: Mapped[int] = mapped_column(sa.BigInteger, sa.ForeignKey('sys_user.id', ondelete='CASCADE'))
    question_id: Mapped[int] = mapped_column(sa.BigInteger, sa.ForeignKey('qbank_v2_question.id', ondelete='CASCADE'))
    context_key: Mapped[str] = mapped_column(sa.String(80), comment='item:<投递题ID> 或 review:<作答ID>')
    annotations: Mapped[list[dict]] = mapped_column(CompatibleJSONB, default_factory=list)
    save_version: Mapped[int] = mapped_column(default=1)
