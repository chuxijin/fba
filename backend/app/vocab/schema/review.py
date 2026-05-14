#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime

from pydantic import ConfigDict, Field

from backend.app.vocab.schema.word import GetWordBrief, GetWordDetail
from backend.common.schema import SchemaBase


class SubmitReviewParam(SchemaBase):
    """提交复习结果参数"""

    word_id: int = Field(description='单词 ID')
    rating: int = Field(ge=1, le=4, description='评分(1 Again 2 Hard 3 Good 4 Easy)')
    review_mode: str = Field(max_length=20, description='学习模式')
    duration_ms: int = Field(ge=0, description='本次耗时(毫秒)')


class CreateReviewLogParam(SchemaBase):
    """创建复习日志参数"""

    user_id: int = Field(description='用户 ID')
    word_id: int = Field(description='单词 ID')
    rating: int = Field(description='评分')
    state: int = Field(description='复习时卡片状态')
    review_mode: str = Field(description='学习模式')
    duration_ms: int = Field(description='耗时(毫秒)')
    reviewed_at: datetime = Field(description='复习时间')


class GetReviewLogDetail(SchemaBase):
    """复习日志详情"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='日志 ID')
    user_id: int = Field(description='用户 ID')
    word_id: int = Field(description='单词 ID')
    rating: int = Field(description='评分')
    state: int = Field(description='复习时卡片状态')
    review_mode: str = Field(description='学习模式')
    duration_ms: int | None = Field(None, description='耗时(毫秒)')
    reviewed_at: datetime = Field(description='复习时间')


class StudySessionWord(SchemaBase):
    """学习会话中的单词"""

    word: GetWordDetail = Field(description='单词详情')
    is_new: bool = Field(description='是否新词')
    user_word_id: int | None = Field(None, description='用户单词状态 ID(已学过时有值)')


class GetStudySession(SchemaBase):
    """学习会话"""

    words: list[StudySessionWord] = Field(default=[], description='本次学习的单词列表')
    new_count: int = Field(default=0, description='新词数')
    review_count: int = Field(default=0, description='复习词数')
    total: int = Field(default=0, description='总数')


class GetStudyStats(SchemaBase):
    """学习统计"""

    total_learned: int = Field(default=0, description='已学总词数')
    total_mastered: int = Field(default=0, description='已掌握词数(review 状态)')
    total_learning: int = Field(default=0, description='学习中词数')
    today_new: int = Field(default=0, description='今日新学')
    today_review: int = Field(default=0, description='今日复习')
    today_duration_seconds: int = Field(default=0, description='今日学习时长(秒)')
    due_count: int = Field(default=0, description='待复习词数')


class ReviewResult(SchemaBase):
    """复习结果"""

    next_due: datetime = Field(description='下次到期时间')
    new_state: int = Field(description='更新后的状态')
    stability: float | None = Field(None, description='更新后的稳定性')
    difficulty: float | None = Field(None, description='更新后的难度')


class ReviewForecast(SchemaBase):
    """复习预测"""

    again: datetime = Field(description='选 Again 后下次复习时间')
    hard: datetime = Field(description='选 Hard 后下次复习时间')
    good: datetime = Field(description='选 Good 后下次复习时间')
    easy: datetime = Field(description='选 Easy 后下次复习时间')
