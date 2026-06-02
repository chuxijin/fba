#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import ConfigDict, Field

from backend.common.schema import SchemaBase

# ===== 枚举字面值 =====
QuestionTypeEnum = Literal['single', 'multiple', 'judgement', 'fill', 'shortAnswer']
DifficultyEnum = Literal['easy', 'medium', 'hard']
ContentStatusEnum = Literal[0, 10, 20]
ReviewStatusEnum = Literal[0, 10, 20]
AnalysisStatusEnum = Literal[0, 10, 20]
CollectSourceType = Literal['placement', 'wrong', 'favorite', 'note']

KnowledgePointValue = str | int | dict[str, Any]


# ===== 题目核心 =====


class QuestionCoreBase(SchemaBase):
    """题目本体基础"""

    type: QuestionTypeEnum = Field(description='题型')
    stem: str = Field(min_length=1, description='题干（富文本）')
    difficulty: DifficultyEnum = Field(default='medium', description='难度')
    default_score: Decimal = Field(default=Decimal('1.0'), ge=Decimal('0'), description='默认分值')
    knowledge_point: list[KnowledgePointValue] | None = Field(None, description='考点标签')
    content_status: ContentStatusEnum = Field(default=10, description='内容状态')


# ===== 挂载相关 =====


class QuestionPlacementItem(SchemaBase):
    """挂载响应项"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='挂载 ID')
    question_id: int = Field(description='题目 ID')
    bank_id: int = Field(description='题库 ID')
    chapter_id: int | None = Field(None, description='章节 ID')
    sort_order: int = Field(ge=0, description='排序')
    is_active: bool = Field(description='是否启用')
    score: Decimal | None = Field(None, ge=Decimal('0'), description='挂载分值')
    review_status: ReviewStatusEnum = Field(description='审核状态')
    scene_mask: int | None = Field(None, ge=0, description='场景位标记')
    bank_name: str | None = Field(None, description='题库名称')
    chapter_name: str | None = Field(None, description='章节名称')


class UpsertQuestionPlacementItem(SchemaBase):
    """挂载请求项"""

    bank_id: int = Field(gt=0, description='题库 ID')
    chapter_id: int | None = Field(None, gt=0, description='章节 ID')
    sort_order: int = Field(default=0, ge=0, description='排序')
    is_active: bool = Field(default=True, description='是否启用')
    score: Decimal | None = Field(None, ge=Decimal('0'), description='挂载分值')
    review_status: ReviewStatusEnum = Field(default=10, description='审核状态')
    scene_mask: int | None = Field(None, ge=0, description='场景位标记')


# ===== 选项相关 =====


class QuestionOptionItem(SchemaBase):
    """选项响应项"""

    option_code: str = Field(description='选项编码')
    content: str = Field(description='选项内容')
    sort_order: int = Field(default=0, ge=0, description='排序')
    is_active: bool = Field(default=True, description='是否启用')


class UpsertQuestionOptionItem(SchemaBase):
    """选项请求项"""

    option_code: str = Field(max_length=16, description='选项编码（大写: A/B/C...）')
    content: str = Field(min_length=1, description='选项内容')
    sort_order: int = Field(default=0, ge=0, description='排序')
    is_active: bool = Field(default=True, description='是否启用')


# ===== 解析相关 =====


class QuestionAnalysisItem(SchemaBase):
    """解析响应项"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='解析 ID')
    question_id: int = Field(description='题目 ID')
    type: str = Field(description='解析类型')
    version_no: int = Field(default=1, ge=1, description='版本号')
    is_default: bool = Field(description='是否默认展示')
    answer_data: dict[str, Any] = Field(description='答案数据')
    content: str = Field(description='解析内容')
    status: AnalysisStatusEnum = Field(description='状态')
    view_count: int = Field(ge=0, description='查看次数')
    helpful_count: int = Field(ge=0, description='有帮助次数')
    unhelpful_count: int = Field(ge=0, description='无帮助次数')
    created_time: datetime = Field(description='创建时间')
    updated_time: datetime | None = Field(None, description='更新时间')


class UpsertQuestionAnalysisItem(SchemaBase):
    """解析请求项"""

    type: str = Field(default='official', max_length=32, description='解析类型')
    version_no: int = Field(default=1, ge=1, description='版本号')
    is_default: bool = Field(default=False, description='是否默认展示')
    answer_data: dict[str, Any] = Field(description='答案数据')
    content: str = Field(min_length=1, description='解析内容')
    status: AnalysisStatusEnum = Field(default=10, description='状态')


# ===== 材料关系 =====


class SetQuestionMaterialRelationParam(SchemaBase):
    """设置题目材料关联"""

    material_ids: list[int] = Field(min_length=1, description='材料 ID 列表')


# ===== 统计相关 =====


class GetQuestionStatisticsDetail(SchemaBase):
    """题目统计详情"""

    model_config = ConfigDict(from_attributes=True)

    question_id: int = Field(description='题目 ID')
    attempt_count: int = Field(ge=0, description='答题总次数')
    correct_count: int = Field(ge=0, description='答对次数')
    correct_rate: Decimal = Field(ge=Decimal('0'), le=Decimal('100'), description='正确率（%）')
    avg_answer_time: Decimal | None = Field(None, ge=Decimal('0'), description='平均答题时间（秒）')
    option_select_stats: dict[str, Any] | None = Field(None, description='选项选择统计')
    collect_count: int = Field(ge=0, description='收藏次数')
    note_count: int = Field(ge=0, description='笔记次数')
    report_count: int = Field(default=0, ge=0, description='举报次数')
    last_updated: datetime = Field(description='最后更新时间')


class UpdateQuestionStatisticsParam(SchemaBase):
    """更新题目统计参数"""

    attempt_count: int | None = Field(None, ge=0, description='答题次数（增量）')
    correct_count: int | None = Field(None, ge=0, description='答对次数（增量）')
    answer_time: Decimal | None = Field(None, ge=Decimal('0'), description='本次答题时间（秒）')
    option_select: list[str] | None = Field(None, description='被选选项')
    collect_delta: int | None = Field(None, description='收藏数变化')
    note_delta: int | None = Field(None, description='笔记数变化')


# ===== 查询参数 =====


class QuestionQueryParam(SchemaBase):
    """题目查询参数"""

    bank_id: int | None = Field(None, gt=0, description='题库 ID（通过挂载筛选）')
    chapter_id: int | None = Field(None, gt=0, description='章节 ID（通过挂载筛选）')
    type: QuestionTypeEnum | None = Field(None, description='题型')
    difficulty: DifficultyEnum | None = Field(None, description='难度')
    content_status: ContentStatusEnum | None = Field(None, description='内容状态')
    is_active: bool | None = Field(None, description='是否启用（挂载级别）')
    review_status: ReviewStatusEnum | None = Field(None, description='审核状态（挂载级别）')
    scene_mask: int | None = Field(None, ge=0, description='场景位标记')
    keyword: str | None = Field(None, max_length=200, description='关键字搜索（搜索题干）')


class QuestionCollectParam(SchemaBase):
    """统一筛题参数"""

    source_type: CollectSourceType = Field(default='placement', description='题目来源类型')
    question_ids: list[int] | None = Field(
        None,
        min_length=1,
        max_length=5000,
        description='显式指定题目 ID 列表；传入后优先在该范围内继续过滤',
    )
    bank_id: int | None = Field(None, gt=0, description='题库 ID（筛题上下文）')
    bank_ids: list[int] | None = Field(
        None,
        min_length=1,
        max_length=5000,
        description='题库 ID 列表（筛题上下文）',
    )
    chapter_id: int | None = Field(None, gt=0, description='章节 ID（筛题上下文）')
    year_end: int | None = Field(None, ge=1900, le=2100, description='结束年份（按试卷年份）')
    year_start: int | None = Field(None, ge=1900, le=2100, description='起始年份（按试卷年份）')
    region: str | None = Field(None, max_length=100, description='地区关键字（算入试卷名称/编码/描述）')
    cat_id: int | None = Field(None, gt=0, description='分类 ID（试卷/合集筛选）')
    knowledge_point: list[KnowledgePointValue] | None = Field(
        None,
        min_length=1,
        max_length=200,
        description='知识点/考点标签筛选',
    )
    question_types: list[QuestionTypeEnum] | None = Field(
        None,
        min_length=1,
        max_length=20,
        description='题型过滤',
    )
    difficulties: list[DifficultyEnum] | None = Field(
        None,
        min_length=1,
        max_length=10,
        description='难度过滤',
    )
    stem_keyword: str | None = Field(None, max_length=200, description='题干关键字')
    option_keyword: str | None = Field(None, max_length=200, description='选项关键字')
    analysis_keyword: str | None = Field(None, max_length=200, description='解析关键字')
    content_status: ContentStatusEnum | None = Field(None, description='内容状态')
    is_active: bool | None = Field(None, description='是否启用（挂载级别）')
    review_status: ReviewStatusEnum | None = Field(None, description='审核状态（挂载级别）')
    limit: int | None = Field(None, ge=1, le=5000, description='最终返回题量上限')
    recent_days: int | None = Field(None, ge=1, le=3650, description='仅个人来源生效：最近天数')


class QuestionCollectResult(SchemaBase):
    """统一筛题结果"""

    source_type: CollectSourceType = Field(description='题目来源类型')
    question_ids: list[int] = Field(default_factory=list, description='命中的题目 ID 列表')
    total: int = Field(default=0, ge=0, description='命中题量')


# ===== 创建 / 更新 / 删除 =====


class CreateQuestionParam(SchemaBase):
    """创建题目参数"""

    core: QuestionCoreBase = Field(description='题目本体')
    options: list[UpsertQuestionOptionItem] = Field(default_factory=list, description='选项列表')
    placements: list[UpsertQuestionPlacementItem] = Field(min_length=1, description='挂载列表（至少 1 条）')
    analyses: list[UpsertQuestionAnalysisItem] = Field(min_length=1, description='解析列表（至少 1 条）')
    material_ids: list[int] | None = Field(None, description='关联材料 ID 列表')


class UpdateQuestionParam(SchemaBase):
    """更新题目参数"""

    core: QuestionCoreBase | None = Field(None, description='题目本体（全量替换）')
    options: list[UpsertQuestionOptionItem] | None = Field(None, description='选项列表（全量替换）')
    placements: list[UpsertQuestionPlacementItem] | None = Field(None, description='挂载列表（全量替换）')
    analyses: list[UpsertQuestionAnalysisItem] | None = Field(None, description='解析列表（全量替换）')
    material_ids: list[int] | None = Field(None, description='关联材料 ID 列表（全量替换）')


class DeleteQuestionParam(SchemaBase):
    """删除题目参数"""

    ids: list[int] = Field(min_length=1, description='题目 ID 列表')


# ===== 响应 =====


class GetQuestionListItem(SchemaBase):
    """题目列表项"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='题目 ID')
    type: QuestionTypeEnum = Field(description='题型')
    stem: str = Field(description='题干')
    difficulty: DifficultyEnum = Field(description='难度')
    default_score: Decimal = Field(ge=Decimal('0'), description='默认分值')
    knowledge_point: list[KnowledgePointValue] | None = Field(None, description='考点标签（code）')
    knowledge_point_display: list[str] | None = Field(None, description='考点标签（名称）')
    content_status: ContentStatusEnum = Field(description='内容状态')
    created_time: datetime = Field(description='创建时间')
    updated_time: datetime | None = Field(None, description='更新时间')
    placement: QuestionPlacementItem | None = Field(None, description='上下文挂载')
    option_count: int = Field(default=0, ge=0, description='选项数量')
    analysis_count: int = Field(default=0, ge=0, description='解析数量')


class GetQuestionDynamicCollectionItem(SchemaBase):
    """按筛选条件动态聚合得到的题目合集项"""

    id: int = Field(description='题库 ID')
    cat_id: int = Field(description='分类 ID')
    name: str = Field(description='题库名称')
    code: str = Field(description='题库编码')
    desc: str | None = Field(None, description='题库描述')
    bank_type: int = Field(description='内容类型: 1=习题, 2=试卷, 3=合集')
    difficulty: Decimal | None = Field(None, description='难度')
    parent_id: int | None = Field(None, description='父级题库 ID')
    q_count_cache: int = Field(default=0, description='题库缓存题量')
    matched_q_count: int = Field(default=0, description='当前筛选命中的题量')


class GetQuestionDetail(SchemaBase):
    """题目详情"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='题目 ID')
    type: QuestionTypeEnum = Field(description='题型')
    stem: str = Field(description='题干')
    difficulty: DifficultyEnum = Field(description='难度')
    default_score: Decimal = Field(ge=Decimal('0'), description='默认分值')
    knowledge_point: list[KnowledgePointValue] | None = Field(None, description='考点标签（code）')
    knowledge_point_display: list[str] | None = Field(None, description='考点标签（名称）')
    content_status: ContentStatusEnum = Field(description='内容状态')
    created_time: datetime = Field(description='创建时间')
    updated_time: datetime | None = Field(None, description='更新时间')
    options: list[QuestionOptionItem] = Field(default_factory=list, description='选项列表')
    placements: list[QuestionPlacementItem] = Field(default_factory=list, description='挂载列表')
    analyses: list[QuestionAnalysisItem] = Field(default_factory=list, description='解析列表')
    material_ids: list[int] = Field(default_factory=list, description='关联材料 ID 列表')
    statistics: GetQuestionStatisticsDetail | None = Field(None, description='题目统计')


class GetQuestionWithAnswer(SchemaBase):
    """题目导出详情（含答案和解析，用于题库导出/离线）"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='题目 ID')
    type: QuestionTypeEnum = Field(description='题型')
    stem: str = Field(description='题干')
    difficulty: DifficultyEnum = Field(description='难度')
    default_score: Decimal = Field(ge=Decimal('0'), description='默认分值')
    knowledge_point: list[KnowledgePointValue] | None = Field(None, description='考点标签（code）')
    knowledge_point_display: list[str] | None = Field(None, description='考点标签（名称）')
    content_status: ContentStatusEnum = Field(description='内容状态')
    created_time: datetime = Field(description='创建时间')
    updated_time: datetime | None = Field(None, description='更新时间')
    # 选项
    options: list[QuestionOptionItem] = Field(default_factory=list, description='选项列表')
    # 挂载上下文
    placement: QuestionPlacementItem | None = Field(None, description='挂载上下文')
    # 答案 & 解析
    answer_data: dict[str, Any] | None = Field(None, description='答案数据（来自默认解析）')
    analysis_content: str | None = Field(None, description='解析内容（来自默认解析）')
    analyses: list[QuestionAnalysisItem] = Field(default_factory=list, description='全部解析版本')
    # 材料
    material_ids: list[int] = Field(default_factory=list, description='关联材料 ID 列表')
