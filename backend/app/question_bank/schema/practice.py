#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import ConfigDict, Field

from backend.common.schema import SchemaBase


# ===== enums =====
SessionType = Literal['chapter', 'bank', 'random', 'exam', 'wrong', 'favorite']
SessionStatus = Literal['in_progress', 'completed', 'abandoned']
QuestionType = Literal['single', 'multiple', 'judgement', 'fill', 'shortAnswer']
AnswerCardStatus = Literal['correct', 'wrong', 'unanswered']


# ===== session create / query =====
class CreatePracticeSessionParam(SchemaBase):
    """创建练习会话参数"""

    session_type: SessionType = Field(description='会话类型')
    practice_name: str | None = Field(None, max_length=255, description='会话名称')
    bank_id: int | None = Field(None, gt=0, description='题库 ID（筛题上下文）')
    chapter_id: int | None = Field(None, gt=0, description='章节 ID（筛题上下文）')
    placement_ids: list[int] | None = Field(None, min_length=1, max_length=2000, description='指定挂载 ID 列表')
    limit: int | None = Field(None, ge=1, le=500, description='抽题数量上限')
    shuffle: bool = Field(False, description='是否打乱题序')
    exam_config: dict[str, Any] | None = Field(None, description='考试配置')


class PracticeSessionQueryParam(SchemaBase):
    """会话列表查询参数"""

    session_type: SessionType | None = Field(None, description='会话类型')
    status: SessionStatus | None = Field(None, description='会话状态')
    bank_id: int | None = Field(None, gt=0, description='题库 ID')
    chapter_id: int | None = Field(None, gt=0, description='章节 ID')


# ===== session question snapshot =====
class SessionQuestionItem(SchemaBase):
    """会话题目快照"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='会话题目明细 ID')
    session_id: int = Field(description='会话 ID')
    seq_no: int = Field(ge=1, description='题序')
    question_id: int = Field(description='题目 ID')
    placement_id: int = Field(description='挂载 ID')
    question_type: QuestionType = Field(description='题型')
    full_score: Decimal = Field(ge=Decimal('0'), description='满分')


# ===== practice record =====
class UpsertPracticeRecordItem(SchemaBase):
    """单题作答提交项"""

    seq_no: int = Field(ge=1, description='题序')
    question_id: int = Field(gt=0, description='题目 ID')
    placement_id: int = Field(gt=0, description='挂载 ID')
    user_answer: dict[str, Any] | list[Any] | str = Field(description='用户答案（JSON 兼容）')
    answer_time: int = Field(ge=0, le=7200, description='本题耗时（秒）')


class BatchUpsertPracticeRecordsParam(SchemaBase):
    """批量提交/更新作答记录"""

    session_id: int = Field(gt=0, description='会话 ID')
    records: list[UpsertPracticeRecordItem] = Field(min_length=1, max_length=500, description='作答记录列表')
    judge_now: bool = Field(default=False, description='是否立即判题')


class GetPracticeRecordDetail(SchemaBase):
    """作答记录详情"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='记录 ID')
    session_id: int = Field(description='会话 ID')
    user_id: int = Field(description='用户 ID')
    seq_no: int = Field(description='题序')
    question_id: int = Field(description='题目 ID')
    placement_id: int = Field(description='挂载 ID')
    user_answer: dict[str, Any] | list[Any] | str = Field(description='用户答案')
    is_correct: bool | None = Field(None, description='是否正确')
    score: Decimal | None = Field(None, ge=Decimal('0'), description='得分')
    full_score: Decimal = Field(ge=Decimal('0'), description='满分')
    answer_time: int = Field(ge=0, description='耗时（秒）')
    judged_at: datetime | None = Field(None, description='判题时间')
    judge_version: str | None = Field(None, max_length=32, description='判题规则版本')
    created_time: datetime = Field(description='创建时间')
    updated_time: datetime | None = Field(None, description='更新时间')


class GetPracticeRecordListItem(SchemaBase):
    """作答记录列表项"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='记录 ID')
    session_id: int = Field(description='会话 ID')
    seq_no: int = Field(description='题序')
    question_id: int = Field(description='题目 ID')
    placement_id: int = Field(description='挂载 ID')
    is_correct: bool | None = Field(None, description='是否正确')
    score: Decimal | None = Field(None, ge=Decimal('0'), description='得分')
    full_score: Decimal = Field(ge=Decimal('0'), description='满分')
    answer_time: int = Field(ge=0, description='耗时（秒）')
    created_time: datetime = Field(description='创建时间')


# ===== session read / submit =====
class GetPracticeSessionListItem(SchemaBase):
    """练习会话列表项"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='会话 ID')
    user_id: int = Field(description='用户 ID')
    session_type: SessionType = Field(description='会话类型')
    status: SessionStatus = Field(description='会话状态')
    bank_id: int | None = Field(None, description='题库 ID')
    chapter_id: int | None = Field(None, description='章节 ID')
    practice_name: str | None = Field(None, description='会话名称')
    total_count: int = Field(ge=0, description='总题数')
    completed_count: int = Field(ge=0, description='已完成数')
    correct_count: int = Field(ge=0, description='答对数')
    wrong_count: int = Field(ge=0, description='答错数')
    accuracy_rate: Decimal = Field(ge=Decimal('0'), le=Decimal('100'), description='正确率（%）')
    score: Decimal | None = Field(None, ge=Decimal('0'), description='总得分')
    total_score: Decimal | None = Field(None, ge=Decimal('0'), description='总满分')
    total_time: int = Field(ge=0, description='总耗时（秒）')
    start_time: datetime = Field(description='开始时间')
    submit_time: datetime | None = Field(None, description='提交时间')
    updated_time: datetime | None = Field(None, description='更新时间')


class GetPracticeSessionDetail(GetPracticeSessionListItem):
    """练习会话详情"""

    session_questions: list[SessionQuestionItem] = Field(default_factory=list, description='会话题目快照')
    records: list[GetPracticeRecordListItem] = Field(default_factory=list, description='作答记录列表')


class SubmitPracticeSessionParam(SchemaBase):
    """提交会话参数"""

    total_time: int = Field(ge=0, description='总耗时（秒）')
    judge_version: str | None = Field(None, max_length=32, description='判题规则版本')


class SubmitPracticeSessionResult(SchemaBase):
    """提交会话结果"""

    completed_count: int = Field(ge=0, description='已完成题数')
    correct_count: int = Field(ge=0, description='答对题数')
    wrong_count: int = Field(ge=0, description='答错题数')
    accuracy_rate: Decimal = Field(ge=Decimal('0'), le=Decimal('100'), description='正确率（%）')
    score: Decimal | None = Field(None, ge=Decimal('0'), description='总得分')
    total_score: Decimal | None = Field(None, ge=Decimal('0'), description='总满分')


# ===== settlement/report =====
class AnswerCardItem(SchemaBase):
    """答题卡项"""

    seq_no: int = Field(ge=1, description='题序')
    question_id: int = Field(description='题目 ID')
    placement_id: int = Field(description='挂载 ID')
    status: AnswerCardStatus = Field(description='作答状态')
    answer_time: int = Field(ge=0, description='耗时（秒）')


class SessionReport(SchemaBase):
    """会话报告"""

    session_id: int = Field(description='会话 ID')
    session_type: SessionType = Field(description='会话类型')
    status: SessionStatus = Field(description='会话状态')
    bank_id: int | None = Field(None, description='题库 ID')
    chapter_id: int | None = Field(None, description='章节 ID')
    total_count: int = Field(ge=0, description='总题数')
    completed_count: int = Field(ge=0, description='已完成数')
    correct_count: int = Field(ge=0, description='答对数')
    wrong_count: int = Field(ge=0, description='答错数')
    unanswered_count: int = Field(ge=0, description='未作答数')
    accuracy_rate: Decimal = Field(ge=Decimal('0'), le=Decimal('100'), description='正确率（%）')
    total_time: int = Field(ge=0, description='总耗时（秒）')
    answer_items: list[AnswerCardItem] = Field(default_factory=list, description='答题卡')
    wrong_question_ids: list[int] = Field(default_factory=list, description='错题 question_id 列表')


# ===== 答题提交（从 question.py 迁移的练习域 Schema） =====


class QuestionAnswerItem(SchemaBase):
    """题目答案项"""

    question_id: int = Field(gt=0, description='题目 ID')
    user_answer: str | list[str] = Field(description='用户答案')
    answer_time: Decimal | None = Field(None, ge=Decimal('0'), description='答题时间（秒）')


class BatchSubmitAnswerParam(SchemaBase):
    """批量提交答案参数"""

    answers: list[QuestionAnswerItem] = Field(min_length=1, description='答案列表')
    bank_id: int | None = Field(None, gt=0, description='题库 ID（用于定位挂载）')
    chapter_id: int | None = Field(None, gt=0, description='章节 ID（用于定位挂载）')
    include_analysis: bool = Field(default=False, description='是否包含解析内容')


class QuestionResultItem(SchemaBase):
    """题目结果项"""

    question_id: int = Field(description='题目 ID')
    is_correct: bool = Field(description='是否正确')
    user_answer: str | list[str] = Field(description='用户答案')
    correct_answer: dict[str, Any] = Field(description='正确答案')
    score: Decimal = Field(ge=Decimal('0'), description='得分')
    full_score: Decimal = Field(ge=Decimal('0'), description='满分')
    analysis_content: str | None = Field(None, description='解析内容')


class BatchSubmitAnswerResult(SchemaBase):
    """批量提交答案结果"""

    total_questions: int = Field(ge=0, description='总题目数')
    correct_count: int = Field(ge=0, description='答对题目数')
    wrong_count: int = Field(ge=0, description='答错题目数')
    total_score: Decimal = Field(ge=Decimal('0'), description='总得分')
    full_score: Decimal = Field(ge=Decimal('0'), description='总满分')
    accuracy_rate: Decimal = Field(ge=Decimal('0'), le=Decimal('100'), description='正确率（%）')
    score_rate: Decimal = Field(ge=Decimal('0'), le=Decimal('100'), description='得分率（%）')
    results: list[QuestionResultItem] = Field(default_factory=list, description='每题结果详情')


class GetQuestionSolution(SchemaBase):
    """题目答案和解析"""

    model_config = ConfigDict(from_attributes=True)

    correct_answer: str | list[str] = Field(description='正确答案')
    analysis: str = Field(description='解析内容')
    is_correct: bool | None = Field(None, description='是否正确')
    correct_rate: Decimal = Field(
        default=Decimal('0'), ge=Decimal('0'), le=Decimal('100'), description='全站正确率（%）'
    )
    wrong_option_stats: dict[str, Any] | None = Field(None, description='错误选项统计')
