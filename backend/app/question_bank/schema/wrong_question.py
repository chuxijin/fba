#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime

from pydantic import ConfigDict, Field

from backend.common.schema import SchemaBase

# ===== 查询参数 =====


class WrongQuestionQueryParam(SchemaBase):
    """错题本查询参数"""

    is_mastered: bool | None = Field(None, description='是否已掌握')
    is_pinned: bool | None = Field(None, description='是否置顶')
    bank_id: int | None = Field(None, gt=0, description='题库 ID（通过挂载筛选）')
    chapter_id: int | None = Field(None, gt=0, description='章节 ID（通过挂载筛选）')
    keyword: str | None = Field(None, max_length=200, description='关键字搜索（搜索题干）')


# ===== 基础 =====


class WrongQuestionSchemaBase(SchemaBase):
    """错题本基础"""

    question_id: int = Field(gt=0, description='题目 ID')
    placement_id: int | None = Field(None, gt=0, description='挂载 ID')


# ===== 响应 =====


class GetWrongQuestionDetail(WrongQuestionSchemaBase):
    """错题详情"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='错题 ID')
    user_id: int = Field(description='用户 ID')
    wrong_count: int = Field(ge=0, description='错误次数')
    correct_streak: int = Field(ge=0, description='连续做对次数')
    first_wrong_time: datetime | None = Field(None, description='首次错误时间')
    last_wrong_time: datetime | None = Field(None, description='最后一次错误时间')
    last_practice_time: datetime | None = Field(None, description='最后一次练习时间')
    is_mastered: bool = Field(description='是否已掌握')
    mastered_time: datetime | None = Field(None, description='掌握时间')
    is_pinned: bool = Field(description='是否置顶')
    pinned_time: datetime | None = Field(None, description='置顶时间')
    created_time: datetime = Field(description='创建时间')
    updated_time: datetime | None = Field(None, description='更新时间')
    # 展示扩展字段（由服务层填充）
    question_stem: str | None = Field(None, description='题目题干')
    question_type: str | None = Field(None, description='题型')
    bank_id: int | None = Field(None, description='题库 ID')
    bank_name: str | None = Field(None, description='题库名称')
    chapter_id: int | None = Field(None, description='章节 ID')
    chapter_name: str | None = Field(None, description='章节名称')
    cat_id: int | None = Field(None, description='分类 ID')
    cat_name: str | None = Field(None, description='分类名称')


class GetWrongQuestionListItem(SchemaBase):
    """错题列表项"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='错题 ID')
    question_id: int = Field(description='题目 ID')
    placement_id: int | None = Field(None, description='挂载 ID')
    wrong_count: int = Field(ge=0, description='错误次数')
    correct_streak: int = Field(ge=0, description='连续做对次数')
    last_wrong_time: datetime | None = Field(None, description='最后一次错误时间')
    last_practice_time: datetime | None = Field(None, description='最后一次练习时间')
    is_mastered: bool = Field(description='是否已掌握')
    is_pinned: bool = Field(description='是否置顶')
    # 展示扩展字段（由服务层填充）
    question_stem: str | None = Field(None, description='题目题干')
    question_type: str | None = Field(None, description='题型')
    bank_id: int | None = Field(None, description='题库 ID')
    bank_name: str | None = Field(None, description='题库名称')
    chapter_id: int | None = Field(None, description='章节 ID')
    chapter_name: str | None = Field(None, description='章节名称')
    cat_id: int | None = Field(None, description='分类 ID')
    cat_name: str | None = Field(None, description='分类名称')


# ===== 操作参数 =====


class SetWrongQuestionPinParam(SchemaBase):
    """设置错题置顶参数"""

    wrong_id: int = Field(gt=0, description='错题 ID')
    is_pinned: bool = Field(description='是否置顶')


class BatchDeleteWrongQuestionsParam(SchemaBase):
    """批量删除错题参数"""

    wrong_ids: list[int] = Field(min_length=1, description='错题 ID 列表')


class WrongQuestionAnswerCorrectParam(SchemaBase):
    """错题答对上报参数"""

    mastery_threshold: int | None = Field(None, ge=1, le=20, description='连对掌握阈值（不传则读取学习偏好）')
    placement_id: int | None = Field(None, gt=0, description='挂载 ID')


# ===== 统计 =====


class WrongQuestionStatistics(SchemaBase):
    """错题本统计"""

    total_count: int = Field(ge=0, description='错题总数')
    mastered_count: int = Field(ge=0, description='已掌握数量')
    unmastered_count: int = Field(ge=0, description='未掌握数量')
    pinned_count: int = Field(ge=0, description='置顶数量')
    avg_wrong_count: float = Field(ge=0, description='平均错误次数')
    avg_correct_streak: float = Field(ge=0, description='平均连续做对次数')


class WrongQuestionProgressStatistics(SchemaBase):
    """错题本进度统计"""

    today_new_wrong: int = Field(ge=0, description='今日新增错题')
    today_mastered: int = Field(ge=0, description='今日掌握数量')
    recent_7d_wrong: int = Field(ge=0, description='近 7 天新增错题')
    recent_7d_mastered: int = Field(ge=0, description='近 7 天掌握数量')


# ===== 分组聚合 =====


class WrongQuestionGroupItem(SchemaBase):
    """分组聚合项"""

    group_id: int | None = Field(None, description='分组 ID（按题库时为 bank_id，按知识点时为 None）')
    group_name: str = Field(description='分组名称')
    count: int = Field(ge=0, description='错题数量')
