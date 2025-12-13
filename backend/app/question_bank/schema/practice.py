#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
练习相关 Schema

包含：
- PracticeSession（练习会话）- PracticeRecord（答题记录）
- 统计相关
"""
from datetime import datetime
from decimal import Decimal

from pydantic import ConfigDict, Field

from backend.common.schema import SchemaBase


# ============ 练习会话 Schema ============


class PracticeSessionSchemaBase(SchemaBase):
    """练习会话基础 Schema"""

    session_type: str = Field(description='练习类型: chapter/bank/random/exam/wrong/favorite')
    bank_id: int | None = Field(None, description='题库 ID')
    chapter_id: int | None = Field(None, description='章节 ID')
    question_ids: list[int] | None = Field(None, description='题目 ID 列表')
    total_count: int = Field(description='题目总数')
    exam_config: dict | None = Field(None, description='考试配置（考试模式时使用）')


class CreatePracticeSessionParam(PracticeSessionSchemaBase):
    """创建练习会话参数"""

    pass


class GetPracticeSessionDetail(PracticeSessionSchemaBase):
    """练习会话详情"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='会话 ID')
    user_id: int = Field(description='用户 ID')
    completed_count: int = Field(description='已完成数量')
    correct_count: int = Field(description='答对数量')
    wrong_count: int = Field(description='答错数量')
    accuracy_rate: Decimal = Field(description='正确率（%）')
    score: Decimal | None = Field(None, description='得分')
    total_score: Decimal | None = Field(None, description='总分')
    total_time: int = Field(description='总用时（秒）')
    start_time: datetime = Field(description='开始时间')
    submit_time: datetime | None = Field(None, description='提交时间')
    status: str = Field(description='状态: in_progress/completed/abandoned')
    created_time: datetime = Field(description='创建时间')


class GetPracticeSessionListItem(SchemaBase):
    """练习会话列表项"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='会话 ID')
    session_type: str = Field(description='练习类型')
    bank_id: int | None = Field(None, description='题库 ID')
    practice_name: str | None = Field(None, description='练习名称')
    total_count: int = Field(description='题目总数')
    completed_count: int = Field(description='已完成数量')
    correct_count: int = Field(description='答对数量')
    wrong_count: int = Field(description='答错数量')
    accuracy_rate: Decimal = Field(description='正确率（%）')
    total_time: int = Field(description='总用时（秒）')
    status: str = Field(description='状态')
    start_time: datetime = Field(description='开始时间')
    updated_time: datetime = Field(description='更新时间')


class UpdatePracticeSessionParam(SchemaBase):
    """更新练习会话参数"""

    completed_count: int | None = Field(None, description='已完成数量')
    correct_count: int | None = Field(None, description='答对数量')
    wrong_count: int | None = Field(None, description='答错数量')
    total_time: int | None = Field(None, description='总用时（秒）')


class SubmitPracticeSessionParam(SchemaBase):
    """提交练习会话参数"""

    score: Decimal | None = Field(None, description='得分（考试模式）')


# ============ 答题记录 Schema ============


class PracticeRecordSchemaBase(SchemaBase):
    """答题记录基础 Schema"""

    question_id: int = Field(description='题目 ID')
    user_answer: str | list[str] = Field(description='用户答案')
    is_correct: bool = Field(description='是否正确')
    answer_time: int = Field(description='本题用时（秒）')


class CreatePracticeRecordParam(PracticeRecordSchemaBase):
    """创建答题记录参数"""

    session_id: int = Field(description='会话 ID')
    bank_id: int = Field(description='题库 ID')
    chapter_id: int | None = Field(None, description='章节 ID')


class BatchCreatePracticeRecordsParam(SchemaBase):
    """批量创建答题记录参数"""

    session_id: int = Field(description='会话 ID')
    records: list[PracticeRecordSchemaBase] = Field(description='答题记录列表')


class GetPracticeRecordDetail(PracticeRecordSchemaBase):
    """答题记录详情"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='记录 ID')
    user_id: int = Field(description='用户 ID')
    session_id: int = Field(description='会话 ID')
    bank_id: int = Field(description='题库 ID')
    chapter_id: int | None = Field(None, description='章节 ID')
    created_time: datetime = Field(description='答题时间')


class GetPracticeRecordListItem(SchemaBase):
    """答题记录列表项"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='记录 ID')
    question_id: int = Field(description='题目 ID')
    is_correct: bool = Field(description='是否正确')
    answer_time: int = Field(description='用时（秒）')
    created_time: datetime = Field(description='答题时间')


# ============ 统计 Schema ============


class UserPracticeStatistics(SchemaBase):
    """用户练习统计"""

    total_sessions: int = Field(description='总会话数')
    completed_sessions: int = Field(description='已完成会话数')
    total_questions: int = Field(description='总做题数')
    correct_count: int = Field(description='答对数')
    wrong_count: int = Field(description='答错数')
    accuracy_rate: Decimal = Field(description='总正确率（%）')
    total_time: int = Field(description='总学习时长（秒）')
    avg_answer_time: Decimal = Field(description='平均答题时间（秒）')


class DailyPracticeStatistics(SchemaBase):
    """每日练习统计"""

    date: str = Field(description='日期 YYYY-MM-DD')
    question_count: int = Field(description='做题数')
    correct_count: int = Field(description='答对数')
    accuracy_rate: Decimal = Field(description='正确率（%）')
    study_time: int = Field(description='学习时长（秒）')


class QuestionTypeStatistics(SchemaBase):
    """题型统计"""

    type: str = Field(description='题型')
    count: int = Field(description='做题数')
    correct_count: int = Field(description='答对数')
    accuracy_rate: Decimal = Field(description='正确率（%）')


# ============ 结算页面数据 Schema ============


class AnswerCardItem(SchemaBase):
    """答题卡项"""

    index: int = Field(description='题目序号（从 0 开始）')
    question_id: int = Field(description='题目 ID')
    status: str = Field(description='状态: correct/wrong/unanswered')


class SessionSummaryData(SchemaBase):
    """练习会话结算数据"""

    # 会话基本信息
    session_id: int = Field(description='会话 ID')
    bank_id: int | None = Field(None, description='题库 ID')
    practice_name: str | None = Field(None, description='练习名称')
    session_type: str = Field(description='练习类型')

    # 统计数据
    total_count: int = Field(description='题目总数')
    completed_count: int = Field(description='已完成数量')
    correct_count: int = Field(description='答对数量')
    wrong_count: int = Field(description='答错数量')
    unanswered_count: int = Field(description='未答题数')
    accuracy_rate: Decimal = Field(description='正确率（%）')
    total_time: int = Field(description='总用时（秒）')
    status: str = Field(description='状态')

    # 答题卡数据
    answer_items: list[AnswerCardItem] = Field(description='答题卡列表')

    # 错题 ID 列表（用于"仅看错题"功能）
    wrong_question_ids: list[int] = Field(description='错题 ID 列表')
