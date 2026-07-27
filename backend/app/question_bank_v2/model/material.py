from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any

import sqlalchemy as sa

from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.common.model import Base, TimeZone, UniversalText, UserMixin, id_key

from .common import CompatibleJSONB, ContentStatus

if TYPE_CHECKING:
    from .asset import QbMaterialRevisionAsset
    from .question import QbQuestionRevision


class QbMaterial(Base, UserMixin):
    """Stable reusable material identity."""

    __tablename__ = 'qbank_v2_material'
    __table_args__ = (
        sa.UniqueConstraint('code', 'deleted', name='uq_qbv2_material_code_deleted'),
        sa.ForeignKeyConstraint(
            ['id', 'current_revision_id'],
            ['qbank_v2_material_revision.material_id', 'qbank_v2_material_revision.id'],
            name='fk_qbv2_material_current_revision',
            ondelete='RESTRICT',
            use_alter=True,
        ),
        sa.CheckConstraint("status IN ('active','disabled','archived')", name='ck_qbv2_material_status'),
        sa.Index('ix_qbv2_material_status_created', 'status', 'created_time'),
        {'comment': '共享材料稳定身份表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    code: Mapped[str] = mapped_column(sa.String(64), comment='稳定业务编码')
    current_revision_id: Mapped[int | None] = mapped_column(
        sa.BigInteger,
        default=None,
        comment='当前发布版本 ID',
    )
    status: Mapped[str] = mapped_column(sa.String(16), default='active', comment='身份状态')

    current_revision: Mapped[QbMaterialRevision | None] = relationship(
        init=False,
        foreign_keys=lambda: [QbMaterial.id, QbMaterial.current_revision_id],
        post_update=True,
        lazy='noload',
    )
    revisions: Mapped[list[QbMaterialRevision]] = relationship(
        init=False,
        back_populates='material',
        foreign_keys=lambda: [QbMaterialRevision.material_id],
        cascade='save-update, merge',
        lazy='noload',
    )


class QbMaterialRevision(Base, UserMixin):
    """Immutable material snapshot shared by one or more question revisions."""

    __tablename__ = 'qbank_v2_material_revision'
    __table_args__ = (
        sa.UniqueConstraint('material_id', 'revision_no', name='uq_qbv2_mrev_material_no'),
        sa.UniqueConstraint('material_id', 'id', name='uq_qbv2_mrev_material_id'),
        sa.CheckConstraint('revision_no > 0', name='ck_qbv2_mrev_revision_no'),
        sa.CheckConstraint(
            "content_format IN ('html','markdown','plain','json')",
            name='ck_qbv2_mrev_content_format',
        ),
        sa.CheckConstraint(
            "status IN ('draft','published','retired')",
            name='ck_qbv2_mrev_status',
        ),
        sa.Index('ix_qbv2_mrev_material_status', 'material_id', 'status', 'revision_no'),
        sa.Index('ix_qbv2_mrev_content_hash', 'content_hash'),
        {'comment': '共享材料不可变版本表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    material_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('qbank_v2_material.id', ondelete='RESTRICT'),
        comment='材料身份 ID',
    )
    revision_no: Mapped[int] = mapped_column(sa.Integer, comment='版本号，从 1 递增')
    title: Mapped[str] = mapped_column(sa.String(255), comment='材料标题')
    content: Mapped[str] = mapped_column(UniversalText, comment='材料正文')
    content_format: Mapped[str] = mapped_column(sa.String(16), default='html', comment='正文格式')
    structured_data: Mapped[dict[str, Any]] = mapped_column(
        CompatibleJSONB,
        default_factory=dict,
        comment='OCR 块、表格、锚点等结构化数据',
    )
    source_name: Mapped[str | None] = mapped_column(sa.String(255), default=None, comment='材料来源')
    source_url: Mapped[str | None] = mapped_column(sa.String(1024), default=None, comment='来源地址')
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

    material: Mapped[QbMaterial] = relationship(
        init=False,
        back_populates='revisions',
        foreign_keys=[material_id],
        lazy='noload',
    )
    assets: Mapped[list[QbMaterialRevisionAsset]] = relationship(
        init=False,
        back_populates='material_revision',
        cascade='save-update, merge',
        lazy='noload',
    )
    anchors: Mapped[list[QbMaterialAnchor]] = relationship(
        init=False,
        back_populates='material_revision',
        cascade='save-update, merge',
        lazy='noload',
    )


class QbQuestionMaterial(Base, UserMixin):
    """Ordered relation pinning a material revision to a question revision."""

    __tablename__ = 'qbank_v2_question_material'
    __table_args__ = (
        sa.UniqueConstraint(
            'question_revision_id',
            'material_id',
            'role',
            'deleted',
            name='uq_qbv2_question_material',
        ),
        sa.UniqueConstraint(
            'question_revision_id',
            'material_revision_id',
            'id',
            name='uq_qbv2_qmaterial_context_id',
        ),
        sa.ForeignKeyConstraint(
            ['material_id', 'material_revision_id'],
            ['qbank_v2_material_revision.material_id', 'qbank_v2_material_revision.id'],
            name='fk_qbv2_qmaterial_revision',
            ondelete='RESTRICT',
        ),
        sa.CheckConstraint("role IN ('passage','prompt','reference','attachment')", name='ck_qbv2_qmaterial_role'),
        sa.CheckConstraint('sort_order >= 0', name='ck_qbv2_qmaterial_sort'),
        sa.Index('ix_qbv2_qmaterial_order', 'question_revision_id', 'sort_order'),
        sa.Index('ix_qbv2_qmaterial_reverse', 'material_id', 'material_revision_id'),
        {'comment': '题目版本与材料版本关联表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    question_revision_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('qbank_v2_question_revision.id', ondelete='RESTRICT'),
        comment='题目版本 ID',
    )
    material_id: Mapped[int] = mapped_column(sa.BigInteger, comment='材料身份 ID')
    material_revision_id: Mapped[int] = mapped_column(sa.BigInteger, comment='固定材料版本 ID')
    role: Mapped[str] = mapped_column(sa.String(16), default='passage', comment='材料在题目中的用途')
    sort_order: Mapped[int] = mapped_column(sa.Integer, default=0, comment='材料展示顺序')
    display_config: Mapped[dict[str, Any]] = mapped_column(
        CompatibleJSONB,
        default_factory=dict,
        comment='材料在此题目中的折叠、节选等展示配置',
    )

    question_revision: Mapped[QbQuestionRevision] = relationship(
        init=False,
        back_populates='materials',
        lazy='noload',
    )
    material_revision: Mapped[QbMaterialRevision] = relationship(
        init=False,
        foreign_keys=[material_id, material_revision_id],
        lazy='noload',
    )
    interactions: Mapped[list[QbQuestionInteraction]] = relationship(
        init=False,
        back_populates='question_material',
        foreign_keys=lambda: [
            QbQuestionInteraction.question_revision_id,
            QbQuestionInteraction.material_revision_id,
            QbQuestionInteraction.question_material_id,
        ],
        cascade='save-update, merge',
        overlaps='question_revision,interactions',
        lazy='noload',
    )


class QbMaterialAnchor(Base, UserMixin):
    """Addressable text, image, or table region in one material revision."""

    __tablename__ = 'qbank_v2_material_anchor'
    __table_args__ = (
        sa.UniqueConstraint('material_revision_id', 'anchor_key', 'deleted', name='uq_qbv2_anchor_key'),
        sa.UniqueConstraint('id', 'material_revision_id', name='uq_qbv2_anchor_id_revision'),
        sa.ForeignKeyConstraint(
            ['material_id', 'material_revision_id'],
            ['qbank_v2_material_revision.material_id', 'qbank_v2_material_revision.id'],
            name='fk_qbv2_anchor_material_revision',
            ondelete='RESTRICT',
        ),
        sa.CheckConstraint(
            "anchor_type IN ('text_range','text_block','image_region','image_point','table_cell')",
            name='ck_qbv2_anchor_type',
        ),
        sa.CheckConstraint(
            "source IN ('manual','ocr','ai','import')",
            name='ck_qbv2_anchor_source',
        ),
        sa.CheckConstraint(
            "status IN ('draft','active','retired')",
            name='ck_qbv2_anchor_status',
        ),
        sa.CheckConstraint(
            '(start_offset IS NULL AND end_offset IS NULL) OR (start_offset >= 0 AND end_offset > start_offset)',
            name='ck_qbv2_anchor_offsets',
        ),
        sa.CheckConstraint(
            'confidence IS NULL OR confidence BETWEEN 0 AND 1',
            name='ck_qbv2_anchor_confidence',
        ),
        sa.Index('ix_qbv2_anchor_revision_type', 'material_revision_id', 'anchor_type', 'status'),
        sa.Index('ix_qbv2_anchor_asset', 'asset_id'),
        sa.Index('ix_qbv2_anchor_content_hash', 'content_hash'),
        {'comment': '材料版本结构化锚点表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    material_id: Mapped[int] = mapped_column(sa.BigInteger, comment='材料身份 ID')
    material_revision_id: Mapped[int] = mapped_column(sa.BigInteger, comment='材料版本 ID')
    anchor_key: Mapped[str] = mapped_column(sa.String(128), comment='版本内稳定锚点键')
    anchor_type: Mapped[str] = mapped_column(sa.String(24), comment='锚点类型')
    text: Mapped[str | None] = mapped_column(UniversalText, default=None, comment='锚点文本快照')
    semantic_role: Mapped[str | None] = mapped_column(sa.String(64), default=None, comment='锚点语义角色')
    block_id: Mapped[str | None] = mapped_column(sa.String(128), default=None, comment='材料结构块 ID')
    start_offset: Mapped[int | None] = mapped_column(sa.Integer, default=None, comment='文本起始偏移')
    end_offset: Mapped[int | None] = mapped_column(sa.Integer, default=None, comment='文本结束偏移')
    asset_id: Mapped[int | None] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('qbank_v2_asset.id', ondelete='RESTRICT'),
        default=None,
        comment='图片或页面资产 ID',
    )
    bbox: Mapped[dict[str, Any] | None] = mapped_column(CompatibleJSONB, default=None, comment='归一化矩形区域')
    polygon: Mapped[list[dict[str, Any]] | None] = mapped_column(
        CompatibleJSONB,
        default=None,
        comment='归一化多边形区域',
    )
    table_cell: Mapped[dict[str, Any] | None] = mapped_column(
        CompatibleJSONB,
        default=None,
        comment='表格行列定位',
    )
    source: Mapped[str] = mapped_column(sa.String(16), default='manual', comment='锚点产生方式')
    confidence: Mapped[Decimal | None] = mapped_column(sa.Numeric(5, 4), default=None, comment='OCR 或 AI 置信度')
    content_hash: Mapped[str | None] = mapped_column(sa.String(64), default=None, comment='创建锚点时的材料内容哈希')
    status: Mapped[str] = mapped_column(sa.String(16), default='draft', comment='draft/active/retired')
    extra_data: Mapped[dict[str, Any]] = mapped_column(
        CompatibleJSONB,
        default_factory=dict,
        comment='锚点类型扩展数据',
    )

    material_revision: Mapped[QbMaterialRevision] = relationship(
        init=False,
        back_populates='anchors',
        foreign_keys=[material_id, material_revision_id],
        lazy='noload',
    )


class QbQuestionInteraction(Base, UserMixin):
    """Interaction definition owned by one immutable question revision."""

    __tablename__ = 'qbank_v2_question_interaction'
    __table_args__ = (
        sa.UniqueConstraint(
            'question_revision_id',
            'interaction_key',
            'deleted',
            name='uq_qbv2_interaction_key',
        ),
        sa.UniqueConstraint('id', 'material_revision_id', name='uq_qbv2_interaction_id_mrev'),
        sa.ForeignKeyConstraint(
            ['question_revision_id', 'material_revision_id', 'question_material_id'],
            [
                'qbank_v2_question_material.question_revision_id',
                'qbank_v2_question_material.material_revision_id',
                'qbank_v2_question_material.id',
            ],
            name='fk_qbv2_interaction_material_context',
            ondelete='RESTRICT',
        ),
        sa.CheckConstraint(
            '(question_material_id IS NULL AND material_revision_id IS NULL) '
            'OR (question_material_id IS NOT NULL AND material_revision_id IS NOT NULL)',
            name='ck_qbv2_interaction_material_pair',
        ),
        sa.CheckConstraint(
            "selection_mode IN ('single','multiple','multi_role')",
            name='ck_qbv2_interaction_selection',
        ),
        sa.CheckConstraint('min_selections >= 0', name='ck_qbv2_interaction_min'),
        sa.CheckConstraint(
            'max_selections IS NULL OR max_selections >= min_selections',
            name='ck_qbv2_interaction_max',
        ),
        sa.CheckConstraint(
            "status IN ('draft','active','retired')",
            name='ck_qbv2_interaction_status',
        ),
        sa.Index('ix_qbv2_interaction_revision', 'question_revision_id', 'status'),
        sa.Index('ix_qbv2_interaction_material', 'question_material_id'),
        {'comment': '题目版本交互定义表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    question_revision_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('qbank_v2_question_revision.id', ondelete='RESTRICT'),
        comment='题目版本 ID',
    )
    interaction_key: Mapped[str] = mapped_column(sa.String(128), comment='版本内稳定交互键')
    interaction_type: Mapped[str] = mapped_column(sa.String(32), comment='可扩展交互类型')
    instruction: Mapped[str] = mapped_column(UniversalText, comment='交互指令')
    question_material_id: Mapped[int | None] = mapped_column(sa.BigInteger, default=None, comment='题目材料关联 ID')
    material_revision_id: Mapped[int | None] = mapped_column(
        sa.BigInteger,
        default=None,
        comment='候选锚点所属材料版本',
    )
    title: Mapped[str | None] = mapped_column(sa.String(160), default=None, comment='交互标题')
    selection_mode: Mapped[str] = mapped_column(sa.String(16), default='single', comment='选择模式')
    min_selections: Mapped[int] = mapped_column(sa.SmallInteger, default=0, comment='最少选择数')
    max_selections: Mapped[int | None] = mapped_column(sa.SmallInteger, default=None, comment='最多选择数')
    config: Mapped[dict[str, Any]] = mapped_column(
        CompatibleJSONB,
        default_factory=dict,
        comment='角色、显示和交互扩展配置',
    )
    status: Mapped[str] = mapped_column(sa.String(16), default='draft', comment='draft/active/retired')

    question_revision: Mapped[QbQuestionRevision] = relationship(
        init=False,
        back_populates='interactions',
        foreign_keys=[question_revision_id],
        overlaps='interactions,question_material',
        lazy='noload',
    )
    question_material: Mapped[QbQuestionMaterial | None] = relationship(
        init=False,
        back_populates='interactions',
        foreign_keys=[question_revision_id, material_revision_id, question_material_id],
        overlaps='interactions,question_revision',
        lazy='noload',
    )
    candidates: Mapped[list[QbQuestionInteractionCandidate]] = relationship(
        init=False,
        back_populates='interaction',
        cascade='all, delete-orphan',
        lazy='noload',
    )


class QbQuestionInteractionCandidate(Base, UserMixin):
    """Ordered material-anchor candidate for a question interaction."""

    __tablename__ = 'qbank_v2_question_interaction_candidate'
    __table_args__ = (
        sa.UniqueConstraint(
            'interaction_id',
            'anchor_id',
            'candidate_role',
            'deleted',
            name='uq_qbv2_interaction_candidate',
        ),
        sa.ForeignKeyConstraint(
            ['interaction_id', 'material_revision_id'],
            ['qbank_v2_question_interaction.id', 'qbank_v2_question_interaction.material_revision_id'],
            name='fk_qbv2_candidate_interaction_mrev',
            ondelete='CASCADE',
        ),
        sa.ForeignKeyConstraint(
            ['anchor_id', 'material_revision_id'],
            ['qbank_v2_material_anchor.id', 'qbank_v2_material_anchor.material_revision_id'],
            name='fk_qbv2_candidate_anchor_mrev',
            ondelete='RESTRICT',
        ),
        sa.CheckConstraint('sort_order >= 0', name='ck_qbv2_candidate_sort'),
        sa.Index('ix_qbv2_candidate_order', 'interaction_id', 'candidate_role', 'sort_order'),
        sa.Index('ix_qbv2_candidate_anchor', 'anchor_id'),
        {'comment': '题目交互候选锚点表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    interaction_id: Mapped[int] = mapped_column(sa.BigInteger, comment='交互定义 ID')
    material_revision_id: Mapped[int] = mapped_column(sa.BigInteger, comment='共同材料版本 ID')
    anchor_id: Mapped[int] = mapped_column(sa.BigInteger, comment='材料锚点 ID')
    candidate_role: Mapped[str] = mapped_column(sa.String(64), default='', comment='候选语义分组或角色')
    label: Mapped[str | None] = mapped_column(sa.String(160), default=None, comment='候选展示标签')
    sort_order: Mapped[int] = mapped_column(sa.Integer, default=0, comment='候选顺序')

    interaction: Mapped[QbQuestionInteraction] = relationship(
        init=False,
        back_populates='candidates',
        foreign_keys=[interaction_id, material_revision_id],
        lazy='noload',
    )
    anchor: Mapped[QbMaterialAnchor] = relationship(
        init=False,
        foreign_keys=[anchor_id, material_revision_id],
        overlaps='candidates,interaction',
        lazy='noload',
    )
