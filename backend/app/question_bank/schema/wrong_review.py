#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime

from pydantic import ConfigDict, Field

from backend.common.schema import SchemaBase


# ───────────────── 错因标签 ─────────────────


class CreateReasonTagParam(SchemaBase):
    """创建错因标签"""

    name: str = Field(min_length=1, max_length=64, description='标签名称')
    color: str | None = Field(None, max_length=16, description='标签颜色')


class GetReasonTagItem(SchemaBase):
    """错因标签列表项"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='标签 ID')
    name: str = Field(description='标签名称')
    color: str | None = Field(None, description='标签颜色')
    is_system: bool = Field(description='是否系统预设')
    display_order: int = Field(description='排序权重')


# ───────────────── 自定义错题 ─────────────────


class CreateCustomQuestionParam(SchemaBase):
    """创建自定义错题"""

    question_id: int | None = Field(None, gt=0, description='关联题库题目 ID')
    category_id: int | None = Field(None, gt=0, description='关联题库分类 ID')
    stem: str | None = Field(None, description='题干文本')
    images: list[str] | None = Field(None, description='截图 URL 数组')
    options: dict | list | None = Field(None, description='选项')
    answer: str | None = Field(None, description='正确答案')
    explanation: str | None = Field(None, description='解析')
    source: str | None = Field(None, max_length=255, description='来源')
    reasons: list[int] | None = Field(None, description='错因标签 ID 数组')
    summary: str | None = Field(None, description='一句话复盘')
    duration_seconds: int | None = Field(None, ge=0, description='做题用时（秒）')


class UpdateCustomQuestionParam(SchemaBase):
    """更新自定义错题"""

    question_id: int | None = Field(None, gt=0, description='关联题库题目 ID')
    category_id: int | None = Field(None, gt=0, description='关联题库分类 ID')
    stem: str | None = Field(None, description='题干文本')
    images: list[str] | None = Field(None, description='截图 URL 数组')
    options: dict | list | None = Field(None, description='选项')
    answer: str | None = Field(None, description='正确答案')
    explanation: str | None = Field(None, description='解析')
    source: str | None = Field(None, max_length=255, description='来源')
    reasons: list[int] | None = Field(None, description='错因标签 ID 数组')
    summary: str | None = Field(None, description='一句话复盘')
    duration_seconds: int | None = Field(None, ge=0, description='做题用时（秒）')


class GetCustomQuestionDetail(SchemaBase):
    """自定义错题详情"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='错题 ID')
    user_id: int = Field(description='用户 ID')
    question_id: int | None = Field(None, description='关联题库题目 ID')
    category_id: int | None = Field(None, description='关联题库分类 ID')
    stem: str | None = Field(None, description='题干文本')
    images: list[str] | None = Field(None, description='截图 URL 数组')
    options: dict | list | None = Field(None, description='选项')
    answer: str | None = Field(None, description='正确答案')
    explanation: str | None = Field(None, description='解析')
    source: str | None = Field(None, description='来源')
    reasons: list[int] | None = Field(None, description='错因标签 ID 数组')
    summary: str | None = Field(None, description='一句话复盘')
    duration_seconds: int | None = Field(None, description='做题用时（秒）')
    created_time: datetime = Field(description='创建时间')
    updated_time: datetime = Field(description='更新时间')


class GetCustomQuestionListItem(SchemaBase):
    """自定义错题列表项"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='错题 ID')
    stem: str | None = Field(None, description='题干文本')
    images: list[str] | None = Field(None, description='截图 URL 数组')
    category_id: int | None = Field(None, description='关联题库分类 ID')
    source: str | None = Field(None, description='来源')
    reasons: list[int] | None = Field(None, description='错因标签 ID 数组')
    summary: str | None = Field(None, description='一句话复盘')
    duration_seconds: int | None = Field(None, description='做题用时（秒）')
    created_time: datetime = Field(description='创建时间')


class CustomQuestionQueryParam(SchemaBase):
    """自定义错题查询参数"""

    category_id: int | None = Field(None, gt=0, description='按分类筛选')
    source: str | None = Field(None, max_length=255, description='按来源筛选')
    keyword: str | None = Field(None, max_length=200, description='关键词搜索')


# ───────────────── 复盘记录 ─────────────────


class CreateReviewParam(SchemaBase):
    """创建复盘记录"""

    review_type: str = Field(description='复盘类型: auto/custom')
    wrong_book_id: int | None = Field(None, gt=0, description='关联自动收录错题 ID')
    custom_question_id: int | None = Field(None, gt=0, description='关联自定义错题 ID')
    duration_seconds: int = Field(ge=0, description='复盘用时（秒）')
    reasons: list[int] | None = Field(None, description='错因标签 ID 数组')
    summary: str | None = Field(None, description='一句话复盘')
    is_mastered: bool | None = Field(None, description='是否标记为已掌握')



class GetReviewDetail(SchemaBase):
    """复盘记录详情"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='复盘 ID')
    user_id: int = Field(description='用户 ID')
    review_type: str = Field(description='复盘类型')
    wrong_book_id: int | None = Field(None, description='关联自动收录错题 ID')
    custom_question_id: int | None = Field(None, description='关联自定义错题 ID')
    duration_seconds: int = Field(description='复盘用时（秒）')
    reasons: list[int] | None = Field(None, description='错因标签 ID 数组')
    summary: str | None = Field(None, description='一句话复盘')
    reviewed_time: datetime = Field(description='复盘时间')
    created_time: datetime = Field(description='创建时间')


class GetReviewListItem(SchemaBase):
    """复盘记录列表项"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='复盘 ID')
    review_type: str = Field(description='复盘类型')
    wrong_book_id: int | None = Field(None, description='关联自动收录错题 ID')
    custom_question_id: int | None = Field(None, description='关联自定义错题 ID')
    duration_seconds: int = Field(description='复盘用时（秒）')
    reasons: list[int] | None = Field(None, description='错因标签 ID 数组')
    summary: str | None = Field(None, description='一句话复盘')
    reviewed_time: datetime = Field(description='复盘时间')


class ReviewQueryParam(SchemaBase):
    """复盘记录查询参数"""

    review_type: str | None = Field(None, description='按复盘类型筛选')
    start_date: datetime | None = Field(None, description='开始日期')
    end_date: datetime | None = Field(None, description='结束日期')


# ───────────────── 看板统计 ─────────────────


class ReasonDistributionItem(SchemaBase):
    """错因分布"""

    tag_id: int = Field(description='标签 ID')
    tag_name: str = Field(description='标签名称')
    color: str | None = Field(None, description='标签颜色')
    count: int = Field(description='出现次数')
    percentage: float = Field(description='占比百分比')


class WrongDistributionItem(SchemaBase):
    """错题分布"""

    bank_id: int = Field(description='题库 ID')
    bank_name: str = Field(description='题库名称')
    wrong_count: int = Field(description='错题数量')
    percentage: float = Field(description='占比百分比')


class TodayPendingItem(SchemaBase):
    """今日待复盘错题"""

    model_config = ConfigDict(from_attributes=True)

    wrong_book_id: int = Field(description='错题本记录 ID')
    question_id: int = Field(description='题目 ID')
    stem: str | None = Field(None, description='题干摘要')
    bank_name: str | None = Field(None, description='题库名称')
    wrong_count: int = Field(description='错误次数')
    last_wrong_time: datetime | None = Field(None, description='最后错误时间')


class GetReviewDashboard(SchemaBase):
    """复盘看板数据"""

    total_wrong_count: int = Field(description='总错题数')
    unmastered_count: int = Field(description='未掌握数')
    total_review_count: int = Field(description='总复盘记录数')
    today_pending_count: int = Field(description='今日待复盘数')
    reason_distribution: list[ReasonDistributionItem] = Field(default_factory=list, description='错因分布')
    wrong_distribution: list[WrongDistributionItem] = Field(default_factory=list, description='错题分布')

