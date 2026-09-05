#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from pydantic import Field

from backend.common.fsrs import ReviewForecast as ReviewForecast, ReviewResult as ReviewResult
from backend.common.schema import SchemaBase


class SubmitReviewParam(SchemaBase):
    """提交复习参数"""

    hanyu_id: int = Field(..., description='汉语词汇 ID')
    rating: int = Field(..., ge=1, le=4, description='评分(1 Again 2 Hard 3 Good 4 Easy)')
    review_mode: str = Field('word', description='学习模式')
    duration_ms: int | None = Field(None, description='耗时(毫秒)')


class HanyuGroupItemOut(SchemaBase):
    """辨析组成员明细"""

    hanyu_id: int | None = Field(None, description='词汇 ID')
    word: str = Field(description='词语')
    emphasis: str | None = Field(None, description='对比侧重点/释义')
    collocation: str | None = Field(None, description='常见搭配/考频')
    is_current: bool = Field(False, description='是否为当前卡片背诵词')


class HanyuGroupOut(SchemaBase):
    """汉语辨析组详情"""

    id: int = Field(description='辨析组 ID')
    title: str = Field(description='辨析组标题')
    group_no: str | None = Field(None, description='题号/序号')
    category: str = Field(description='分类')
    summary: str | None = Field(None, description='整组解析概要')
    items: list[HanyuGroupItemOut] = Field(default=[], description='组内对比词条')


class StudySessionWord(SchemaBase):
    """学习会话中的词语"""

    hanyu_id: int = Field(description='词语 ID')
    word: str = Field(description='词语')
    pinyin: str | None = Field(None, description='拼音')
    type: str | None = Field(None, description='类型')
    meaning: str | None = Field(None, description='释义')
    commentary: str | None = Field(None, description='讲解/备注')
    example: str | None = Field(None, description='例句')
    definition_info: dict | None = Field(None, description='定义信息')
    detail_means: dict | None = Field(None, description='详细含义')
    voice: str | None = Field(None, description='语音 URL')
    state: int | None = Field(None, description='FSRS 状态')
    stability: float | None = Field(None, description='FSRS 稳定性')
    difficulty: float | None = Field(None, description='FSRS 难度')
    is_new: bool = Field(description='是否新词')
    is_starred: bool = Field(False, description='是否收藏')
    bianxi_groups: list[HanyuGroupOut] = Field(default=[], description='关联的近义辨析对比组')



class GetStudySession(SchemaBase):
    """学习会话"""

    words: list[StudySessionWord] = Field(default=[], description='本次学习的词语列表')
    new_count: int = Field(default=0, description='新词数')
    review_count: int = Field(default=0, description='复习词数')
    total: int = Field(default=0, description='总数')


class HanyuBookProgress(SchemaBase):
    """词语本学习进度"""

    book_id: int = Field(description='词语本 ID')
    book_name: str = Field(description='词语本名称')
    book_cover: str | None = Field(None, description='封面图')
    total_words: int = Field(0, description='词语总数')
    learned_words: int = Field(0, description='已学词语数')


class GetStudyStats(SchemaBase):
    """学习统计"""

    total_learned: int = Field(default=0, description='已学总词数')
    total_mastered: int = Field(default=0, description='已掌握词数(review 状态)')
    total_learning: int = Field(default=0, description='学习中词数')
    today_new: int = Field(default=0, description='今日新学')
    today_review: int = Field(default=0, description='今日复习')
    today_duration_seconds: int = Field(default=0, description='今日学习时长(秒)')
    due_count: int = Field(default=0, description='待复习词数')
    active_book: HanyuBookProgress | None = Field(None, description='当前在学的词语本')
