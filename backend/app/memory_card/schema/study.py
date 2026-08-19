#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime
from typing import Any, Literal

from pydantic import Field

from backend.common.schema import SchemaBase

MemoryCheckResult = Literal['correct', 'wrong', 'undetermined']
MemoryPlayMode = Literal['input', 'reveal', 'choice', 'correction']


class GetMemoryDeckItem(SchemaBase):
    """用户视角卡组项"""

    id: int = Field(description='卡组 ID')
    name: str = Field(description='卡组名称')
    description: str | None = Field(None, description='卡组描述')
    scope: str = Field(description='system/personal')
    status: str = Field(description='卡组状态')
    card_count: int = Field(default=0, description='卡组内卡片数')
    subscribed: bool = Field(default=False, description='当前用户是否已订阅')
    daily_new_limit: int = Field(description='每日新卡上限')
    daily_review_limit: int = Field(description='每日复习上限')


class GetMemoryOverview(SchemaBase):
    """记忆学习概览"""

    due_count: int = Field(description='待复习卡数')
    new_count: int = Field(description='今日可学新卡数')
    today_new: int = Field(description='今日已学新卡')
    today_reviewed: int = Field(description='今日已复习')
    total_learning: int = Field(description='学习中（FSRS learning/relearning）')
    total_reviewing: int = Field(description='已进入长期复习')
    total_cards: int = Field(description='已加入学习的卡总数')
    forecast: list[dict[str, Any]] = Field(default_factory=list, description='未来 7 天到期预测')
    decks: list[GetMemoryDeckItem] = Field(default_factory=list, description='可学习卡组')


class StudySegmentItem(SchemaBase):
    """学习用素材片段（不含正确答案）。"""

    type: Literal['text', 'point'] = Field(description='text 普通文本 / point 记忆点')
    id: str | None = Field(None, description='记忆点 ID')
    text: str = Field(default='', description='文本内容；纠错模式下 point 为当前展示内容')
    options: list[str] = Field(default_factory=list, description='选择模式选项')


class StudyContent(SchemaBase):
    """指定玩法的学习内容（不含正确答案）。"""

    mode: MemoryPlayMode = Field(description='本次玩法')
    segments: list[StudySegmentItem] = Field(default_factory=list, description='素材片段')
    correction_case: Literal['correct', 'wrong'] | None = Field(None, description='纠错题当前展示的句子类型')


class GetStudyQueueItem(SchemaBase):
    """学习队列项"""

    card_id: int = Field(description='卡片 ID')
    deck_id: int = Field(description='卡组 ID')
    deck_name: str | None = Field(None, description='卡组名称')
    title: str = Field(description='卡片标题')
    card_type: str = Field(description='记忆玩法')
    response_mode: str = Field(description='作答交互')
    default_mode: MemoryPlayMode = Field(default='input', description='默认学习玩法')
    available_modes: list[MemoryPlayMode] = Field(default_factory=list, description='素材支持的玩法')
    content: StudyContent = Field(description='学习内容')
    play_contents: dict[str, StudyContent] = Field(default_factory=dict, description='各玩法学习内容')
    is_new: bool = Field(description='是否新卡')
    state: int = Field(description='FSRS 状态')
    stability: float | None = Field(None, description='FSRS 稳定性')
    difficulty: float | None = Field(None, description='FSRS 难度')
    retrievability: float = Field(default=0, description='当前回忆概率')
    due: datetime | None = Field(None, description='到期时间')


class GetStudyQueue(SchemaBase):
    """学习队列"""

    cards: list[GetStudyQueueItem] = Field(default_factory=list, description='队列卡片')
    due_count: int = Field(default=0, description='本队待复习数')
    new_count: int = Field(default=0, description='本队新卡数')
    total: int = Field(default=0, description='总数')


class CheckMemoryCardParam(SchemaBase):
    """判定答案参数"""

    response_data: Any | None = Field(
        None,
        description='输入/选择为 {point_id: value}；纠错为 {case, action, point_ids}',
    )
    play_mode: MemoryPlayMode = Field(default='input', description='本次学习玩法')
    revealed: bool = Field(default=False, description='是否已揭晓答案')
    duration_ms: int = Field(default=0, ge=0, le=86_400_000, description='用时毫秒')


class CheckBlankResult(SchemaBase):
    """单空位判定结果"""

    blank_id: str = Field(description='空位标识')
    user_answer: Any | None = Field(None, description='用户作答')
    correct: bool | None = Field(None, description='是否正确')
    correct_answer: Any | None = Field(None, description='正确答案')


class CheckMemoryCardResult(SchemaBase):
    """判定结果"""

    card_id: int = Field(description='卡片 ID')
    check_result: MemoryCheckResult = Field(description='整体判定')
    blanks: list[CheckBlankResult] = Field(default_factory=list, description='逐空判定')
    correct_template: str | None = Field(None, description='纠错正确版本')
    hints: list[dict[str, Any]] = Field(default_factory=list, description='提示')
    forecast: dict[str, datetime | None] | None = Field(None, description='四档评分下次复习时间')
    recommended_rating: int | None = Field(None, description='推荐评分 1-4')


class SubmitMemoryReviewParam(SchemaBase):
    """提交评分并推进 FSRS 调度参数"""

    card_id: int = Field(gt=0, description='卡片 ID')
    play_mode: MemoryPlayMode = Field(default='input', description='本次学习玩法')
    rating: int = Field(ge=1, le=4, description='评分(1 Again 2 Hard 3 Good 4 Easy)')
    idempotency_key: str = Field(min_length=8, max_length=128, description='客户端幂等键')
    session_key: str | None = Field(None, min_length=1, max_length=64, description='学习会话标识')
    response_data: Any | None = Field(None, description='作答数据快照')
    check_result: MemoryCheckResult = Field(default='undetermined', description='客观判定')
    revealed: bool = Field(default=False, description='是否先揭晓')
    duration_ms: int = Field(default=0, ge=0, le=86_400_000, description='用时毫秒')


class SubmitMemoryReviewResult(SchemaBase):
    """评分调度结果"""

    review_log_id: int = Field(description='日志 ID')
    card_id: int = Field(description='卡片 ID')
    next_due: datetime = Field(description='下次复习时间')
    new_state: int = Field(description='新 FSRS 状态')
    stability: float | None = Field(None, description='稳定性')
    difficulty: float | None = Field(None, description='难度')


class GetMemoryForecast(SchemaBase):
    """到期预测"""

    days: list[dict[str, Any]] = Field(default_factory=list, description='每日到期卡数')


class GetMemoryCurve(SchemaBase):
    """单卡记忆曲线"""

    card_id: int = Field(description='卡片 ID')
    title: str = Field(description='卡片标题')
    stability: float | None = Field(None, description='稳定性')
    difficulty: float | None = Field(None, description='难度')
    retrievability: float = Field(default=0, description='当前回忆概率')
    due: datetime | None = Field(None, description='到期时间')
    points: list[dict[str, Any]] = Field(default_factory=list, description='曲线采样点')
