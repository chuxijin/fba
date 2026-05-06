#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import ConfigDict, Field

from backend.common.schema import SchemaBase

# ===== enums =====
SessionType = Literal['chapter', 'bank', 'random', 'exam', 'wrong', 'favorite', 'note']
SessionStatus = Literal['in_progress', 'completed', 'abandoned']
QuestionType = Literal['single', 'multiple', 'judgement', 'fill', 'shortAnswer']
AnswerCardStatus = Literal['correct', 'wrong', 'unanswered']

KnowledgePointValue = str | int | dict[str, Any]


# ===== chapter brief for session =====
class SessionChapterBrief(SchemaBase):
    """会话关联章节摘要"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='章节 ID')
    name: str = Field(description='章节名称')
    code: str | None = Field(None, description='章节编码')
    parent_id: int | None = Field(None, description='父级章节 ID')
    level: int = Field(description='章节层级')
    sort_order: int = Field(default=0, description='排序权重')


# ===== session create / query =====
class CreatePracticeSessionParam(SchemaBase):
    """创建练习会话参数"""

    session_type: SessionType = Field(description='会话类型')
    practice_name: str | None = Field(None, max_length=255, description='会话名称')
    bank_id: int | None = Field(None, gt=0, description='题库 ID（筛题上下文）')
    chapter_id: int | None = Field(None, gt=0, description='章节 ID（筛题上下文）')
    year_end: int | None = Field(None, ge=1900, le=2100, description='结束年份（按试卷年份）')
    year_start: int | None = Field(None, ge=1900, le=2100, description='起始年份（按试卷年份）')
    region: str | None = Field(None, max_length=100, description='地区关键字（算入试卷名称/编码/描述）')
    cat_id: int | None = Field(None, gt=0, description='分类 ID（知识点合集筛选）')
    knowledge_point: list[KnowledgePointValue] | None = Field(None, min_length=1, max_length=200, description='考点标签筛选')
    limit: int | None = Field(None, ge=1, le=500, description='抽题数量上限')
    shuffle: bool = Field(False, description='是否打乱题序')
    exam_config: dict[str, Any] | None = Field(None, description='考试配置')


class CreateSessionFromIdsParam(SchemaBase):
    """从题目 ID 列表创建练习会话"""

    question_ids: list[int] = Field(min_length=1, max_length=500, description='题目 ID 列表')
    session_type: SessionType = Field(description='会话类型')
    practice_name: str | None = Field(None, max_length=255, description='会话名称')
    bank_id: int | None = Field(None, gt=0, description='题库 ID（可选，用于限定挂载上下文）')
    chapter_id: int | None = Field(None, gt=0, description='章节 ID（可选，用于限定挂载上下文）')



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
    chapter: SessionChapterBrief | None = Field(None, description='题目所属章节')


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


class GetPracticeRecordSessionItem(SchemaBase):
    """会话详情中的作答记录项（包含 user_answer）"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='记录 ID')
    session_id: int = Field(description='会话 ID')
    seq_no: int = Field(description='题序')
    question_id: int = Field(description='题目 ID')
    placement_id: int = Field(description='挂载 ID')
    user_answer: dict[str, Any] | list[Any] | str = Field(description='用户答案')
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
    source_key: str | None = Field(None, description='来源签名')
    exam_config: dict[str, Any] | None = Field(None, description='考试配置')
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


class ChapterDistributionItem(SchemaBase):
    """章节分布统计项"""

    chapter_id: int | None = Field(None, description='章节 ID')
    chapter_name: str | None = Field(None, description='章节名称')
    chapter_code: str | None = Field(None, description='章节编码')
    question_count: int = Field(ge=0, description='题目数量')


class GetPracticeSessionDetail(GetPracticeSessionListItem):
    """练习会话详情"""

    chapter_distribution: list[ChapterDistributionItem] = Field(default_factory=list, description='章节分布统计')
    session_questions: list[SessionQuestionItem] = Field(default_factory=list, description='会话题目快照')
    records: list[GetPracticeRecordSessionItem] = Field(default_factory=list, description='作答记录列表')


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
    reward_exp: int = Field(default=0, ge=0, description='本次奖励经验')
    practice_reward_exp: int = Field(default=0, ge=0, description='本次答题奖励经验')
    check_in_reward_exp: int = Field(default=0, ge=0, description='本次自动签到奖励经验')
    is_auto_checked_in: bool = Field(default=False, description='本次是否自动签到')
    check_in_streak: int | None = Field(default=None, description='连续签到天数')
    family_code: str | None = Field(default=None, description='入账等级族群')
    tier_grade: int | None = Field(default=None, description='当前等级')
    exp: int | None = Field(default=None, description='累计经验')
    available_exp: int | None = Field(default=None, description='可用经验')


# ===== settlement/report =====
class AnswerCardItem(SchemaBase):
    """答题卡项"""

    seq_no: int = Field(ge=1, description='题序')
    question_id: int = Field(description='题目 ID')
    placement_id: int = Field(description='挂载 ID')
    status: AnswerCardStatus = Field(description='作答状态')
    answer_time: int = Field(ge=0, description='耗时（秒）')
    chapter_name: str | None = Field(None, description='章节名称')


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
    option_select_stats: dict[str, Any] | None = Field(None, description='选项选择统计')


class PracticeJudgeResultItem(GetQuestionSolution):
    """即时判题结果"""

    question_id: int = Field(description='题目 ID')
    record_id: int | None = Field(None, description='答题记录 ID')
    score: Decimal | None = Field(None, ge=Decimal('0'), description='得分')
    full_score: Decimal | None = Field(None, ge=Decimal('0'), description='满分')
    ai_evaluation_id: int | None = Field(None, description='AI 判分记录 ID')
    summary_text: str | None = Field(None, description='AI 判分摘要')
    error_message: str | None = Field(None, description='错误信息')


class BatchUpsertPracticeRecordsResult(SchemaBase):
    """批量提交作答结果"""

    upserted_count: int = Field(ge=0, description='写入记录数')
    judge_results: list[PracticeJudgeResultItem] = Field(default_factory=list, description='即时判题结果')


# ===== 会话题目批量返回 =====


class SessionQuestionOptionItem(SchemaBase):
    """会话题目选项项"""

    option_code: str = Field(description='选项编码')
    content: str = Field(description='选项内容')


class SessionQuestionItem(SchemaBase):
    """会话题目项"""

    seq_no: int = Field(ge=1, description='题序')
    question_id: int = Field(description='题目 ID')
    type: QuestionType = Field(description='题型')
    stem: str = Field(description='题干')
    options: list[SessionQuestionOptionItem] = Field(default_factory=list, description='选项列表')
    material_ids: list[int] = Field(default_factory=list, description='材料 ID 列表')
    knowledge_point: list[KnowledgePointValue] | None = Field(None, description='考点标签')
    difficulty: str | None = Field(None, description='难度')


class SessionMaterialItem(SchemaBase):
    """会话材料项"""

    id: int = Field(description='材料 ID')
    title: str | None = Field(None, description='材料标题')
    content: str = Field(description='材料内容')


class GetSessionQuestionsResponse(SchemaBase):
    """会话题目批量返回"""

    questions: list[SessionQuestionItem] = Field(default_factory=list, description='题目列表')
    materials: list[SessionMaterialItem] = Field(default_factory=list, description='材料列表')
