#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
题目相关 Schema

设计原则：
- 题目和解析分离
- 刷题时不返回答案
- 答案在解析中统一管理
"""
from datetime import datetime
from decimal import Decimal

from pydantic import ConfigDict, Field

from backend.common.schema import SchemaBase


# ============ 题目 Schema ============


class QuestionSchemaBase(SchemaBase):
    """题目基础 Schema"""

    bank_id: int = Field(description='题库 ID')
    chapter_id: int | None = Field(None, description='章节 ID')
    type: str = Field(description='题型: single/multiple/judgement/fill/shortAnswer')
    stem: str = Field(description='题干（富文本）')
    options_data: dict | None = Field(
        None,
        description='选项数据 {"A": {"code": "A", "content": "<p>...</p>"}, ...}',
    )
    difficulty: str = Field(default='medium', description='难度: easy/medium/hard')
    score: Decimal = Field(default=Decimal('1.0'), description='分值')
    knowledge_point: str | None = Field(None, description='考点（多个用逗号分隔）')
    source: str | None = Field(None, description='来源')
    year: int | None = Field(None, description='年份')
    usage: str = Field(default='all', description='用途: all/exam/practice')
    sort_order: int = Field(default=0, description='题目序号（在题库/章节内的排序）')
    is_active: bool = Field(default=True, description='是否启用')


class GetQuestionListItem(SchemaBase):
    """题目列表项（不含答案）"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='题目 ID')
    bank_id: int = Field(description='题库 ID')
    chapter_id: int | None = Field(None, description='章节 ID')
    type: str = Field(description='题型')
    stem: str = Field(description='题干')
    options_data: dict | None = Field(None, description='选项数据（刷题时必需）')
    difficulty: str = Field(description='难度')
    score: Decimal = Field(description='分值')
    knowledge_point: str | None = Field(None, description='考点')
    is_active: bool = Field(description='是否启用')
    sort_order: int = Field(default=0, description='题目序号')
    review_status: int = Field(description='审核状态')
    created_time: datetime = Field(description='创建时间')
    # 扁平化字段，方便前端直接显示
    bank_name: str | None = Field(None, description='题库名称')
    chapter_name: str | None = Field(None, description='章节名称')





class GetQuestionDetail(QuestionSchemaBase):
    """题目详情（管理员接口，包含答案和解析）"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='题目 ID')
    review_status: int = Field(description='审核状态')
    created_by: int = Field(description='创建人 ID')
    updated_by: int | None = Field(None, description='更新人 ID')
    created_time: datetime = Field(description='创建时间')
    updated_time: datetime | None = Field(None, description='更新时间')
    # 关联的解析数据（包含答案和解析内容）
    analysis: 'QuestionAnalysisSimple | None' = Field(None, description='题目解析（包含答案）')
    # 关联的材料 ID 列表
    material_ids: list[int] | None = Field(None, description='关联材料 ID 列表')


class GetQuestionWithRelations(GetQuestionDetail):
    """题目详情（含关联信息）"""

    model_config = ConfigDict(from_attributes=True)

    bank: dict | None = Field(None, description='题库信息')
    chapter: dict | None = Field(None, description='章节信息')


class CreateQuestionParam(SchemaBase):
    """创建题目参数"""

    bank_id: int = Field(description='题库 ID')
    chapter_id: int | None = Field(None, description='章节 ID')
    type: str = Field(description='题型: single/multiple/judgement/fill/shortAnswer')
    stem: str = Field(description='题干（富文本）')
    options_data: dict | None = Field(
        None,
        description='选项数据',
        examples=[
            {
                'A': {'code': 'A', 'content': '<p>选项A</p>'},
                'B': {'code': 'B', 'content': '<p>选项B</p>'},
            }
        ],
    )
    difficulty: str = Field(default='medium', description='难度: easy/medium/hard')
    score: Decimal = Field(default=Decimal('1.0'), description='分值')
    knowledge_point: str | None = Field(None, description='考点（多个用逗号分隔）')
    source: str | None = Field(None, description='来源')
    year: int | None = Field(None, description='年份')
    usage: str = Field(default='all', description='用途: all/exam/practice')
    sort_order: int = Field(default=0, description='题目序号（在题库/章节内的排序）')
    analysis: dict | None = Field(None, description='题目解析数据（单条，包含 answer_data 和 content，向下兼容）')
    analyses: list[dict] | None = Field(None, description='多版本解析列表（每个元素包含 type, answer_data, content, is_default）')
    material_ids: list[int] | None = Field(None, description='关联材料 ID 列表')


class UpdateQuestionParam(SchemaBase):
    """更新题目参数"""

    bank_id: int = Field(description='题库 ID')
    chapter_id: int | None = Field(None, description='章节 ID')
    type: str = Field(description='题型')
    stem: str = Field(description='题干（富文本）')
    options_data: dict | None = Field(None, description='选项数据')
    difficulty: str = Field(description='难度')
    score: Decimal = Field(description='分值')
    knowledge_point: str | None = Field(None, description='考点')
    source: str | None = Field(None, description='来源')
    year: int | None = Field(None, description='年份')
    usage: str = Field(description='用途')
    is_active: bool = Field(description='是否启用')
    sort_order: int = Field(default=0, description='题目序号')
    analysis: dict | None = Field(None, description='题目解析数据（单条，向下兼容）')
    analyses: list[dict] | None = Field(None, description='多版本解析列表')
    material_ids: list[int] | None = Field(None, description='关联材料 ID 列表')


class QuestionQueryParam(SchemaBase):
    """题目查询参数"""

    bank_id: int | None = Field(None, description='题库 ID')
    chapter_id: int | None = Field(None, description='章节 ID')
    type: str | None = Field(None, description='题型')
    difficulty: str | None = Field(None, description='难度')
    is_active: bool | None = Field(None, description='是否启用')
    review_status: int | None = Field(None, description='审核状态')
    keyword: str | None = Field(None, description='关键字搜索（搜索题干）')


class DeleteQuestionParam(SchemaBase):
    """删除题目参数"""

    ids: list[int] = Field(description='题目 ID 列表')


# ============ 题目解析 Schema ============


class QuestionAnalysisSchemaBase(SchemaBase):
    """题目解析基础 Schema"""

    answer_data: dict = Field(
        description='答案数据',
        examples=[
            {'correct': 'A'},
            {'correct': ['A', 'C']},
            {'correct': ['答案1', '答案2']},
        ],
    )
    content: str = Field(description='解析内容（富文本）')


class QuestionAnalysisSimple(SchemaBase):
    """简单的解析 Schema（仅用于嵌套）"""

    model_config = ConfigDict(from_attributes=True)

    answer_data: dict = Field(description='答案数据')
    content: str = Field(description='解析内容')


class GetQuestionAnalysisDetail(QuestionAnalysisSchemaBase):
    """题目解析详情"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='解析 ID')
    question_id: int = Field(description='题目 ID')
    view_count: int = Field(description='查看次数')
    helpful_count: int = Field(description='有帮助次数')
    unhelpful_count: int = Field(description='无帮助次数')
    created_time: datetime = Field(description='创建时间')
    updated_time: datetime | None = Field(None, description='更新时间')
    type: str = Field(default='official', description='解析类型')


class GetQuestionWithAnswer(GetQuestionListItem):
    """题目列表项（含答案和解析）- 用于查看历史记录"""

    answer_data: dict | None = Field(None, description='答案数据 {"correct": ["A", "B"]}')
    analysis_content: str | None = Field(None, description='解析内容')
    materials: list[dict] | None = Field(None, description='关联材料')
    analyses: list[GetQuestionAnalysisDetail] | None = Field(None, description='所有解析列表')


class CreateQuestionAnalysisParam(QuestionAnalysisSchemaBase):
    """创建题目解析参数"""

    question_id: int = Field(description='题目 ID')
    type: str = Field(default='official', description='解析类型/来源机构')
    is_default: bool = Field(default=False, description='是否默认展示')


class AnalysisVersionItem(SchemaBase):
    """单个解析版本（用于批量创建）"""
    
    type: str = Field(description='解析类型/来源机构，如: 华图, 粉笔, 官方')
    answer_data: dict = Field(description='答案数据 {\"correct\": \"...\"} ')
    content: str = Field(description='解析内容')
    is_default: bool = Field(default=False, description='是否默认展示')


class UpdateQuestionAnalysisParam(QuestionAnalysisSchemaBase):
    """更新题目解析参数"""


class QuestionAnswerItem(SchemaBase):
    """题目答案项（批量提交）"""

    question_id: int = Field(description='题目 ID')
    user_answer: str | list[str] = Field(description='用户答案')
    answer_time: Decimal | None = Field(None, description='答题时间（秒）')


class BatchSubmitAnswerParam(SchemaBase):
    """批量提交答案参数"""

    answers: list[QuestionAnswerItem] = Field(description='题目答案列表')
    include_analysis: bool = Field(default=False, description='是否包含解析内容（默认不包含）')


class QuestionResultItem(SchemaBase):
    """题目结果项（批量提交返回）"""

    question_id: int = Field(description='题目 ID')
    is_correct: bool = Field(description='是否正确')
    user_answer: str | list[str] = Field(description='用户答案')
    correct_answer: dict = Field(description='正确答案')
    score: Decimal = Field(description='得分')
    full_score: Decimal = Field(description='满分')
    analysis_content: str | None = Field(None, description='解析内容（可选，仅当 include_analysis=True 时返回）')


class BatchSubmitAnswerResult(SchemaBase):
    """批量提交答案结果"""

    total_questions: int = Field(description='总题目数')
    correct_count: int = Field(description='答对题目数')
    wrong_count: int = Field(description='答错题目数')
    total_score: Decimal = Field(description='总得分')
    full_score: Decimal = Field(description='总满分')
    accuracy_rate: Decimal = Field(description='正确率（百分比）')
    score_rate: Decimal = Field(description='得分率（百分比）')
    results: list[QuestionResultItem] = Field(description='每道题的结果详情')


# ============ 题目统计 Schema ============


class GetQuestionStatisticsDetail(SchemaBase):
    """题目统计详情"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='统计 ID')
    question_id: int = Field(description='题目 ID')
    attempt_count: int = Field(description='答题总次数')
    correct_count: int = Field(description='答对次数')
    correct_rate: Decimal = Field(description='正确率（百分比）')
    avg_answer_time: Decimal | None = Field(None, description='平均答题时间（秒）')
    wrong_option_stats: dict | None = Field(None, description='错误选项统计')
    collect_count: int = Field(description='收藏次数')
    note_count: int = Field(description='笔记次数')
    last_updated: datetime = Field(description='最后更新时间')


class UpdateQuestionStatisticsParam(SchemaBase):
    """更新题目统计参数"""

    attempt_count: int | None = Field(None, description='答题总次数（增量）')
    correct_count: int | None = Field(None, description='答对次数（增量）')
    answer_time: Decimal | None = Field(None, description='本次答题时间（秒）')
    wrong_option: str | None = Field(None, description='错误选项')
    collect_delta: int | None = Field(None, description='收藏数变化 (+1/-1)')
    note_delta: int | None = Field(None, description='笔记数变化 (+1/-1)')


class GetQuestionSolution(SchemaBase):
    """题目答案和解析（用于练题模式）"""

    model_config = ConfigDict(from_attributes=True)

    correct_answer: str | list[str] = Field(description='正确答案')
    analysis: str = Field(description='解析内容')
    is_correct: bool | None = Field(None, description='是否正确（传入 user_answer 时返回）')
    # 🔥 统计数据（全站正确率和易错项）
    correct_rate: Decimal = Field(default=Decimal('0'), description='全站正确率（百分比）')
    wrong_option_stats: dict | None = Field(None, description='错误选项统计: {"B": 1250, "D": 850}')


# ============ CSV 批量导入 Schema ============


class QuestionImportRow(SchemaBase):
    """单条题目导入数据"""

    ID: int | str | None = Field(None, description='序号（可选，仅用于排序）')
    题目: str = Field(description='题干内容')
    题型: str = Field(description='题型: 单选/多选/判断/填空/简答')
    分数: int | None = Field(default=1, description='分值')
    难度: str | None = Field(default='中等', description='难度: 简单/中等/困难')
    选项A: str | None = Field(None, description='选项 A')
    选项B: str | None = Field(None, description='选项 B')
    选项C: str | None = Field(None, description='选项 C')
    选项D: str | None = Field(None, description='选项 D')
    答案: str = Field(description='正确答案（如：A 或 A,B 或 答案文本）')
    解析: str | None = Field(None, description='解析内容')
    一级目录: str | None = Field(None, description='一级章节名称')
    二级目录: str | None = Field(None, description='二级章节名称')


class BatchImportParam(SchemaBase):
    """批量导入题目参数"""

    bank_id: int = Field(description='题库 ID')
    questions: list[QuestionImportRow] = Field(description='题目列表')


class ImportResultItem(SchemaBase):
    """单条导入结果"""

    row_number: int = Field(description='行号（CSV 中的行）')
    success: bool = Field(description='是否成功')
    question_id: int | None = Field(None, description='题目 ID（成功时返回）')
    error_message: str | None = Field(None, description='错误信息（失败时返回）')


class BatchImportResult(SchemaBase):
    """批量导入结果"""

    total: int = Field(description='总数')
    success_count: int = Field(description='成功数')
    fail_count: int = Field(description='失败数')
    details: list[ImportResultItem] = Field(description='详情列表')

