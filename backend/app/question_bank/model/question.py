#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any

import sqlalchemy as sa

from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.common.model import Base, UniversalText, UserMixin, id_key

# 为 PostgreSQL 提供原生的拥有极高索引与搜索能力的 JSONB 性能，并保留对本地普通库的兼容
CompatibleJSONB = sa.JSON().with_variant(JSONB, 'postgresql')

if TYPE_CHECKING:
    from .bank import QuestionBank
    from .chapter import QuestionChapter


# 题目-材料关联表（多对多）
question_material_relation = sa.Table(
    'study_question_material_relation',
    Base.metadata,
    sa.Column('question_id', sa.BigInteger, sa.ForeignKey('study_question.id', ondelete='CASCADE'), primary_key=True),
    sa.Column(
        'material_id', sa.BigInteger, sa.ForeignKey('study_question_material.id', ondelete='CASCADE'), primary_key=True
    ),
    sa.Column('sort_order', sa.Integer, default=0, comment='排序'),
    sa.Index('idx_qmr_material', 'material_id'),
    sa.Index('idx_qmr_question_sort', 'question_id', 'sort_order'),
    sa.Index('idx_qmr_material_sort', 'material_id', 'sort_order'),
    comment='题目-材料关联表',
)


class QuestionPlacement(Base, UserMixin):
    """题目挂载表"""

    __tablename__ = 'study_question_placement'
    __table_args__ = (
        sa.UniqueConstraint('bank_id', 'question_id', name='uq_study_question_placement_bank_question'),
        sa.Index('idx_placement_bank_chapter_active_sort', 'bank_id', 'chapter_id', 'is_active', 'sort_order'),
        sa.Index('idx_placement_question', 'question_id'),
        sa.Index('idx_placement_bank_active_review', 'bank_id', 'is_active', 'review_status'),
        sa.Index('idx_placement_scene_mask', 'scene_mask'),
        {'comment': '题目挂载表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    question_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('study_question.id', ondelete='CASCADE'),
        comment='题目 ID',
    )
    bank_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('study_question_bank.id', ondelete='CASCADE'),
        comment='题库 ID',
    )
    chapter_id: Mapped[int | None] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('study_question_chapter.id', ondelete='SET NULL'),
        default=None,
        comment='章节 ID',
    )
    sort_order: Mapped[int] = mapped_column(sa.Integer, default=0, comment='排序')
    is_active: Mapped[bool] = mapped_column(default=True, comment='是否启用')
    score: Mapped[Decimal | None] = mapped_column(sa.Numeric(6, 2), default=None, comment='挂载分值')
    review_status: Mapped[int] = mapped_column(
        sa.SmallInteger,
        default=10,
        comment='审核状态: 0=待审核, 10=已通过, 20=已拒绝',
    )
    scene_mask: Mapped[int | None] = mapped_column(
        sa.Integer,
        default=None,
        comment='可用场景位标记（为空=继承题库）: 1=练习, 2=考试, 4=模考, 8=错题重练',
    )
    bank: Mapped['QuestionBank'] = relationship(init=False, back_populates='placements', lazy='noload')
    chapter: Mapped['QuestionChapter | None'] = relationship(init=False, back_populates='placements', lazy='noload')
    question: Mapped['Question'] = relationship(init=False, back_populates='placements', lazy='noload')


from pgvector.sqlalchemy import Vector


class Question(Base, UserMixin):
    """题目表"""

    __tablename__ = 'study_question'
    __table_args__ = (
        sa.Index('idx_question_type_status', 'type', 'content_status'),
        sa.Index('idx_question_difficulty', 'difficulty'),
        sa.Index('idx_question_status_created', 'content_status', 'created_time'),
        sa.Index(
            'idx_question_knowledge_point_gin',
            'knowledge_point',
            postgresql_ops={'knowledge_point': 'jsonb_path_ops'},
            postgresql_using='gin',
        ).ddl_if(dialect='postgresql'),
        {'comment': '题目表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    type: Mapped[str] = mapped_column(
        sa.String(16),
        comment='题型: single/multiple/judgement/fill/shortAnswer',
    )
    stem: Mapped[str] = mapped_column(
        UniversalText,
        comment='题干（富文本）',
    )
    difficulty: Mapped[Decimal | None] = mapped_column(
        sa.Numeric(3, 1),
        default=None,
        comment='难度 (1.0-5.0, 基于答题统计动态计算)',
    )
    default_score: Mapped[Decimal] = mapped_column(
        sa.Numeric(6, 2),
        default=Decimal('1.0'),
        comment='默认分值',
    )
    knowledge_point: Mapped[list[str | int | dict[str, Any]] | None] = mapped_column(
        CompatibleJSONB,
        default=None,
        comment='考点标签',
    )
    options: Mapped[list[dict[str, Any]] | None] = mapped_column(
        CompatibleJSONB,
        default=None,
        comment='选项列表: [{option_code, content, sort_order, is_active}]',
    )
    content_status: Mapped[int] = mapped_column(
        sa.SmallInteger,
        default=10,
        comment='内容状态: 0=待审核, 10=已通过, 20=已拒绝',
    )
    content_vector: Mapped[list[float] | None] = mapped_column(
        Vector(1536), default=None, deferred=True, comment='内容语义向量(1536维)，统合用于自动标注、相似推荐与AI问答'
    )

    # ============ 关系 ============
    analyses: Mapped[list['QuestionAnalysis']] = relationship(
        init=False,
        back_populates='question',
        lazy='noload',
    )
    statistics: Mapped['QuestionStatistics | None'] = relationship(
        init=False,
        back_populates='question',
        lazy='noload',
        uselist=False,
    )
    materials: Mapped[list['QuestionMaterial']] = relationship(
        init=False,
        secondary=question_material_relation,
        back_populates='questions',
        lazy='noload',
    )
    placements: Mapped[list['QuestionPlacement']] = relationship(
        init=False,
        back_populates='question',
        lazy='noload',
        cascade='all, delete-orphan',
    )


class QuestionAnalysis(Base, UserMixin):
    """题目解析表"""

    __tablename__ = 'study_question_analysis'
    __table_args__ = (
        sa.UniqueConstraint('question_id', 'type', 'version_no', name='uq_study_question_analysis_question_type_ver'),
        sa.Index('idx_analysis_question', 'question_id'),
        sa.Index('idx_analysis_question_default', 'question_id', 'is_default'),
        sa.Index('idx_analysis_question_status', 'question_id', 'status'),
        sa.Index('idx_analysis_type_status', 'type', 'status'),
        {'comment': '题目解析表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    question_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('study_question.id', ondelete='CASCADE'),
        comment='题目 ID',
    )
    answer_data: Mapped[dict] = mapped_column(
        CompatibleJSONB,
        comment='答案数据',
    )
    content: Mapped[str] = mapped_column(
        UniversalText,
        comment='解析内容（富文本）',
    )
    type: Mapped[str] = mapped_column(
        sa.String(32),
        default='official',
        comment='解析类型: official=官方, expert=名师, user=用户',
    )
    version_no: Mapped[int] = mapped_column(
        sa.SmallInteger,
        default=1,
        comment='版本号（同 type 下多版本）',
    )
    is_default: Mapped[bool] = mapped_column(default=False, comment='是否默认展示')
    view_count: Mapped[int] = mapped_column(sa.Integer, default=0, comment='查看次数')
    helpful_count: Mapped[int] = mapped_column(sa.Integer, default=0, comment='有帮助次数')
    unhelpful_count: Mapped[int] = mapped_column(sa.Integer, default=0, comment='无帮助次数')
    status: Mapped[int] = mapped_column(
        sa.SmallInteger,
        default=10,
        comment='状态: 0=待审核, 10=已通过, 20=已拒绝',
    )

    # ============ 关系 ============
    question: Mapped['Question'] = relationship(
        init=False,
        back_populates='analyses',
        lazy='noload',
    )


class QuestionStatistics(Base):
    """题目统计表"""

    __tablename__ = 'study_question_statistics'
    __table_args__ = (
        sa.Index('idx_statistics_question', 'question_id'),
        sa.Index('idx_statistics_rate', 'correct_rate'),
        sa.Index('idx_statistics_attempt', 'attempt_count'),
        sa.Index('idx_statistics_last_updated', 'last_updated'),
        {'comment': '题目统计表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    question_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('study_question.id', ondelete='CASCADE'),
        unique=True,
        comment='题目 ID',
    )
    attempt_count: Mapped[int] = mapped_column(sa.Integer, default=0, comment='答题总次数')
    correct_count: Mapped[int] = mapped_column(sa.Integer, default=0, comment='答对次数')
    correct_rate: Mapped[Decimal] = mapped_column(
        sa.Numeric(5, 2),
        default=Decimal('0'),
        comment='正确率（百分比）',
    )
    avg_answer_time: Mapped[Decimal | None] = mapped_column(
        sa.Numeric(8, 2),
        default=None,
        comment='平均答题时间（秒）',
    )
    valid_attempt_count: Mapped[int] = mapped_column(
        sa.Integer, default=0, comment='有效答题次数 (过滤 answer_time < 3s)'
    )
    valid_correct_count: Mapped[int] = mapped_column(sa.Integer, default=0, comment='有效答对次数')
    valid_avg_answer_time: Mapped[Decimal | None] = mapped_column(
        sa.Numeric(8, 2),
        default=None,
        comment='有效平均答题时间（秒）',
    )
    option_select_stats: Mapped[dict | None] = mapped_column(
        CompatibleJSONB,
        default=None,
        comment='选中选项统计',
    )
    collect_count: Mapped[int] = mapped_column(sa.Integer, default=0, comment='收藏次数')
    note_count: Mapped[int] = mapped_column(sa.Integer, default=0, comment='笔记次数')
    report_count: Mapped[int] = mapped_column(sa.Integer, default=0, comment='举报次数')
    last_updated: Mapped[datetime] = mapped_column(
        init=False,
        default_factory=datetime.now,
        onupdate=datetime.now,
        comment='最后更新时间',
    )

    # ============ 关系 ============
    question: Mapped['Question'] = relationship(
        init=False,
        back_populates='statistics',
        lazy='noload',
    )


class QuestionNote(Base, UserMixin):
    """
    题目笔记表

    设计思路：
    - 用户可为题目写笔记，支持公开分享
    - 公开笔记可被其他用户点赞/点踩
    - 管理员可精选优质笔记
    - quality_score = like_count - dislike_count，用于排序推荐
    """

    __tablename__ = 'study_question_note'
    __table_args__ = (
        sa.UniqueConstraint('user_id', 'question_id', name='uq_user_question_note'),
        sa.Index('idx_note_user_question', 'user_id', 'question_id'),
        sa.Index('idx_note_question_public_quality', 'question_id', 'is_public', 'quality_score'),
        sa.Index('idx_note_featured', 'is_featured', 'quality_score'),
        sa.Index('idx_note_user_bank', 'user_id', 'bank_id'),
        {'comment': '题目笔记表'},
    )

    # ============ 基础字段 ============
    id: Mapped[id_key] = mapped_column(init=False)
    user_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('study_user_account.user_id', ondelete='CASCADE'),
        comment='用户 ID',
    )
    question_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('study_question.id', ondelete='CASCADE'),
        comment='题目 ID',
    )

    # ============ 笔记内容 ============
    content: Mapped[str] = mapped_column(
        UniversalText,
        comment='笔记内容（Markdown 格式）',
    )

    # ============ 冗余字段（创建时快照，用于分组聚合） ============
    bank_id: Mapped[int | None] = mapped_column(sa.BigInteger, default=None, comment='题库 ID（冗余）')
    bank_name: Mapped[str | None] = mapped_column(sa.String(200), default=None, comment='题库名称（冗余）')
    chapter_id: Mapped[int | None] = mapped_column(sa.BigInteger, default=None, comment='章节 ID（冗余）')
    chapter_name: Mapped[str | None] = mapped_column(sa.String(200), default=None, comment='章节名称（冗余）')

    # ============ 公开设置 ============
    is_public: Mapped[bool] = mapped_column(default=False, comment='是否公开（公开后其他用户可见）')

    # ============ 互动统计（聚合数据，避免实时计算） ============
    like_count: Mapped[int] = mapped_column(sa.Integer, default=0, comment='点赞数')
    dislike_count: Mapped[int] = mapped_column(sa.Integer, default=0, comment='点踩数')
    view_count: Mapped[int] = mapped_column(sa.Integer, default=0, comment='浏览次数（仅公开笔记）')
    quality_score: Mapped[int] = mapped_column(
        sa.Integer, default=0, comment='质量分 = like_count - dislike_count（用于排序）'
    )

    # ============ 管理功能 ============
    is_featured: Mapped[bool] = mapped_column(default=False, comment='是否精选（管理员标记优质笔记）')
    featured_time: Mapped[datetime | None] = mapped_column(default=None, comment='精选时间')

    # ============ 时间字段 ============
    updated_time: Mapped[datetime] = mapped_column(
        init=False,
        default_factory=datetime.now,
        onupdate=datetime.now,
        comment='更新时间',
    )


class UserNoteVote(Base):
    """
    笔记投票表

    设计思路：
    - 用户对公开笔记进行点赞/点踩
    - 复合主键防止重复投票
    - vote_value: 1=点赞，-1=点踩
    - 单表设计（Reddit/StackExchange 模式），支持切换投票
    """

    __tablename__ = 'study_user_note_vote'
    __table_args__ = (
        sa.PrimaryKeyConstraint('user_id', 'note_id', name='pk_user_note_vote'),
        sa.Index('idx_vote_note', 'note_id'),
        sa.Index('idx_vote_user_time', 'user_id', 'created_time'),
        {'comment': '笔记投票表'},
    )

    # ============ 基础字段（复合主键） ============
    user_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('study_user_account.user_id', ondelete='CASCADE'),
        comment='投票用户 ID',
    )
    note_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('study_question_note.id', ondelete='CASCADE'),
        comment='笔记 ID',
    )

    # ============ 投票值 ============
    vote_value: Mapped[int] = mapped_column(
        sa.SmallInteger,
        comment='投票值：1=点赞，-1=点踩',
    )

    # ============ 时间字段 ============
    created_time: Mapped[datetime] = mapped_column(
        init=False,
        default_factory=datetime.now,
        comment='投票时间',
    )
    updated_time: Mapped[datetime] = mapped_column(
        init=False,
        default_factory=datetime.now,
        onupdate=datetime.now,
        comment='更新时间（用于切换投票）',
    )


class QuestionFavorite(Base, UserMixin):
    """
    题目收藏表

    设计思路：
    - 用户收藏题目，支持文件夹分组（类似 LeetCode）
    - 支持自定义标签（JSON 数组）
    - 支持置顶功能
    - 唯一约束防止重复收藏
    """

    __tablename__ = 'study_question_favorite'
    __table_args__ = (
        sa.UniqueConstraint('user_id', 'question_id', name='uq_user_question_favorite'),
        sa.Index('idx_favorite_user_pinned_time', 'user_id', 'is_pinned', 'created_time'),
        sa.Index('idx_favorite_user_folder', 'user_id', 'folder_name'),
        sa.Index('idx_favorite_question', 'question_id'),
        sa.Index('idx_favorite_placement', 'placement_id'),
        {'comment': '题目收藏表'},
    )

    # ============ 基础字段 ============
    id: Mapped[id_key] = mapped_column(init=False)
    user_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('study_user_account.user_id', ondelete='CASCADE'),
        comment='用户 ID',
    )
    question_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('study_question.id', ondelete='CASCADE'),
        comment='题目 ID',
    )
    placement_id: Mapped[int | None] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('study_question_placement.id', ondelete='SET NULL'),
        default=None,
        comment='挂载 ID（精确指定收藏的题库/章节上下文）',
    )

    # ============ 收藏夹分组（可选） ============
    folder_name: Mapped[str | None] = mapped_column(
        sa.String(100),
        default=None,
        comment='收藏夹名称（类似 LeetCode 的收藏夹功能，默认为空）',
    )

    # ============ 自定义标签 ============
    tags: Mapped[list[str] | None] = mapped_column(
        CompatibleJSONB,
        default=None,
        comment='自定义标签 JSON: ["重点", "易错", "常考"]',
    )

    # ============ 置顶功能 ============
    is_pinned: Mapped[bool] = mapped_column(default=False, comment='是否置顶')
    pinned_time: Mapped[datetime | None] = mapped_column(default=None, comment='置顶时间')

    # ============ 备注（可选） ============
    remark: Mapped[str | None] = mapped_column(sa.String(500), default=None, comment='备注')

    # ============ 冗余字段（收藏时快照，提升查询性能） ============
    # 原则：只冗余"稳定且不易变"的字段（题库、章节名称），题目信息通过 JOIN 获取
    bank_id: Mapped[int | None] = mapped_column(
        sa.BigInteger,
        default=None,
        comment='题库 ID（冗余字段）',
    )
    bank_name: Mapped[str | None] = mapped_column(
        sa.String(200),
        default=None,
        comment='题库名称（冗余字段，收藏时快照）',
    )
    chapter_id: Mapped[int | None] = mapped_column(
        sa.BigInteger,
        default=None,
        comment='章节 ID（冗余字段）',
    )
    chapter_name: Mapped[str | None] = mapped_column(
        sa.String(200),
        default=None,
        comment='章节名称（冗余字段，收藏时快照）',
    )


class QuestionMaterial(Base, UserMixin):
    """题目材料表"""

    __tablename__ = 'study_question_material'
    __table_args__ = (
        sa.Index('idx_material_bank', 'bank_id'),
        sa.Index('idx_material_category', 'category_id'),
        sa.Index('idx_material_active', 'is_active'),
        sa.Index('idx_material_bank_sort', 'bank_id', 'sort_order'),
        sa.Index('idx_material_bank_active', 'bank_id', 'is_active'),
        {'comment': '题目材料表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    bank_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('study_question_bank.id', ondelete='CASCADE'),
        comment='题库 ID',
    )
    title: Mapped[str] = mapped_column(sa.String(255), comment='材料标题')
    content: Mapped[str] = mapped_column(UniversalText, comment='材料内容（富文本）')
    category_id: Mapped[int | None] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('sys_category.id', ondelete='SET NULL'),
        default=None,
        comment='分类 ID',
    )
    source: Mapped[str | None] = mapped_column(sa.String(255), default=None, comment='来源')
    year: Mapped[int | None] = mapped_column(sa.SmallInteger, default=None, comment='年份')
    sort_order: Mapped[int] = mapped_column(sa.Integer, default=0, comment='排序')
    is_active: Mapped[bool] = mapped_column(default=True, comment='是否启用')

    # ============ 关系 ============
    bank: Mapped['QuestionBank'] = relationship(init=False, lazy='noload')
    questions: Mapped[list['Question']] = relationship(
        init=False,
        secondary=question_material_relation,
        back_populates='materials',
        lazy='noload',
    )


class MaterialAnchor(Base, UserMixin):
    """材料锚点表"""

    __tablename__ = 'study_material_anchor'
    __table_args__ = (
        sa.UniqueConstraint('material_id', 'anchor_key', 'deleted', name='uq_material_anchor_key_deleted'),
        sa.Index('idx_material_anchor_material', 'material_id'),
        sa.Index('idx_material_anchor_type_status', 'anchor_type', 'status'),
        sa.Index('idx_material_anchor_content_hash', 'content_hash'),
        sa.Index('idx_material_anchor_asset_hash', 'asset_hash'),
        sa.CheckConstraint(
            "anchor_type IN ('text_range','image_region','table_cell','text_block','image_point')",
            name='ck_material_anchor_type',
        ),
        sa.CheckConstraint("source IN ('manual','ocr','ai','import')", name='ck_material_anchor_source'),
        sa.CheckConstraint('status IN (0,10,20)', name='ck_material_anchor_status'),
        {'comment': '材料锚点表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    material_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('study_question_material.id', ondelete='CASCADE'),
        comment='材料 ID',
    )
    anchor_key: Mapped[str] = mapped_column(sa.String(128), comment='锚点业务键')
    anchor_type: Mapped[str] = mapped_column(sa.String(32), comment='锚点类型')
    text: Mapped[str | None] = mapped_column(UniversalText, default=None, comment='锚点文本')
    role: Mapped[str | None] = mapped_column(sa.String(64), default=None, comment='锚点语义角色')
    block_id: Mapped[str | None] = mapped_column(sa.String(128), default=None, comment='材料分块 ID')
    start_offset: Mapped[int | None] = mapped_column(sa.Integer, default=None, comment='文本起始偏移')
    end_offset: Mapped[int | None] = mapped_column(sa.Integer, default=None, comment='文本结束偏移')
    asset_url: Mapped[str | None] = mapped_column(sa.String(1024), default=None, comment='图片或资源地址')
    asset_hash: Mapped[str | None] = mapped_column(sa.String(128), default=None, comment='资源哈希')
    natural_width: Mapped[int | None] = mapped_column(sa.Integer, default=None, comment='资源原始宽度')
    natural_height: Mapped[int | None] = mapped_column(sa.Integer, default=None, comment='资源原始高度')
    bbox: Mapped[dict[str, Any] | None] = mapped_column(CompatibleJSONB, default=None, comment='归一化矩形区域')
    polygon: Mapped[list[dict[str, Any]] | None] = mapped_column(
        CompatibleJSONB, default=None, comment='归一化多边形区域'
    )
    table_cell: Mapped[dict[str, Any] | None] = mapped_column(CompatibleJSONB, default=None, comment='表格单元格定位')
    ocr_confidence: Mapped[Decimal | None] = mapped_column(
        sa.Numeric(5, 4), default=None, comment='OCR 置信度'
    )
    source: Mapped[str] = mapped_column(sa.String(16), default='manual', comment='来源')
    content_hash: Mapped[str | None] = mapped_column(sa.String(128), default=None, comment='材料内容哈希')
    status: Mapped[int] = mapped_column(sa.SmallInteger, default=10, comment='状态: 0=待审核, 10=可用, 20=废弃')
    extra_data: Mapped[dict[str, Any]] = mapped_column(CompatibleJSONB, default_factory=dict, comment='扩展数据')

    material: Mapped[QuestionMaterial] = relationship(init=False, lazy='noload')


class QuestionInteractionAnnotation(Base, UserMixin):
    """题目交互标注表"""

    __tablename__ = 'study_question_interaction_annotation'
    __table_args__ = (
        sa.UniqueConstraint(
            'question_id',
            'annotation_key',
            'version_no',
            'deleted',
            name='uq_question_interaction_version_deleted',
        ),
        sa.Index('idx_question_interaction_question', 'question_id'),
        sa.Index('idx_question_interaction_material', 'material_id'),
        sa.Index('idx_question_interaction_type_status', 'interaction_type', 'status'),
        sa.Index('idx_question_interaction_default', 'question_id', 'interaction_type', 'is_default'),
        sa.CheckConstraint(
            "selection_mode IN ('single','multiple','multi_role')",
            name='ck_question_interaction_selection_mode',
        ),
        sa.CheckConstraint('status IN (0,10,20)', name='ck_question_interaction_status'),
        {'comment': '题目交互标注表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    question_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('study_question.id', ondelete='CASCADE'),
        comment='题目 ID',
    )
    annotation_key: Mapped[str] = mapped_column(sa.String(128), comment='标注业务键')
    interaction_type: Mapped[str] = mapped_column(sa.String(32), comment='交互类型')
    instruction: Mapped[str] = mapped_column(UniversalText, comment='交互指令')
    material_id: Mapped[int | None] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('study_question_material.id', ondelete='CASCADE'),
        default=None,
        comment='材料 ID',
    )
    title: Mapped[str | None] = mapped_column(sa.String(128), default=None, comment='标注标题')
    selection_mode: Mapped[str] = mapped_column(sa.String(16), default='single', comment='选择模式')
    candidate_anchor_ids: Mapped[list[int]] = mapped_column(
        CompatibleJSONB, default_factory=list, comment='候选锚点 ID'
    )
    answer_data: Mapped[dict[str, Any]] = mapped_column(CompatibleJSONB, default_factory=dict, comment='答案数据')
    config: Mapped[dict[str, Any]] = mapped_column(CompatibleJSONB, default_factory=dict, comment='交互配置')
    content_hash: Mapped[str | None] = mapped_column(sa.String(128), default=None, comment='材料内容哈希')
    version_no: Mapped[int] = mapped_column(sa.SmallInteger, default=1, comment='版本号')
    is_default: Mapped[bool] = mapped_column(default=True, comment='是否默认使用')
    status: Mapped[int] = mapped_column(sa.SmallInteger, default=10, comment='状态: 0=待审核, 10=可用, 20=废弃')

    question: Mapped[Question] = relationship(init=False, lazy='noload')
    material: Mapped[QuestionMaterial | None] = relationship(init=False, lazy='noload')
