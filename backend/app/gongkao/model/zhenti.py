#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime
from decimal import Decimal

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from backend.common.model import Base, UserMixin, id_key


class GkQuestion(Base, UserMixin):
    """公考题目表"""

    __tablename__ = 'gk_question'
    __table_args__ = {'comment': '公考题目表'}

    id: Mapped[id_key] = mapped_column(init=False)

    # 基础信息（必填字段）
    title: Mapped[str] = mapped_column(sa.Text, comment='题目题干')
    type: Mapped[str] = mapped_column(sa.String(20), index=True, comment='题型')
    category_id: Mapped[int] = mapped_column(sa.BigInteger, index=True, comment='关联分类 ID')

    # 基础信息（可选字段）
    material_ids: Mapped[list[int] | None] = mapped_column(sa.JSON, default=None, comment='关联材料 ID 列表')
    difficulty: Mapped[Decimal | None] = mapped_column(sa.Numeric(3, 1), default=None, comment='难度')
    year: Mapped[int | None] = mapped_column(sa.Integer, default=None, index=True, comment='年份')
    source: Mapped[str | None] = mapped_column(sa.String(100), default=None, comment='来源')
    tags: Mapped[str | None] = mapped_column(sa.JSON, default=None, comment='标签')
    score: Mapped[Decimal | None] = mapped_column(sa.Numeric(5, 1), default=None, comment='分值')
    view_count: Mapped[int] = mapped_column(default=0, comment='浏览量')
    status: Mapped[bool] = mapped_column(default=True, comment='状态')
    sort_order: Mapped[int] = mapped_column(default=0, comment='排序权重')


class GkQuestionOption(Base):
    """公考题目选项表"""

    __tablename__ = 'gk_question_option'
    __table_args__ = {'comment': '公考题目选项表'}

    id: Mapped[id_key] = mapped_column(init=False)

    # 基础信息（必填字段）
    question_id: Mapped[int] = mapped_column(sa.BigInteger, index=True, comment='关联题目 ID')
    option_key: Mapped[str] = mapped_column(sa.String(10), comment='选项标识')
    option_content: Mapped[str] = mapped_column(sa.Text, comment='选项内容')

    # 基础信息（可选字段）
    sort_order: Mapped[int] = mapped_column(default=0, comment='排序')
    created_time: Mapped[datetime] = mapped_column(init=False, default_factory=datetime.now, comment='创建时间')
    updated_time: Mapped[datetime | None] = mapped_column(init=False, onupdate=datetime.now, default=None, comment='更新时间')


class GkQuestionAnswer(Base):
    """公考题目答案表"""

    __tablename__ = 'gk_question_answer'
    __table_args__ = {'comment': '公考题目答案表'}

    id: Mapped[id_key] = mapped_column(init=False)

    # 基础信息（必填字段）
    question_id: Mapped[int] = mapped_column(sa.BigInteger, index=True, comment='关联题目 ID')
    source: Mapped[str] = mapped_column(sa.String(100), comment='答案来源')

    # 答案字段（二选一）
    answer_keys: Mapped[str | None] = mapped_column(sa.String(500), default=None, comment='客观题答案')
    answer: Mapped[str | None] = mapped_column(sa.Text, default=None, comment='主观题答案')

    # 解析信息（可选字段）
    analysis: Mapped[str | None] = mapped_column(sa.Text, default=None, comment='答案解析')
    analysis_video_url: Mapped[str | None] = mapped_column(sa.String(500), default=None, comment='视频解析链接')
    knowledge_points: Mapped[str | None] = mapped_column(sa.JSON, default=None, comment='知识点')
    reference_materials: Mapped[str | None] = mapped_column(sa.Text, default=None, comment='参考资料')
    is_official: Mapped[bool] = mapped_column(default=False, comment='是否官方答案')
    created_time: Mapped[datetime] = mapped_column(init=False, default_factory=datetime.now, comment='创建时间')
    updated_time: Mapped[datetime | None] = mapped_column(init=False, onupdate=datetime.now, default=None, comment='更新时间')


class GkMaterial(Base, UserMixin):
    """公考材料表"""

    __tablename__ = 'gk_material'
    __table_args__ = {'comment': '公考材料表'}

    id: Mapped[id_key] = mapped_column(init=False)

    # 基础信息（必填字段）
    title: Mapped[str] = mapped_column(sa.String(256), comment='材料标题')
    content: Mapped[str] = mapped_column(sa.Text, comment='材料内容')
    category_id: Mapped[int] = mapped_column(sa.BigInteger, index=True, comment='关联分类 ID')

    # 基础信息（可选字段）
    year: Mapped[int | None] = mapped_column(sa.Integer, default=None, index=True, comment='年份')
    source: Mapped[str | None] = mapped_column(sa.String(100), default=None, comment='来源')
    tags: Mapped[str | None] = mapped_column(sa.JSON, default=None, comment='标签')
    view_count: Mapped[int] = mapped_column(default=0, comment='浏览量')
    status: Mapped[bool] = mapped_column(default=True, comment='状态')
    sort_order: Mapped[int] = mapped_column(default=0, comment='排序权重')
