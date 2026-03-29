#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import ConfigDict, Field

from backend.app.question_bank.schema.chapter import GetChapterTree
from backend.common.schema import SchemaBase


class BankSchemaBase(SchemaBase):
    """题库基础"""

    cat_id: int = Field(description='分类 ID')
    name: str = Field(max_length=128, description='题库名称')
    code: str = Field(max_length=32, description='业务编码')
    desc: str | None = Field(None, description='描述')
    cover_url: str | None = Field(None, description='封面地址')
    difficulty: Decimal | None = Field(None, ge=0, description='整体难度')
    bank_type: Literal[1, 2, 3] = Field(default=1, description='内容类型: 1=题库, 2=试卷, 3=合集')
    scene_mask: int = Field(default=1, ge=0, description='可用场景位标记: 1=练习, 2=考试, 4=模考, 8=错题重练')
    parent_id: int | None = Field(None, description='父题库 ID')
    chapter_source_bank_id: int | None = Field(None, description='篇章来源题库 ID')
    status: int = Field(default=1, ge=0, description='状态')
    access_entitlement_code: str | None = Field(None, max_length=64, description='访问所需权益编码，为空表示公开')


class GetBankDetail(BankSchemaBase):
    """题库详情"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='题库 ID')
    q_count_cache: int = Field(description='缓存题量')
    total_score_cache: Decimal = Field(description='缓存总分')
    buy_count: int = Field(description='购买数量')
    created_by: int = Field(description='创建者')
    updated_by: int | None = Field(None, description='修改者')
    created_time: datetime = Field(description='创建时间')
    updated_time: datetime | None = Field(None, description='更新时间')


class GetBankDetailWithChapters(GetBankDetail):
    """题库详情"""

    chapters: list[GetChapterTree] = Field(default_factory=list, description='篇章树')


class GetBankWithRelationDetail(GetBankDetail):
    """题库关联详情"""

    model_config = ConfigDict(from_attributes=True)

    category: dict | None = Field(None, description='分类信息')


class BankParam(SchemaBase):
    """题库查询参数"""

    cat_id: int | None = Field(None, description='分类 ID')
    status: int | None = Field(None, ge=0, description='题库状态')
    keyword: str | None = Field(None, description='关键字搜索')
    bank_type: Literal[1, 2, 3] | None = Field(None, description='内容类型: 1=题库, 2=试卷, 3=合集')
    parent_id: int | None = Field(None, description='父题库 ID')
    scene_mask: int | None = Field(None, ge=0, description='可用场景位标记')


class CreateBankParam(BankSchemaBase):
    """创建题库参数"""


class UpdateBankParam(BankSchemaBase):
    """更新题库参数"""


class DeleteBankParam(SchemaBase):
    """删除题库参数"""

    ids: list[int] = Field(description='题库 ID 列表')


class ChapterProgressNode(SchemaBase):
    """篇章进度节点"""

    chapter_id: int = Field(description='篇章 ID')
    name: str = Field(description='篇章名称')
    question_count: int = Field(default=0, description='题目总数')
    answer_count: int = Field(default=0, description='已做题数')
    correct_count: int = Field(default=0, description='答对数')
    correct_ratio: Decimal = Field(default=Decimal('0'), description='正确率')
    children: list['ChapterProgressNode'] = Field(default_factory=list, description='子篇章')


class GetBankChapterProgress(SchemaBase):
    """题库篇章进度"""

    bank_id: int = Field(description='题库 ID')
    total_question_count: int = Field(default=0, description='总题数')
    total_answer_count: int = Field(default=0, description='总已做题数')
    total_correct_count: int = Field(default=0, description='总答对数')
    chapters: list[ChapterProgressNode] = Field(default_factory=list, description='篇章进度树')
