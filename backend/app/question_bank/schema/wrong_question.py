#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
错题本相关 Schema

设计原则：
- 答错自动加入，答对3次自动掌握
- 支持置顶和移除功能
"""
from datetime import datetime

from pydantic import ConfigDict, Field

from backend.common.schema import SchemaBase


# ============ 错题本 Schema ============


class WrongQuestionSchemaBase(SchemaBase):
    """错题本基础 Schema"""

    question_id: int = Field(description='题目 ID')


class GetWrongQuestionDetail(WrongQuestionSchemaBase):
    """错题本详情"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='错题 ID')
    user_id: int = Field(description='用户 ID')
    wrong_count: int = Field(description='错误次数')
    correct_count: int = Field(description='连续做对次数')
    first_wrong_time: datetime = Field(description='首次错误时间')
    last_wrong_time: datetime = Field(description='最后一次错误时间')
    last_practice_time: datetime | None = Field(None, description='最后一次练习时间')
    is_mastered: bool = Field(description='是否已掌握（连续答对3次）')
    mastered_time: datetime | None = Field(None, description='掌握时间')
    is_pinned: bool = Field(description='是否置顶')
    pinned_time: datetime | None = Field(None, description='置顶时间')
    created_time: datetime = Field(description='创建时间')


class GetWrongQuestionListItem(SchemaBase):
    """错题本列表项"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='错题 ID')
    question_id: int = Field(description='题目 ID')
    wrong_count: int = Field(description='错误次数')
    correct_count: int = Field(description='连续做对次数')
    last_wrong_time: datetime = Field(description='最后一次错误时间')
    is_mastered: bool = Field(description='是否已掌握')
    is_pinned: bool = Field(description='是否置顶')
    # 扁平化字段，方便前端显示
    question_stem: str | None = Field(None, description='题目题干')
    question_type: str | None = Field(None, description='题型')
    bank_id: int | None = Field(None, description='题库 ID')
    bank_name: str | None = Field(None, description='题库名称')
    chapter_id: int | None = Field(None, description='章节 ID')
    chapter_name: str | None = Field(None, description='章节名称')
    cat_id: int | None = Field(None, description='分类 ID')
    cat_name: str | None = Field(None, description='分类名称')


class SetWrongQuestionPinParam(SchemaBase):
    """设置错题置顶参数"""

    wrong_id: int = Field(description='错题 ID')
    is_pinned: bool = Field(description='是否置顶')


class BatchDeleteWrongQuestionsParam(SchemaBase):
    """批量删除错题参数"""

    wrong_ids: list[int] = Field(description='错题 ID 列表')


class WrongQuestionStatistics(SchemaBase):
    """错题本统计"""

    total_count: int = Field(description='错题总数')
    mastered_count: int = Field(description='已掌握数量')
    unmastered_count: int = Field(description='未掌握数量')
    avg_wrong_count: float = Field(description='平均错误次数')
