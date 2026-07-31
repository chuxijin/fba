from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import ConfigDict, Field, model_validator

from backend.app.question_bank_v2.schema.knowledge import (
    GetKnowledgePointAssignmentDetail,
    KnowledgePointAssignmentParam,
)
from backend.app.question_bank_v2.schema.material import (
    GetQuestionInteractionDetail,
    GetQuestionMaterialDetail,
    QuestionMaterialParam,
)
from backend.common.schema import SchemaBase

QuestionType = Literal[
    'single_choice',
    'multiple_choice',
    'true_false',
    'fill_blank',
    'short_answer',
    'composite',
    'interactive',
]
ContentFormat = Literal['html', 'markdown', 'plain', 'json']
QuestionVisibility = Literal['private', 'internal', 'public']
QuestionOrigin = Literal['curated', 'imported', 'user_created', 'generated']
QuestionStatus = Literal['active', 'disabled', 'archived']
RevisionStatus = Literal['draft', 'published', 'retired']
GradingMethod = Literal['exact', 'set', 'ordered', 'range', 'keyword', 'rubric', 'manual', 'custom']
QuestionCollectionSource = Literal['bank', 'wrong', 'favorite', 'note', 'custom']


class CollectQuestionsParam(SchemaBase):
    """统一采集题目稳定身份参数"""

    source_type: QuestionCollectionSource = Field(default='bank', description='题目来源类型')
    bank_id: int | None = Field(None, gt=0, description='题库稳定身份 ID；题库来源必填，个人来源可用于筛选')
    section_id: int | None = Field(None, gt=0, description='篇章 ID')
    favorite_folder_id: int | None = Field(None, gt=0, description='收藏来源的收藏夹 ID')
    question_ids: list[int] = Field(default_factory=list, max_length=5000, description='指定题目的稳定身份 ID')
    knowledge_point_ids: list[int] = Field(default_factory=list, max_length=200, description='知识点 ID')
    include_knowledge_descendants: bool = Field(default=True, description='是否包含知识点后代节点')
    question_types: list[QuestionType] = Field(default_factory=list, max_length=7, description='题型筛选')
    year_start: int | None = Field(None, ge=1900, le=2100, description='试题起始年份')
    year_end: int | None = Field(None, ge=1900, le=2100, description='试题结束年份')
    limit: int = Field(default=5000, ge=1, le=5000, description='返回题量上限')

    @model_validator(mode='after')
    def normalize_filters(self) -> 'CollectQuestionsParam':
        """规范化采集条件并校验来源专用参数"""
        self.question_ids = list(dict.fromkeys(self.question_ids))
        self.knowledge_point_ids = sorted(set(self.knowledge_point_ids))
        self.question_types = sorted(set(self.question_types))
        if any(item <= 0 for item in self.question_ids + self.knowledge_point_ids):
            raise ValueError('题目和知识点 ID 必须大于 0')
        if self.year_start is not None and self.year_end is not None and self.year_start > self.year_end:
            raise ValueError('起始年份不能大于结束年份')
        if self.source_type == 'bank' and self.bank_id is None:
            raise ValueError('题库来源必须提供 bank_id')
        if self.section_id is not None and self.bank_id is None:
            raise ValueError('按篇章筛选必须提供 bank_id')
        if self.favorite_folder_id is not None and self.source_type != 'favorite':
            raise ValueError('favorite_folder_id 仅适用于收藏来源')
        if self.source_type == 'custom' and not self.question_ids:
            raise ValueError('指定题目来源必须提供 question_ids')
        if self.source_type != 'custom' and self.question_ids:
            raise ValueError('question_ids 仅适用于指定题目来源')
        return self


class CollectQuestionsResult(SchemaBase):
    """统一采集题目结果"""

    source_type: QuestionCollectionSource = Field(description='题目来源类型')
    question_ids: list[int] = Field(default_factory=list, description='命中的稳定题目 ID')
    total: int = Field(ge=0, description='命中题量')


class QuestionOption(SchemaBase):
    """题目有序选项"""

    option_code: str = Field(min_length=1, max_length=16, description='选项稳定编码')
    content: str = Field(min_length=1, max_length=100_000, description='选项内容')
    sort_order: int = Field(default=0, ge=0, description='选项排序')


class QuestionAnswerParam(SchemaBase):
    """题目权威答案参数"""

    answer_data: dict[str, Any] = Field(description='结构化标准答案')
    grading_method: GradingMethod = Field(default='exact', description='判分方式')
    grading_config: dict[str, Any] = Field(default_factory=dict, description='判分容错、关键词或量规配置')


class QuestionExplanationParam(SchemaBase):
    """题目解析参数"""

    content: str = Field(min_length=1, max_length=1_000_000, description='解析富文本')
    explanation_type: str = Field(default='official', min_length=1, max_length=24, description='解析类型')
    version_no: int = Field(default=1, gt=0, description='同类型解析版本号')
    is_default: bool = Field(default=False, description='是否默认展示')


class CreateQuestionParam(SchemaBase):
    """创建题目参数"""

    code: str = Field(min_length=1, max_length=64, pattern=r'^[A-Za-z0-9][A-Za-z0-9_.-]*$', description='稳定业务编码')
    visibility: QuestionVisibility = Field(default='public', description='题目可见范围')
    origin_type: QuestionOrigin = Field(default='curated', description='题目来源类型')
    status: QuestionStatus = Field(default='active', description='题目身份状态')
    stem: str = Field(min_length=1, max_length=1_000_000, description='题干富文本')
    content_format: ContentFormat = Field(default='html', description='题干内容格式')
    question_type: QuestionType = Field(default='single_choice', description='题型')
    options: list[QuestionOption] = Field(default_factory=list, max_length=20, description='有序选项快照')
    default_score: Decimal = Field(default=Decimal('1.00'), ge=0, description='默认分值')
    answer: QuestionAnswerParam = Field(description='题目权威答案')
    explanations: list[QuestionExplanationParam] = Field(min_length=1, max_length=20, description='题目解析列表')
    knowledge_points: list[KnowledgePointAssignmentParam] = Field(
        default_factory=list,
        max_length=50,
        description='知识点标注',
    )
    materials: list[QuestionMaterialParam] = Field(
        default_factory=list,
        max_length=20,
        description='题目使用的固定材料版本',
    )

    @model_validator(mode='after')
    def validate_default_explanation(self) -> 'CreateQuestionParam':
        """每个题目必须且只能有一个默认解析"""
        if sum(item.is_default for item in self.explanations) != 1:
            raise ValueError('题目必须且只能有一个默认解析')
        point_ids = [item.knowledge_point_id for item in self.knowledge_points]
        if len(point_ids) != len(set(point_ids)):
            raise ValueError('同一题目不能重复标注知识点')
        material_keys = [(item.material_id, item.role) for item in self.materials]
        if len(material_keys) != len(set(material_keys)):
            raise ValueError('同一题目不能以相同用途重复关联同一材料')
        return self


class UpdateQuestionParam(SchemaBase):
    """更新题目参数"""

    code: str | None = Field(
        None,
        min_length=1,
        max_length=64,
        pattern=r'^[A-Za-z0-9][A-Za-z0-9_.-]*$',
        description='稳定业务编码',
    )
    visibility: QuestionVisibility | None = Field(None, description='题目可见范围')
    status: QuestionStatus | None = Field(None, description='题目身份状态')
    stem: str | None = Field(None, min_length=1, max_length=1_000_000, description='题干富文本')
    content_format: ContentFormat | None = Field(None, description='题干内容格式')
    question_type: QuestionType | None = Field(None, description='题型')
    options: list[QuestionOption] | None = Field(None, max_length=20, description='有序选项快照')
    default_score: Decimal | None = Field(None, ge=0, description='默认分值')
    answer: QuestionAnswerParam | None = Field(None, description='题目权威答案')
    explanations: list[QuestionExplanationParam] | None = Field(
        None,
        min_length=1,
        max_length=20,
        description='题目解析列表',
    )
    knowledge_points: list[KnowledgePointAssignmentParam] | None = Field(
        None,
        max_length=50,
        description='知识点标注；传入时全量替换',
    )
    materials: list[QuestionMaterialParam] | None = Field(
        None,
        max_length=20,
        description='题目材料；传入时全量替换',
    )

    @model_validator(mode='after')
    def validate_default_explanation(self) -> 'UpdateQuestionParam':
        """全量替换解析时必须且只能有一个默认解析"""
        if self.explanations is not None and sum(item.is_default for item in self.explanations) != 1:
            raise ValueError('题目必须且只能有一个默认解析')
        if self.knowledge_points is not None:
            point_ids = [item.knowledge_point_id for item in self.knowledge_points]
            if len(point_ids) != len(set(point_ids)):
                raise ValueError('同一题目不能重复标注知识点')
        if self.materials is not None:
            material_keys = [(item.material_id, item.role) for item in self.materials]
            if len(material_keys) != len(set(material_keys)):
                raise ValueError('同一题目不能以相同用途重复关联同一材料')
        return self


class GetQuestionAnswerDetail(QuestionAnswerParam):
    """题目权威答案详情"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='答案 ID')
    question_id: int = Field(description='题目稳定身份 ID')


class GetQuestionExplanationDetail(QuestionExplanationParam):
    """题目解析详情"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='解析 ID')
    question_id: int = Field(description='题目稳定身份 ID')
    status: RevisionStatus = Field(description='解析状态')


class GetQuestionDetail(SchemaBase):
    """题目聚合详情"""

    id: int = Field(description='题目稳定身份 ID')
    code: str = Field(description='稳定业务编码')
    owner_id: int | None = Field(None, description='题目所有者 ID')
    visibility: QuestionVisibility = Field(description='题目可见范围')
    origin_type: QuestionOrigin = Field(description='题目来源类型')
    status: QuestionStatus = Field(description='题目身份状态')
    stem: str = Field(description='题干富文本')
    content_format: ContentFormat = Field(default='html', description='题干内容格式')
    question_type: QuestionType = Field(description='题型')
    options: list[QuestionOption] = Field(default_factory=list, description='有序选项快照')
    default_score: Decimal = Field(description='默认分值')
    difficulty: Decimal | None = Field(None, description='基于作答数据动态计算的难度')
    content_hash: str | None = Field(None, description='规范化内容 SHA-256')
    answer: GetQuestionAnswerDetail | None = Field(None, description='权威答案')
    explanations: list[GetQuestionExplanationDetail] = Field(default_factory=list, description='解析列表')
    knowledge_points: list[GetKnowledgePointAssignmentDetail] = Field(default_factory=list, description='知识点标注')
    materials: list[GetQuestionMaterialDetail] = Field(default_factory=list, description='固定材料版本')
    interactions: list[GetQuestionInteractionDetail] = Field(default_factory=list, description='交互题定义')
    created_by: int = Field(description='创建者 ID')
    updated_by: int | None = Field(None, description='修改者 ID')
    created_time: datetime = Field(description='创建时间')
    updated_time: datetime | None = Field(None, description='更新时间')


class GetQuestionListItem(SchemaBase):
    """题目管理列表项"""

    id: int = Field(description='题目稳定身份 ID')
    code: str = Field(description='稳定业务编码')
    visibility: QuestionVisibility = Field(description='题目可见范围')
    origin_type: QuestionOrigin = Field(description='题目来源类型')
    status: QuestionStatus = Field(description='题目身份状态')
    stem: str = Field(description='题干富文本')
    question_type: QuestionType = Field(description='题型')
    default_score: Decimal | None = Field(None, description='默认分值')
    difficulty: Decimal | None = Field(None, description='基于作答数据动态计算的难度')
    created_time: datetime = Field(description='创建时间')
    updated_time: datetime | None = Field(None, description='最近更新时间')
