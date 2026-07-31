from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

import sqlalchemy as sa

from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.common.model import Base, UniversalText, UserMixin, id_key

if TYPE_CHECKING:
    from .question import QbQuestion


class QbKnowledgeSystem(Base, UserMixin):
    """Versioned namespace for one knowledge taxonomy."""

    __tablename__ = 'qbank_v2_knowledge_system'
    __table_args__ = (
        sa.UniqueConstraint('code', 'version', 'deleted', name='uq_qbv2_ksystem_code_version'),
        sa.CheckConstraint("status IN ('draft','active','archived')", name='ck_qbv2_ksystem_status'),
        sa.Index('ix_qbv2_ksystem_status', 'status'),
        {'comment': '知识体系表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    code: Mapped[str] = mapped_column(sa.String(64), comment='知识体系编码')
    name: Mapped[str] = mapped_column(sa.String(128), comment='知识体系名称')
    version: Mapped[str] = mapped_column(sa.String(32), comment='体系版本')
    description: Mapped[str | None] = mapped_column(UniversalText, default=None, comment='体系说明')
    status: Mapped[str] = mapped_column(sa.String(16), default='draft', comment='draft/active/archived')

    points: Mapped[list[QbKnowledgePoint]] = relationship(
        init=False,
        back_populates='system',
        cascade='save-update, merge',
        overlaps='children,parent',
        lazy='noload',
    )


class QbKnowledgePoint(Base, UserMixin):
    """Normalized knowledge point in a single taxonomy."""

    __tablename__ = 'qbank_v2_knowledge_point'
    __table_args__ = (
        sa.UniqueConstraint('system_id', 'id', name='uq_qbv2_kpoint_system_id'),
        sa.UniqueConstraint('system_id', 'code', 'deleted', name='uq_qbv2_kpoint_code'),
        sa.ForeignKeyConstraint(
            ['system_id', 'parent_id'],
            ['qbank_v2_knowledge_point.system_id', 'qbank_v2_knowledge_point.id'],
            name='fk_qbv2_kpoint_parent_same_system',
            ondelete='RESTRICT',
        ),
        sa.CheckConstraint('parent_id IS NULL OR parent_id <> id', name='ck_qbv2_kpoint_not_self'),
        sa.CheckConstraint('depth >= 0', name='ck_qbv2_kpoint_depth'),
        sa.Index('ix_qbv2_kpoint_parent_order', 'system_id', 'parent_id', 'sort_order'),
        sa.Index('ix_qbv2_kpoint_path', 'system_id', 'path'),
        {'comment': '知识点表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    system_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('qbank_v2_knowledge_system.id', ondelete='RESTRICT'),
        comment='知识体系 ID',
    )
    code: Mapped[str] = mapped_column(sa.String(96), comment='体系内唯一编码')
    name: Mapped[str] = mapped_column(sa.String(160), comment='知识点名称')
    parent_id: Mapped[int | None] = mapped_column(sa.BigInteger, default=None, comment='同体系内父知识点 ID')
    path: Mapped[str | None] = mapped_column(sa.String(1024), default=None, comment='物化路径缓存')
    depth: Mapped[int] = mapped_column(sa.SmallInteger, default=0, comment='树深度')
    sort_order: Mapped[int] = mapped_column(sa.Integer, default=0, comment='同层排序')
    description: Mapped[str | None] = mapped_column(UniversalText, default=None, comment='知识点说明')

    system: Mapped[QbKnowledgeSystem] = relationship(
        init=False,
        back_populates='points',
        foreign_keys=[system_id],
        overlaps='children,parent',
        lazy='noload',
    )
    parent: Mapped[QbKnowledgePoint | None] = relationship(
        init=False,
        remote_side=lambda: [QbKnowledgePoint.system_id, QbKnowledgePoint.id],
        foreign_keys=lambda: [QbKnowledgePoint.system_id, QbKnowledgePoint.parent_id],
        back_populates='children',
        overlaps='points,system',
        lazy='noload',
    )
    children: Mapped[list[QbKnowledgePoint]] = relationship(
        init=False,
        foreign_keys=lambda: [QbKnowledgePoint.system_id, QbKnowledgePoint.parent_id],
        back_populates='parent',
        cascade='save-update, merge',
        overlaps='points,system',
        lazy='noload',
    )
    question_links: Mapped[list[QbQuestionKnowledgePoint]] = relationship(
        init=False,
        back_populates='knowledge_point',
        cascade='save-update, merge',
        lazy='noload',
    )


class QbQuestionKnowledgePoint(Base, UserMixin):
    """Weighted, auditable relation from a question to a knowledge point."""

    __tablename__ = 'qbank_v2_question_knowledge_point'
    __table_args__ = (
        sa.UniqueConstraint(
            'question_id',
            'knowledge_point_id',
            'deleted',
            name='uq_qbv2_question_kpoint',
        ),
        sa.CheckConstraint("role IN ('primary','secondary','prerequisite')", name='ck_qbv2_qkp_role'),
        sa.CheckConstraint("source IN ('manual','import','ai')", name='ck_qbv2_qkp_source'),
        sa.CheckConstraint('weight > 0 AND weight <= 1', name='ck_qbv2_qkp_weight'),
        sa.CheckConstraint('confidence IS NULL OR confidence BETWEEN 0 AND 1', name='ck_qbv2_qkp_confidence'),
        sa.Index('ix_qbv2_qkp_point_question', 'knowledge_point_id', 'question_id'),
        sa.Index('ix_qbv2_qkp_question_role', 'question_id', 'role'),
        {'comment': '题目知识点关联表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    question_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('qbank_v2_question.id', ondelete='RESTRICT'),
        comment='题目 ID',
    )
    knowledge_point_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('qbank_v2_knowledge_point.id', ondelete='RESTRICT'),
        comment='知识点 ID',
    )
    role: Mapped[str] = mapped_column(sa.String(16), default='primary', comment='知识点角色')
    weight: Mapped[Decimal] = mapped_column(sa.Numeric(5, 4), default=Decimal('1.0000'), comment='贡献权重')
    source: Mapped[str] = mapped_column(sa.String(16), default='manual', comment='标注来源')
    confidence: Mapped[Decimal | None] = mapped_column(sa.Numeric(5, 4), default=None, comment='自动标注置信度')

    question: Mapped[QbQuestion] = relationship(
        init=False,
        back_populates='knowledge_points',
        lazy='noload',
    )
    knowledge_point: Mapped[QbKnowledgePoint] = relationship(
        init=False,
        back_populates='question_links',
        lazy='noload',
    )
