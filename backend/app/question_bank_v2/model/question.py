from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING, Any

import sqlalchemy as sa

from pgvector.sqlalchemy import Vector
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.common.model import Base, UniversalText, UserMixin, id_key

from .common import CompatibleJSONB, QuestionOrigin, QuestionType, Visibility

if TYPE_CHECKING:
    from .asset import QbQuestionAsset
    from .knowledge import QbQuestionKnowledgePoint
    from .material import QbQuestionInteraction, QbQuestionMaterial


class QbQuestion(Base, UserMixin):
    __tablename__ = 'qbank_v2_question'
    __table_args__ = (
        sa.UniqueConstraint('code', 'deleted', name='uq_qbv2_question_code_deleted'),
        sa.CheckConstraint(
            "visibility IN ('private','internal','public')",
            name='ck_qbv2_question_visibility',
        ),
        sa.CheckConstraint(
            "origin_type IN ('curated','imported','user_created','generated')",
            name='ck_qbv2_question_origin',
        ),
        sa.CheckConstraint(
            "status IN ('active','disabled','archived')",
            name='ck_qbv2_question_status',
        ),
        sa.CheckConstraint(
            "visibility <> 'private' OR owner_id IS NOT NULL",
            name='ck_qbv2_question_private_owner',
        ),
        sa.CheckConstraint('length(trim(stem)) > 0', name='ck_qbv2_question_stem_not_blank'),
        sa.CheckConstraint('default_score >= 0', name='ck_qbv2_question_default_score'),
        sa.CheckConstraint('difficulty IS NULL OR difficulty BETWEEN 1 AND 5', name='ck_qbv2_question_difficulty'),
        sa.CheckConstraint(
            "question_type IN ('single_choice','multiple_choice','true_false','fill_blank',"
            "'short_answer','composite','interactive')",
            name='ck_qbv2_question_type',
        ),
        sa.CheckConstraint(
            "content_format IN ('html','markdown','plain','json')",
            name='ck_qbv2_question_content_format',
        ),
        sa.Index('ix_qbv2_question_status_created', 'status', 'created_time'),
        sa.Index('ix_qbv2_question_owner_visibility', 'owner_id', 'visibility', 'status'),
        sa.Index('ix_qbv2_question_origin_status', 'origin_type', 'status'),
        sa.Index('ix_qbv2_question_type_status', 'question_type', 'status'),
        sa.Index('ix_qbv2_question_content_hash', 'content_hash'),
        {'comment': '题目表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    code: Mapped[str] = mapped_column(sa.String(64), comment='稳定业务编码')
    stem: Mapped[str] = mapped_column(UniversalText, comment='题干富文本')
    owner_id: Mapped[int | None] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('sys_user.id', ondelete='RESTRICT'),
        default=None,
        comment='私有或用户创建题目的所有者',
    )
    visibility: Mapped[str] = mapped_column(
        sa.String(16),
        default=Visibility.public.value,
        comment='private/internal/public',
    )
    origin_type: Mapped[str] = mapped_column(
        sa.String(16),
        default=QuestionOrigin.curated.value,
        comment='curated/imported/user_created/generated',
    )
    status: Mapped[str] = mapped_column(
        sa.String(16),
        default='active',
        comment='active/disabled/archived',
    )
    content_format: Mapped[str] = mapped_column(sa.String(16), default='html', comment='题干内容格式')
    question_type: Mapped[str] = mapped_column(
        sa.String(24),
        default=QuestionType.single_choice.value,
        comment='题型',
    )
    option_data: Mapped[list[dict[str, Any]]] = mapped_column(
        CompatibleJSONB,
        default_factory=list,
        comment='有序选项；非选择题为空数组',
    )
    default_score: Mapped[Decimal] = mapped_column(
        sa.Numeric(8, 2),
        default=Decimal('1.00'),
        comment='默认分值',
    )
    difficulty: Mapped[Decimal | None] = mapped_column(
        sa.Numeric(3, 2),
        default=None,
        comment='基于有效作答正确率和相对耗时动态计算，范围 1-5',
    )
    content_hash: Mapped[str | None] = mapped_column(sa.String(64), default=None, comment='规范化内容 SHA-256')

    answer: Mapped[QbQuestionAnswer | None] = relationship(
        init=False,
        back_populates='question',
        uselist=False,
        lazy='noload',
    )
    explanations: Mapped[list[QbQuestionExplanation]] = relationship(
        init=False,
        back_populates='question',
        cascade='save-update, merge',
        lazy='noload',
    )
    knowledge_points: Mapped[list[QbQuestionKnowledgePoint]] = relationship(
        init=False,
        back_populates='question',
        cascade='save-update, merge',
        lazy='noload',
    )
    materials: Mapped[list[QbQuestionMaterial]] = relationship(
        init=False,
        back_populates='question',
        cascade='save-update, merge',
        lazy='noload',
    )
    assets: Mapped[list[QbQuestionAsset]] = relationship(
        init=False,
        back_populates='question',
        cascade='save-update, merge',
        lazy='noload',
    )
    interactions: Mapped[list[QbQuestionInteraction]] = relationship(
        init=False,
        back_populates='question',
        cascade='save-update, merge',
        lazy='noload',
    )
    embeddings: Mapped[list[QbQuestionEmbedding]] = relationship(
        init=False,
        back_populates='question',
        cascade='save-update, merge',
        lazy='noload',
    )


class QbQuestionAnswer(Base, UserMixin):
    __tablename__ = 'qbank_v2_question_answer'
    __table_args__ = (
        sa.UniqueConstraint('question_id', name='uq_qbv2_answer_question'),
        sa.CheckConstraint(
            "grading_method IN ('exact','set','ordered','range','keyword','rubric','manual','custom')",
            name='ck_qbv2_answer_grading_method',
        ),
        {'comment': '题目权威答案表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    question_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('qbank_v2_question.id', ondelete='RESTRICT'),
        comment='题目 ID',
    )
    answer_data: Mapped[dict[str, Any]] = mapped_column(CompatibleJSONB, comment='结构化标准答案')
    grading_method: Mapped[str] = mapped_column(sa.String(16), default='exact', comment='判分方式')
    grading_config: Mapped[dict[str, Any]] = mapped_column(
        CompatibleJSONB,
        default_factory=dict,
        comment='容错、关键词、量规等判分配置',
    )

    question: Mapped[QbQuestion] = relationship(
        init=False,
        back_populates='answer',
        lazy='noload',
    )


class QbQuestionExplanation(Base, UserMixin):
    __tablename__ = 'qbank_v2_question_explanation'
    __table_args__ = (
        sa.UniqueConstraint(
            'question_id',
            'explanation_type',
            'deleted',
            name='uq_qbv2_explanation_variant',
        ),
        sa.CheckConstraint(
            "status IN ('draft','published','retired')",
            name='ck_qbv2_explanation_status',
        ),
        sa.Index('ix_qbv2_explanation_default', 'question_id', 'is_default', 'status'),
        {'comment': '题目解析表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    question_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('qbank_v2_question.id', ondelete='RESTRICT'),
        comment='题目 ID',
    )
    content: Mapped[str] = mapped_column(UniversalText, comment='解析富文本')
    explanation_type: Mapped[str] = mapped_column(
        sa.String(24),
        default='official',
        comment='default/official/expert/ai/user',
    )
    is_default: Mapped[bool] = mapped_column(default=False, comment='是否默认展示')
    status: Mapped[str] = mapped_column(sa.String(16), default='draft', comment='draft/published/retired')

    question: Mapped[QbQuestion] = relationship(
        init=False,
        back_populates='explanations',
        lazy='noload',
    )


class QbQuestionEmbedding(Base):
    __tablename__ = 'qbank_v2_question_embedding'
    __table_args__ = (
        sa.UniqueConstraint('question_id', 'embedding_space', 'deleted', name='uq_qbv2_embedding_space'),
        sa.CheckConstraint('vector_dims > 0', name='ck_qbv2_embedding_dims'),
        sa.Index('ix_qbv2_embedding_question', 'question_id'),
        sa.Index('ix_qbv2_embedding_model', 'provider', 'model_name', 'vector_dims'),
        {'comment': '题目语义向量表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    question_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('qbank_v2_question.id', ondelete='CASCADE'),
        comment='题目 ID',
    )
    provider: Mapped[str] = mapped_column(sa.String(64), comment='向量服务商')
    model_name: Mapped[str] = mapped_column(sa.String(128), comment='向量模型名')
    embedding_space: Mapped[str] = mapped_column(sa.String(160), comment='含模型版本和预处理策略的稳定向量空间标识')
    content_hash: Mapped[str] = mapped_column(sa.String(64), comment='生成向量时的内容哈希')
    embedding: Mapped[list[float]] = mapped_column(Vector(), deferred=True, comment='可变维度内容向量')
    vector_dims: Mapped[int] = mapped_column(sa.Integer, comment='向量维数')

    question: Mapped[QbQuestion] = relationship(
        init=False,
        back_populates='embeddings',
        lazy='noload',
    )
