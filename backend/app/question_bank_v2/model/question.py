from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any

import sqlalchemy as sa

from pgvector.sqlalchemy import Vector
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.common.model import Base, TimeZone, UniversalText, UserMixin, id_key

from .common import CompatibleJSONB, ContentStatus, QuestionOrigin, QuestionType, Visibility

if TYPE_CHECKING:
    from .asset import QbQuestionRevisionAsset
    from .knowledge import QbQuestionKnowledgePoint
    from .material import QbQuestionInteraction, QbQuestionMaterial


class QbQuestion(Base, UserMixin):
    """Stable question identity; editable content lives in immutable revisions."""

    __tablename__ = 'qbank_v2_question'
    __table_args__ = (
        sa.UniqueConstraint('code', 'deleted', name='uq_qbv2_question_code_deleted'),
        sa.ForeignKeyConstraint(
            ['id', 'current_revision_id'],
            ['qbank_v2_question_revision.question_id', 'qbank_v2_question_revision.id'],
            name='fk_qbv2_question_current_revision',
            ondelete='RESTRICT',
            use_alter=True,
        ),
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
        sa.Index('ix_qbv2_question_status_created', 'status', 'created_time'),
        sa.Index('ix_qbv2_question_owner_visibility', 'owner_id', 'visibility', 'status'),
        sa.Index('ix_qbv2_question_origin_status', 'origin_type', 'status'),
        {'comment': '题目稳定身份表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    code: Mapped[str] = mapped_column(sa.String(64), comment='稳定业务编码')
    owner_id: Mapped[int | None] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('sys_user.id', ondelete='RESTRICT'),
        default=None,
        comment='私有或用户创建题目的所有者',
    )
    current_revision_id: Mapped[int | None] = mapped_column(
        sa.BigInteger,
        default=None,
        comment='当前发布版本 ID',
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
        comment='身份状态: active/disabled/archived',
    )

    current_revision: Mapped[QbQuestionRevision | None] = relationship(
        init=False,
        foreign_keys=lambda: [QbQuestion.id, QbQuestion.current_revision_id],
        post_update=True,
        lazy='noload',
    )
    revisions: Mapped[list[QbQuestionRevision]] = relationship(
        init=False,
        back_populates='question',
        foreign_keys=lambda: [QbQuestionRevision.question_id],
        cascade='save-update, merge',
        lazy='noload',
    )


class QbQuestionRevision(Base, UserMixin):
    """Immutable snapshot of question content once published."""

    __tablename__ = 'qbank_v2_question_revision'
    __table_args__ = (
        sa.UniqueConstraint('question_id', 'revision_no', name='uq_qbv2_qrev_question_no'),
        sa.UniqueConstraint('question_id', 'id', name='uq_qbv2_qrev_question_id'),
        sa.CheckConstraint('revision_no > 0', name='ck_qbv2_qrev_revision_no'),
        sa.CheckConstraint('length(trim(stem)) > 0', name='ck_qbv2_qrev_stem_not_blank'),
        sa.CheckConstraint('default_score >= 0', name='ck_qbv2_qrev_default_score'),
        sa.CheckConstraint('difficulty IS NULL OR difficulty BETWEEN 1 AND 5', name='ck_qbv2_qrev_difficulty'),
        sa.CheckConstraint(
            "question_type IN ('single_choice','multiple_choice','true_false','fill_blank',"
            "'short_answer','composite','interactive')",
            name='ck_qbv2_qrev_type',
        ),
        sa.CheckConstraint(
            "content_format IN ('html','markdown','plain','json')",
            name='ck_qbv2_qrev_content_format',
        ),
        sa.CheckConstraint(
            "status IN ('draft','published','retired')",
            name='ck_qbv2_qrev_status',
        ),
        sa.Index('ix_qbv2_qrev_question_status', 'question_id', 'status', 'revision_no'),
        sa.Index('ix_qbv2_qrev_type_status', 'question_type', 'status'),
        sa.Index('ix_qbv2_qrev_content_hash', 'content_hash'),
        {'comment': '题目不可变版本表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    question_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('qbank_v2_question.id', ondelete='RESTRICT'),
        comment='题目身份 ID',
    )
    revision_no: Mapped[int] = mapped_column(sa.Integer, comment='版本号，从 1 递增')
    stem: Mapped[str] = mapped_column(UniversalText, comment='题干富文本')
    content_format: Mapped[str] = mapped_column(sa.String(16), default='html', comment='题干内容格式')
    question_type: Mapped[str] = mapped_column(
        sa.String(24),
        default=QuestionType.single_choice.value,
        comment='题型',
    )
    option_data: Mapped[list[dict[str, Any]]] = mapped_column(
        CompatibleJSONB,
        default_factory=list,
        comment='有序选项快照；非选择题为空数组',
    )
    default_score: Mapped[Decimal] = mapped_column(
        sa.Numeric(8, 2),
        default=Decimal('1.00'),
        comment='默认分值',
    )
    difficulty: Mapped[Decimal | None] = mapped_column(
        sa.Numeric(3, 2),
        default=None,
        comment='人工标定难度，范围 1-5',
    )
    language: Mapped[str] = mapped_column(sa.String(16), default='zh-CN', comment='内容语言')
    content_hash: Mapped[str | None] = mapped_column(sa.String(64), default=None, comment='规范化内容 SHA-256')
    status: Mapped[str] = mapped_column(
        sa.String(16),
        default=ContentStatus.draft.value,
        comment='draft/published/retired',
    )
    published_by: Mapped[int | None] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('sys_user.id', ondelete='SET NULL'),
        default=None,
        comment='发布人 ID',
    )
    published_time: Mapped[datetime | None] = mapped_column(TimeZone, default=None, comment='发布时间')

    question: Mapped[QbQuestion] = relationship(
        init=False,
        back_populates='revisions',
        foreign_keys=[question_id],
        lazy='noload',
    )
    answer: Mapped[QbQuestionAnswer | None] = relationship(
        init=False,
        back_populates='question_revision',
        uselist=False,
        lazy='noload',
    )
    explanations: Mapped[list[QbQuestionExplanation]] = relationship(
        init=False,
        back_populates='question_revision',
        cascade='save-update, merge',
        lazy='noload',
    )
    knowledge_points: Mapped[list[QbQuestionKnowledgePoint]] = relationship(
        init=False,
        back_populates='question_revision',
        cascade='save-update, merge',
        lazy='noload',
    )
    materials: Mapped[list[QbQuestionMaterial]] = relationship(
        init=False,
        back_populates='question_revision',
        cascade='save-update, merge',
        lazy='noload',
    )
    assets: Mapped[list[QbQuestionRevisionAsset]] = relationship(
        init=False,
        back_populates='question_revision',
        cascade='save-update, merge',
        lazy='noload',
    )
    interactions: Mapped[list[QbQuestionInteraction]] = relationship(
        init=False,
        back_populates='question_revision',
        cascade='save-update, merge',
        lazy='noload',
    )


class QbQuestionAnswer(Base, UserMixin):
    """Authoritative answer and grading policy, isolated from display explanations."""

    __tablename__ = 'qbank_v2_question_answer'
    __table_args__ = (
        sa.UniqueConstraint('question_revision_id', name='uq_qbv2_answer_revision'),
        sa.CheckConstraint(
            "grading_method IN ('exact','set','ordered','range','keyword','rubric','manual','custom')",
            name='ck_qbv2_answer_grading_method',
        ),
        {'comment': '题目版本权威答案表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    question_revision_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('qbank_v2_question_revision.id', ondelete='RESTRICT'),
        comment='题目版本 ID',
    )
    answer_data: Mapped[dict[str, Any]] = mapped_column(CompatibleJSONB, comment='结构化标准答案')
    grading_method: Mapped[str] = mapped_column(sa.String(16), default='exact', comment='判分方式')
    grading_config: Mapped[dict[str, Any]] = mapped_column(
        CompatibleJSONB,
        default_factory=dict,
        comment='容错、关键词、量规等判分配置',
    )

    question_revision: Mapped[QbQuestionRevision] = relationship(
        init=False,
        back_populates='answer',
        lazy='noload',
    )


class QbQuestionExplanation(Base, UserMixin):
    """Versioned explanation variants independent from the authoritative answer."""

    __tablename__ = 'qbank_v2_question_explanation'
    __table_args__ = (
        sa.UniqueConstraint(
            'question_revision_id',
            'explanation_type',
            'language',
            'version_no',
            'deleted',
            name='uq_qbv2_explanation_variant',
        ),
        sa.CheckConstraint('version_no > 0', name='ck_qbv2_explanation_version'),
        sa.CheckConstraint(
            "status IN ('draft','published','retired')",
            name='ck_qbv2_explanation_status',
        ),
        sa.Index(
            'ix_qbv2_explanation_default',
            'question_revision_id',
            'language',
            'is_default',
            'status',
        ),
        {'comment': '题目版本解析表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    question_revision_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('qbank_v2_question_revision.id', ondelete='RESTRICT'),
        comment='题目版本 ID',
    )
    content: Mapped[str] = mapped_column(UniversalText, comment='解析富文本')
    explanation_type: Mapped[str] = mapped_column(
        sa.String(24),
        default='official',
        comment='official/expert/ai/user',
    )
    language: Mapped[str] = mapped_column(sa.String(16), default='zh-CN', comment='内容语言')
    version_no: Mapped[int] = mapped_column(sa.Integer, default=1, comment='同类型解析版本号')
    is_default: Mapped[bool] = mapped_column(default=False, comment='是否默认展示')
    status: Mapped[str] = mapped_column(
        sa.String(16),
        default=ContentStatus.draft.value,
        comment='draft/published/retired',
    )

    question_revision: Mapped[QbQuestionRevision] = relationship(
        init=False,
        back_populates='explanations',
        lazy='noload',
    )


class QbQuestionExternalRef(Base, UserMixin):
    """Idempotent source mapping for imports and synchronization."""

    __tablename__ = 'qbank_v2_question_external_ref'
    __table_args__ = (
        sa.Index(
            'uq_qbv2_qref_system_source_key',
            'source_system',
            'external_key',
            unique=True,
            postgresql_where=sa.text('owner_id IS NULL AND deleted = 0'),
        ).ddl_if(dialect='postgresql'),
        sa.Index(
            'uq_qbv2_qref_user_source_key',
            'owner_id',
            'source_system',
            'external_key',
            unique=True,
            postgresql_where=sa.text('owner_id IS NOT NULL AND deleted = 0'),
        ).ddl_if(dialect='postgresql'),
        sa.Index('ix_qbv2_qref_question', 'question_id'),
        {'comment': '题目外部来源映射表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    question_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('qbank_v2_question.id', ondelete='RESTRICT'),
        comment='题目身份 ID',
    )
    source_system: Mapped[str] = mapped_column(sa.String(64), comment='来源系统')
    external_key: Mapped[str] = mapped_column(sa.String(255), comment='来源唯一键')
    owner_id: Mapped[int | None] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('sys_user.id', ondelete='CASCADE'),
        default=None,
        comment='用户私有来源所有者；系统来源为空',
    )
    source_url: Mapped[str | None] = mapped_column(sa.String(1024), default=None, comment='来源地址')
    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        'metadata',
        CompatibleJSONB,
        default_factory=dict,
        comment='来源扩展元数据',
    )


class QbQuestionEmbedding(Base):
    """Regenerable semantic vector for one immutable question revision."""

    __tablename__ = 'qbank_v2_question_embedding'
    __table_args__ = (
        sa.UniqueConstraint(
            'question_revision_id',
            'embedding_space',
            'deleted',
            name='uq_qbv2_embedding_space',
        ),
        sa.CheckConstraint('vector_dims > 0', name='ck_qbv2_embedding_dims'),
        sa.Index('ix_qbv2_embedding_revision', 'question_revision_id'),
        sa.Index('ix_qbv2_embedding_model', 'provider', 'model_name', 'vector_dims'),
        {'comment': '题目版本语义向量表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    question_revision_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('qbank_v2_question_revision.id', ondelete='CASCADE'),
        comment='题目版本 ID',
    )
    provider: Mapped[str] = mapped_column(sa.String(64), comment='向量服务商')
    model_name: Mapped[str] = mapped_column(sa.String(128), comment='向量模型名')
    embedding_space: Mapped[str] = mapped_column(
        sa.String(160),
        comment='含模型版本和预处理策略的稳定向量空间标识',
    )
    content_hash: Mapped[str] = mapped_column(sa.String(64), comment='生成向量时的内容哈希')
    embedding: Mapped[list[float]] = mapped_column(Vector(), deferred=True, comment='可变维度内容向量')
    vector_dims: Mapped[int] = mapped_column(sa.Integer, comment='向量维数')
