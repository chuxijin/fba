#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
重构后的题目相关模型

主要改进：
1. 题目和解析分离 - 支持多版本解析、用户贡献
2. 选项 JSON 化 - 简化查询，适合大多数场景
3. 统计数据分离 - 避免频繁更新题目表，提升性能
4. 索引优化 - 针对高频查询建立联合索引
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.common.model import Base, UniversalText, UserMixin, id_key

if TYPE_CHECKING:
    from .bank import QuestionBank
    from .chapter import QuestionChapter


# 题目-材料关联表（多对多）
question_material_relation = sa.Table(
    'study_question_material_relation',
    Base.metadata,
    sa.Column('question_id', sa.BigInteger, sa.ForeignKey('study_question.id', ondelete='CASCADE'), primary_key=True),
    sa.Column('material_id', sa.BigInteger, sa.ForeignKey('study_question_material.id', ondelete='CASCADE'), primary_key=True),
    sa.Column('sort_order', sa.Integer, default=0, comment='排序'),
    comment='题目-材料关联表'
)


class Question(Base, UserMixin):
    """
    题目表 - 只存储题目核心信息

    设计原则：
    - 题干和选项使用富文本（媒体资源直接嵌入）
    - 解析分离到 QuestionAnalysis 表
    - 统计分离到 QuestionStatistics 表
    """

    __tablename__ = 'study_question'
    __table_args__ = (
        sa.Index('idx_question_bank_type_status', 'bank_id', 'type', 'review_status'),
        sa.Index('idx_question_bank_sort', 'bank_id', 'sort_order'),
        sa.Index('idx_question_chapter', 'chapter_id'),
        sa.Index('idx_question_active_created', 'is_active', 'created_time'),
        {'comment': '题目表'},
    )

    # ============ 基础字段 ============
    id: Mapped[id_key] = mapped_column(init=False)
    bank_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('study_question_bank.id', ondelete='CASCADE'),
        comment='题库 ID',
    )

    # ============ 题目内容（必填字段） ============
    type: Mapped[str] = mapped_column(
        sa.String(16),
        comment='题型: single/multiple/judgement/fill/shortAnswer',
    )
    stem: Mapped[str] = mapped_column(
        UniversalText,
        comment='题干（富文本，包含图片/视频等媒体资源）',
    )

    # ============ 基础字段（可选） ============
    chapter_id: Mapped[int | None] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('study_question_chapter.id', ondelete='SET NULL'),
        default=None,
        comment='章节 ID',
    )

    # ============ 选项数据 (JSON) ============
    options_data: Mapped[dict | None] = mapped_column(
        sa.JSON,
        default=None,
        comment="""
        选项数据（富文本）:
        {
            "A": {"code": "A", "content": "<p>选项A内容<img src='...' /></p>"},
            "B": {"code": "B", "content": "<p>选项B内容</p>"},
            "C": {"code": "C", "content": "<p>选项C<video src='...' /></p>"},
            "D": {"code": "D", "content": "<p>选项D</p>"}
        }
        注：不包含答案标识，答案统一存储在 QuestionAnalysis.answer_data
        填空题/简答题为 null
        """,
    )

    # ============ 元数据 ============
    sort_order: Mapped[int] = mapped_column(
        sa.Integer,
        default=0,
        comment='题目序号（在题库/章节内的排序）',
    )
    difficulty: Mapped[str] = mapped_column(
        sa.String(16),
        default='medium',
        comment='难度: easy/medium/hard',
    )
    score: Mapped[Decimal] = mapped_column(
        sa.Numeric(6, 2),
        default=Decimal('1.0'),
        comment='默认分值',
    )
    knowledge_point: Mapped[str | None] = mapped_column(
        sa.String(255),
        default=None,
        comment='考点（多个用逗号分隔）',
    )
    source: Mapped[str | None] = mapped_column(sa.String(255), default=None, comment='来源')
    year: Mapped[int | None] = mapped_column(sa.SmallInteger, default=None, comment='年份')
    usage: Mapped[str] = mapped_column(
        sa.String(16),
        default='all',
        comment='用途: all/exam/practice',
    )

    # ============ 状态字段 ============
    is_active: Mapped[bool] = mapped_column(default=True, comment='是否启用')
    review_status: Mapped[int] = mapped_column(
        sa.SmallInteger,
        default=10,
        comment='审核状态: 0=待审核, 10=已通过, 20=已拒绝',
    )

    # ============ 关系 ============
    bank: Mapped['QuestionBank'] = relationship(
        init=False,
        back_populates='questions',
        lazy='joined',
    )
    chapter: Mapped['QuestionChapter | None'] = relationship(
        init=False,
        back_populates='questions',
        lazy='joined',
    )
    analyses: Mapped[list['QuestionAnalysis']] = relationship(
        init=False,
        back_populates='question',
        lazy='selectin',
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
        lazy='selectin',
    )


class QuestionAnalysis(Base, UserMixin):
    """
    题目解析表 - 与题目完全分离

    设计目标：
    - 包含答案和解析内容
    - 支持多版本解析（官方、名师、用户等）
    - 解析内容使用富文本（媒体直接嵌入）
    """

    __tablename__ = 'study_question_analysis'
    __table_args__ = (
        sa.Index('idx_analysis_question', 'question_id'),
        {'comment': '题目解析表'},
    )

    # ============ 基础字段 ============
    id: Mapped[id_key] = mapped_column(init=False)
    question_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('study_question.id', ondelete='CASCADE'),
        # unique=True,  # 移除唯一约束，支持多版本
        comment='题目 ID',
    )
    


    # ============ 答案数据 (JSON) ============
    answer_data: Mapped[dict] = mapped_column(
        sa.JSON,
        comment="""
        答案数据:
        单选/判断: {"correct": "A"}
        多选: {"correct": ["A", "C"]}
        填空: {"correct": ["答案1", "答案2"]}
        简答: {"keywords": ["关键词1", "关键词2"]}
        """,
    )

    # ============ 解析内容 ============
    content: Mapped[str] = mapped_column(
        UniversalText,
        comment='解析内容（富文本，包含图片/视频等媒体资源）',
    )

    # ============ 解析类型 ============
    type: Mapped[str] = mapped_column(
        sa.String(32),
        default='official',
        comment='解析类型: official=官方, expert=名师, user=用户',
    )
    is_default: Mapped[bool] = mapped_column(default=False, comment='是否默认展示')

    # ============ 互动数据 ============
    view_count: Mapped[int] = mapped_column(sa.Integer, default=0, comment='查看次数')
    helpful_count: Mapped[int] = mapped_column(sa.Integer, default=0, comment='有帮助次数')
    unhelpful_count: Mapped[int] = mapped_column(sa.Integer, default=0, comment='无帮助次数')

    # ============ 关系 ============
    question: Mapped['Question'] = relationship(
        init=False,
        back_populates='analyses',
        lazy='noload',
    )


class QuestionStatistics(Base):
    """
    题目统计表

    设计目标：
    - 分离高频更新的统计数据，避免影响题目表性能
    - 支持实时统计和定时批量更新
    - 为推荐算法提供数据支持
    """

    __tablename__ = 'study_question_statistics'
    __table_args__ = (
        sa.Index('idx_statistics_question', 'question_id'),
        sa.Index('idx_statistics_rate', 'correct_rate'),
        {'comment': '题目统计表'},
    )

    # ============ 基础字段 ============
    id: Mapped[id_key] = mapped_column(init=False)
    question_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('study_question.id', ondelete='CASCADE'),
        unique=True,
        comment='题目 ID',
    )

    # ============ 答题统计 ============
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

    # ============ 选项统计 ============
    wrong_option_stats: Mapped[dict | None] = mapped_column(
        sa.JSON,
        default=None,
        comment="""
        错误选项统计:
        {
            "B": 1250,  # 选择B的次数
            "D": 850,   # 选择D的次数
            "C": 320
        }
        """,
    )

    # ============ 用户行为统计 ============
    collect_count: Mapped[int] = mapped_column(sa.Integer, default=0, comment='收藏次数')
    note_count: Mapped[int] = mapped_column(sa.Integer, default=0, comment='笔记次数')
    report_count: Mapped[int] = mapped_column(sa.Integer, default=0, comment='举报次数')

    # ============ 时间字段 ============
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
        sa.Index('idx_note_user_question', 'user_id', 'question_id'),
        sa.Index('idx_note_question_public_quality', 'question_id', 'is_public', 'quality_score'),
        sa.Index('idx_note_featured', 'is_featured', 'quality_score'),
        {'comment': '题目笔记表'},
    )

    # ============ 基础字段 ============
    id: Mapped[id_key] = mapped_column(init=False)
    user_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('study_user_account.id', ondelete='CASCADE'),
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
        sa.ForeignKey('study_user_account.id', ondelete='CASCADE'),
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
        {'comment': '题目收藏表'},
    )

    # ============ 基础字段 ============
    id: Mapped[id_key] = mapped_column(init=False)
    user_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('study_user_account.id', ondelete='CASCADE'),
        comment='用户 ID',
    )
    question_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('study_question.id', ondelete='CASCADE'),
        comment='题目 ID',
    )

    # ============ 收藏夹分组（可选） ============
    folder_name: Mapped[str | None] = mapped_column(
        sa.String(100),
        default=None,
        comment='收藏夹名称（类似 LeetCode 的收藏夹功能，默认为空）',
    )

    # ============ 自定义标签 ============
    tags: Mapped[list[str] | None] = mapped_column(
        sa.JSON,
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
    """
    题目材料表

    设计思路：
    - 存储阅读理解、资料分析、案例分析等题型的共享材料
    - 一个材料可对应多道题目（一对多关系）
    - 材料内容使用富文本，支持图片/表格等媒体
    """

    __tablename__ = 'study_question_material'
    __table_args__ = (
        sa.Index('idx_material_bank', 'bank_id'),
        sa.Index('idx_material_category', 'category_id'),
        sa.Index('idx_material_active', 'is_active'),
        {'comment': '题目材料表'},
    )

    # ============ 基础字段 ============
    id: Mapped[id_key] = mapped_column(init=False)
    bank_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('study_question_bank.id', ondelete='CASCADE'),
        comment='题库 ID',
    )


    # ============ 材料内容 ============
    title: Mapped[str] = mapped_column(
        sa.String(255),
        comment='材料标题',
    )
    content: Mapped[str] = mapped_column(
        UniversalText,
        comment='材料内容（富文本，支持图片/表格等媒体资源）',
    )
    category_id: Mapped[int | None] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('sys_category.id', ondelete='SET NULL'),
        default=None,
        comment='分类 ID',
    )

    # ============ 元数据 ============
    source: Mapped[str | None] = mapped_column(sa.String(255), default=None, comment='来源')
    year: Mapped[int | None] = mapped_column(sa.SmallInteger, default=None, comment='年份')
    sort_order: Mapped[int] = mapped_column(sa.Integer, default=0, comment='排序顺序')

    # ============ 状态字段 ============
    is_active: Mapped[bool] = mapped_column(default=True, comment='是否启用')

    # ============ 关系 ============
    bank: Mapped['QuestionBank'] = relationship(
        init=False,
        lazy='joined',
    )
    questions: Mapped[list['Question']] = relationship(
        init=False,
        secondary=question_material_relation,
        back_populates='materials',
        lazy='noload',
    )
