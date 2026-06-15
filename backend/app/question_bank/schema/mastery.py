#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime

from pydantic import ConfigDict, Field

from backend.common.schema import SchemaBase


class GetMasteryStatusItem(SchemaBase):
    """掌握状态项"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='ID')
    question_id: int | None = Field(None, description='题库题目 ID')
    custom_question_id: int | None = Field(None, description='自定义错题 ID')
    status: str = Field(description='状态: learning/mastered/forgotten')
    correct_streak: int = Field(description='连续答对次数')
    review_count: int = Field(description='复盘次数')
    last_practice_time: datetime | None = Field(None, description='最后练习时间')
    last_review_time: datetime | None = Field(None, description='最后复盘时间')
    mastered_time: datetime | None = Field(None, description='掌握时间')
    next_review_time: datetime | None = Field(None, description='下次复习时间')


class GetMasteryStatsResponse(SchemaBase):
    """掌握状态统计响应"""

    learning: int = Field(description='未掌握题目数')
    mastered: int = Field(description='已掌握题目数')
    forgotten: int = Field(description='遗忘题目数')
    total: int = Field(description='总题目数')


class GetForgottenItem(SchemaBase):
    """遗忘题目项"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='掌握状态 ID')
    question_id: int | None = Field(None, description='题库题目 ID')
    custom_question_id: int | None = Field(None, description='自定义错题 ID')
    correct_streak: int = Field(description='连续答对次数')
    last_practice_time: datetime | None = Field(None, description='最后练习时间')
    next_review_time: datetime | None = Field(None, description='下次复习时间')
