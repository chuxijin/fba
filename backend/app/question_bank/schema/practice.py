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
    bank_id: int | None = Field(None, description='题库 ID（考试模式时作为试卷 ID）')
    chapter_id: int | None = Field(None, description='章节 ID')
    question_ids: list[int] | None = Field(None, description='题目 ID 列表（可选，不传则根据 chapter_id/bank_id 自动获取）')
    total_count: int | None = Field(None, description='题目总数（可选，后端自动计算）')
    limit: int | None = Field(None, description='题目数量限制（用于随机出题，不传或传 0 表示全部）')
    shuffle: bool = Field(False, description='是否随机顺序（默认 False 按原顺序）')
    exam_config: dict | None = Field(None, description='考试配置（考试模式时使用）')


class CreatePracticeSessionParam(PracticeSessionSchemaBase):
    """创建练习会话参数"""

    pass


from backend.app.question_bank.schema.question import GetQuestionListItem


class UserAnswerItem(SchemaBase):
    """用户答案项"""

    question_id: int = Field(description='题目 ID')
    user_answer: str | list[str] = Field(description='用户答案')
    answer_time: int = Field(default=0, description='答题用时（秒）')


class GetPracticeSessionDetail(PracticeSessionSchemaBase):
    """练习会话详情"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='会话 ID')
    user_id: int = Field(description='用户 ID')
    practice_name: str | None = Field(None, description='练习名称')
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
    questions: list[GetQuestionListItem] | None = Field(None, description='题目列表（创建/获取时返回）')
    user_answers: dict[int, UserAnswerItem] | None = Field(None, description='用户答案（question_id -> 答案详情）')


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
    updated_time: datetime | None = Field(None, description='更新时间')


class UpdatePracticeSessionParam(SchemaBase):
    """更新练习会话参数"""

    completed_count: int | None = Field(None, description='已完成数量')
    correct_count: int | None = Field(None, description='答对数量')
    wrong_count: int | None = Field(None, description='答错数量')
    total_time: int | None = Field(None, description='总用时（秒）')


class SubmitPracticeSessionParam(SchemaBase):
    """提交练习会话参数"""

    total_time: int = Field(description='总用时（秒）')


# ============ 答题记录 Schema ============


class PracticeRecordSchemaBase(SchemaBase):
    """答题记录基础 Schema"""

    question_id: int = Field(description='题目 ID')
    user_answer: str | list[str] = Field(description='用户答案')
    is_correct: bool | None = Field(None, description='是否正确（提交时由后端判题）')
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

    index: int = Field(description='题目序号（从 1 开始）')
    question_id: int = Field(description='题目 ID')
    status: str = Field(description='状态: correct/wrong/unanswered')
    answer_time: int = Field(default=0, description='答题用时（秒）')


class SessionReport(SchemaBase):
    """会话答题报告"""

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


class QuestionSolution(SchemaBase):
    """题目解析项"""

    question_id: int = Field(description='题目 ID')
    content: str = Field(description='题干')
    type: str = Field(description='题型')
    options: list[dict] | None = Field(None, description='选项列表')
    correct_answer: str | list[str] = Field(description='正确答案')
    analysis: str | None = Field(None, description='解析')
    user_answer: str | list[str] | None = Field(None, description='用户答案')
    is_correct: bool | None = Field(None, description='是否正确')
    answer_time: int = Field(default=0, description='答题用时（秒）')


class SessionSolution(SchemaBase):
    """会话答案解析"""

    session_id: int = Field(description='会话 ID')
    questions: list[QuestionSolution] = Field(description='题目解析列表')


# ============ 学习统计 Schema ============


class ChapterStatistics(SchemaBase):
    """章节学习统计"""

    chapter_id: int = Field(description='章节 ID')
    chapter_name: str = Field(description='章节名称')
    total_questions: int = Field(description='总题数')
    practiced_count: int = Field(description='已练习题数（去重）')
    correct_count: int = Field(description='答对题数')
    accuracy_rate: Decimal = Field(description='正确率（%）')


class BankStatistics(SchemaBase):
    """题库学习统计"""

    bank_id: int = Field(description='题库 ID')
    total_questions: int = Field(description='总题数')
    practiced_count: int = Field(description='已练习题数（去重）')
    correct_count: int = Field(description='答对题数')
    accuracy_rate: Decimal = Field(description='正确率（%）')
    total_time: int = Field(description='总练习时长（秒）')
    chapter_statistics: list[ChapterStatistics] = Field(description='章节统计列表')


# ============ 用户学习统计（练习中心用）============


class ChapterProgressItem(SchemaBase):
    """章节学习进度项"""

    chapter_id: int = Field(description='章节 ID')
    chapter_name: str = Field(description='章节名称')
    total_count: int = Field(description='章节总题数')
    practiced_count: int = Field(description='已练习题数（包含未判题）')
    completed_count: int = Field(description='已判题题数（is_correct 不为空）')
    correct_count: int = Field(description='答对题数')
    accuracy_rate: Decimal = Field(description='正确率（%，基于已判题题目）')


class BankProgressItem(SchemaBase):
    """题库学习进度项"""

    bank_id: int = Field(description='题库 ID')
    practiced_count: int = Field(description='已练习题数（包含未判题，去重）')
    completed_count: int = Field(description='已判题题数（is_correct 不为空，去重）')
    total_count: int = Field(description='题库总题数')
    correct_count: int = Field(description='答对题数')
    accuracy_rate: Decimal = Field(description='正确率（%，基于已判题题目）')
    total_time: int = Field(description='累计学习时长（秒）')
    in_progress_session_id: int | None = Field(None, description='未完成会话ID')
    in_progress_count: int = Field(0, description='未完成会话已做题数')
    chapters: list[ChapterProgressItem] = Field(default_factory=list, description='章节学习进度')


class UserStatisticsSummary(SchemaBase):
    """用户学习汇总"""

    total_practiced: int = Field(description='总练习题数')
    total_correct: int = Field(description='总答对数')
    total_time: int = Field(description='总学习时长（秒）')
    bank_count: int = Field(description='学习过的题库数')


class UserStatistics(SchemaBase):
    """用户学习统计"""

    banks: list[BankProgressItem] = Field(description='各题库学习进度')
    summary: UserStatisticsSummary = Field(description='汇总数据')
