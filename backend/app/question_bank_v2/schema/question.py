from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import ConfigDict, Field, model_validator

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


class QuestionOption(SchemaBase):
    """题目有序选项"""

    option_code: str = Field(min_length=1, max_length=16, description='选项稳定编码')
    content: str = Field(min_length=1, description='选项内容')
    sort_order: int = Field(default=0, ge=0, description='选项排序')


class QuestionAnswerParam(SchemaBase):
    """题目权威答案参数"""

    answer_data: dict[str, Any] = Field(description='结构化标准答案')
    grading_method: GradingMethod = Field(default='exact', description='判分方式')
    grading_config: dict[str, Any] = Field(default_factory=dict, description='判分容错、关键词或量规配置')


class QuestionExplanationParam(SchemaBase):
    """题目解析参数"""

    content: str = Field(min_length=1, description='解析富文本')
    explanation_type: str = Field(default='official', min_length=1, max_length=24, description='解析类型')
    language: str = Field(default='zh-CN', min_length=2, max_length=16, description='内容语言')
    version_no: int = Field(default=1, gt=0, description='同类型解析版本号')
    is_default: bool = Field(default=False, description='是否默认展示')


class QuestionRevisionSchemaBase(SchemaBase):
    """题目版本内容基础模型"""

    stem: str = Field(min_length=1, description='题干富文本')
    content_format: ContentFormat = Field(default='html', description='题干内容格式')
    question_type: QuestionType = Field(default='single_choice', description='题型')
    options: list[QuestionOption] = Field(default_factory=list, description='有序选项快照')
    default_score: Decimal = Field(default=Decimal('1.00'), ge=0, description='默认分值')
    difficulty: Decimal | None = Field(None, ge=1, le=5, description='人工标定难度')
    language: str = Field(default='zh-CN', min_length=2, max_length=16, description='内容语言')


class CreateQuestionRevisionParam(QuestionRevisionSchemaBase):
    """创建题目草稿版本参数"""

    answer: QuestionAnswerParam = Field(description='题目权威答案')
    explanations: list[QuestionExplanationParam] = Field(min_length=1, description='题目解析列表')

    @model_validator(mode='after')
    def validate_default_explanation(self) -> 'CreateQuestionRevisionParam':
        """每个题目版本必须且只能有一个默认解析"""
        if sum(item.is_default for item in self.explanations) != 1:
            raise ValueError('题目版本必须且只能有一个默认解析')
        return self


class UpdateQuestionRevisionParam(SchemaBase):
    """更新题目草稿版本参数"""

    stem: str | None = Field(None, min_length=1, description='题干富文本')
    content_format: ContentFormat | None = Field(None, description='题干内容格式')
    question_type: QuestionType | None = Field(None, description='题型')
    options: list[QuestionOption] | None = Field(None, description='有序选项快照')
    default_score: Decimal | None = Field(None, ge=0, description='默认分值')
    difficulty: Decimal | None = Field(None, ge=1, le=5, description='人工标定难度')
    language: str | None = Field(None, min_length=2, max_length=16, description='内容语言')
    answer: QuestionAnswerParam | None = Field(None, description='题目权威答案')
    explanations: list[QuestionExplanationParam] | None = Field(None, min_length=1, description='题目解析列表')

    @model_validator(mode='after')
    def validate_default_explanation(self) -> 'UpdateQuestionRevisionParam':
        """全量替换解析时必须且只能有一个默认解析"""
        if self.explanations is not None and sum(item.is_default for item in self.explanations) != 1:
            raise ValueError('题目版本必须且只能有一个默认解析')
        return self


class CreateQuestionParam(SchemaBase):
    """创建题目及首个草稿版本参数"""

    code: str = Field(min_length=1, max_length=64, pattern=r'^[A-Za-z0-9][A-Za-z0-9_.-]*$', description='稳定业务编码')
    visibility: QuestionVisibility = Field(default='public', description='题目可见范围')
    origin_type: QuestionOrigin = Field(default='curated', description='题目来源类型')
    status: QuestionStatus = Field(default='active', description='题目身份状态')
    revision: CreateQuestionRevisionParam = Field(description='首个草稿版本')


class UpdateQuestionParam(SchemaBase):
    """更新题目稳定身份参数"""

    code: str | None = Field(
        None,
        min_length=1,
        max_length=64,
        pattern=r'^[A-Za-z0-9][A-Za-z0-9_.-]*$',
        description='稳定业务编码',
    )
    visibility: QuestionVisibility | None = Field(None, description='题目可见范围')
    status: QuestionStatus | None = Field(None, description='题目身份状态')


class GetQuestionAnswerDetail(QuestionAnswerParam):
    """题目权威答案详情"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='答案 ID')
    question_revision_id: int = Field(description='题目版本 ID')


class GetQuestionExplanationDetail(QuestionExplanationParam):
    """题目解析详情"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='解析 ID')
    question_revision_id: int = Field(description='题目版本 ID')
    status: RevisionStatus = Field(description='解析状态')


class GetQuestionRevisionDetail(QuestionRevisionSchemaBase):
    """题目版本详情"""

    id: int = Field(description='题目版本 ID')
    question_id: int = Field(description='题目稳定身份 ID')
    revision_no: int = Field(description='题目版本号')
    content_hash: str | None = Field(None, description='规范化内容 SHA-256')
    status: RevisionStatus = Field(description='版本状态')
    answer: GetQuestionAnswerDetail | None = Field(None, description='权威答案')
    explanations: list[GetQuestionExplanationDetail] = Field(default_factory=list, description='解析列表')
    published_by: int | None = Field(None, description='发布人 ID')
    published_time: datetime | None = Field(None, description='发布时间')
    created_by: int = Field(description='创建者 ID')
    updated_by: int | None = Field(None, description='修改者 ID')
    created_time: datetime = Field(description='创建时间')
    updated_time: datetime | None = Field(None, description='更新时间')


class GetQuestionDetail(SchemaBase):
    """题目聚合详情"""

    id: int = Field(description='题目稳定身份 ID')
    code: str = Field(description='稳定业务编码')
    owner_id: int | None = Field(None, description='题目所有者 ID')
    current_revision_id: int | None = Field(None, description='当前发布版本 ID')
    visibility: QuestionVisibility = Field(description='题目可见范围')
    origin_type: QuestionOrigin = Field(description='题目来源类型')
    status: QuestionStatus = Field(description='题目身份状态')
    revision: GetQuestionRevisionDetail | None = Field(None, description='请求的题目版本')
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
    revision_id: int = Field(description='最近题目版本 ID')
    revision_no: int = Field(description='最近题目版本号')
    revision_status: RevisionStatus = Field(description='最近题目版本状态')
    stem: str = Field(description='题干富文本')
    question_type: QuestionType = Field(description='题型')
    difficulty: Decimal | None = Field(None, description='人工标定难度')
    updated_time: datetime | None = Field(None, description='最近更新时间')
