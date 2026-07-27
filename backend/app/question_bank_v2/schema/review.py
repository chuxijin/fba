from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import Field, model_validator

from backend.app.question_bank_v2.schema.question import (
    ContentFormat,
    QuestionAnswerParam,
    QuestionExplanationParam,
    QuestionOption,
    QuestionType,
)
from backend.common.fsrs import ReviewForecast
from backend.common.schema import SchemaBase

WrongEntrySource = Literal['attempt', 'manual', 'ocr', 'import']
WrongStateStatus = Literal['active', 'resolved', 'suspended']
ReviewOutcome = Literal['continue', 'mastered', 'reopened']
ReviewRatingSource = Literal['user', 'auto']
ReviewTagType = Literal['reason', 'method', 'other']
QuestionAssetRole = Literal['stem', 'option', 'explanation', 'attachment', 'ocr_source', 'other']


class ExternalQuestionAssetParam(SchemaBase):
    """外部错题版本资产关联参数"""

    asset_id: int = Field(gt=0, description='已托管题库资产 ID')
    link_key: str = Field(min_length=1, max_length=64, description='题目版本内稳定引用键')
    role: QuestionAssetRole = Field(default='ocr_source', description='资产用途')
    locator: dict[str, Any] = Field(default_factory=dict, description='选项或内容块定位信息')
    sort_order: int = Field(default=0, ge=0, description='同用途资产排序')


class CreateExternalWrongQuestionParam(SchemaBase):
    """录入用户在外部遇到的错题参数"""

    idempotency_key: str = Field(min_length=8, max_length=128, description='客户端录入幂等键')
    entry_source: Literal['manual', 'ocr', 'import'] = Field(description='错题录入来源')
    stem: str = Field(min_length=1, description='题干内容；图片题可填写简短占位说明')
    content_format: ContentFormat = Field(default='html', description='题干内容格式')
    question_type: QuestionType = Field(default='single_choice', description='题型')
    options: list[QuestionOption] = Field(default_factory=list, description='有序选项')
    default_score: Decimal = Field(default=Decimal('1.00'), ge=0, description='默认分值')
    difficulty: Decimal | None = Field(None, ge=1, le=5, description='人工标定难度')
    language: str = Field(default='zh-CN', min_length=2, max_length=16, description='内容语言')
    answer: QuestionAnswerParam | None = Field(None, description='可选权威答案；缺失时题目保持草稿')
    explanations: list[QuestionExplanationParam] = Field(default_factory=list, description='可选解析列表')
    assets: list[ExternalQuestionAssetParam] = Field(default_factory=list, description='题干、选项或 OCR 来源资产')
    source_system: str | None = Field(None, min_length=1, max_length=64, description='外部来源系统')
    external_key: str | None = Field(None, min_length=1, max_length=255, description='外部来源唯一键')
    source_url: str | None = Field(None, max_length=1024, description='外部来源地址')
    entry_metadata: dict[str, Any] = Field(default_factory=dict, description='OCR 置信度等采集上下文')
    summary: str | None = Field(None, description='录入时的初步反思')
    review_data: dict[str, Any] = Field(default_factory=dict, description='录入时的防错策略等结构化信息')
    tag_ids: list[int] = Field(default_factory=list, description='录入时选择的复盘标签 ID')
    knowledge_point_ids: list[int] = Field(default_factory=list, description='录入时选择的知识点 ID')

    @model_validator(mode='after')
    def validate_content(self) -> 'CreateExternalWrongQuestionParam':
        """校验选项、解析和外部来源参数"""
        option_codes = [item.option_code for item in self.options]
        if len(option_codes) != len(set(option_codes)):
            raise ValueError('选项编码不能重复')
        if self.explanations and sum(item.is_default for item in self.explanations) != 1:
            raise ValueError('存在解析时必须且只能有一个默认解析')
        if (self.source_system is None) != (self.external_key is None):
            raise ValueError('外部来源系统和来源唯一键必须同时提供')
        self.tag_ids = list(dict.fromkeys(self.tag_ids))
        self.knowledge_point_ids = list(dict.fromkeys(self.knowledge_point_ids))
        return self


class CreateQuestionReviewParam(SchemaBase):
    """提交一次真正错题复习参数"""

    idempotency_key: str = Field(min_length=8, max_length=128, description='客户端复习提交幂等键')
    rating: int = Field(ge=1, le=4, description='FSRS 评分: 1 Again, 2 Hard, 3 Good, 4 Easy')
    rating_source: ReviewRatingSource = Field(default='user', description='评分来源')
    source_attempt_id: int | None = Field(None, gt=0, description='本次复习关联的作答事实 ID')
    duration_ms: int = Field(default=0, ge=0, le=86_400_000, description='复盘用时毫秒')
    summary: str | None = Field(None, description='学习者复盘总结')
    outcome: ReviewOutcome = Field(default='continue', description='复盘后的错题状态意图')
    review_data: dict[str, Any] = Field(default_factory=dict, description='防错策略等结构化内容')
    tag_ids: list[int] = Field(default_factory=list, description='复盘标签 ID')
    knowledge_point_ids: list[int] = Field(default_factory=list, description='知识点 ID')

    @model_validator(mode='after')
    def deduplicate_links(self) -> 'CreateQuestionReviewParam':
        """去重复盘标签和知识点"""
        self.tag_ids = list(dict.fromkeys(self.tag_ids))
        self.knowledge_point_ids = list(dict.fromkeys(self.knowledge_point_ids))
        return self


class CreateReviewTagParam(SchemaBase):
    """创建用户自定义复盘标签参数"""

    name: str = Field(min_length=1, max_length=64, description='标签名称')
    tag_type: ReviewTagType = Field(default='reason', description='标签类型')
    color: str | None = Field(None, max_length=16, description='展示颜色')


class GetReviewTagDetail(SchemaBase):
    """复盘标签详情"""

    id: int = Field(description='复盘标签 ID')
    name: str = Field(description='标签名称')
    user_id: int | None = Field(None, description='用户自定义标签所有者；系统标签为空')
    tag_type: ReviewTagType = Field(description='标签类型')
    color: str | None = Field(None, description='展示颜色')
    sort_order: int = Field(description='展示顺序')
    is_active: bool = Field(description='是否可选')


class GetWrongQuestionListItem(SchemaBase):
    """用户错题列表项"""

    id: int = Field(description='错题状态 ID')
    question_id: int = Field(description='稳定题目 ID')
    question_revision_id: int = Field(description='最近题目版本 ID')
    entry_source: WrongEntrySource = Field(description='首次进入错题本的来源')
    status: WrongStateStatus = Field(description='错题当前状态')
    wrong_count: int = Field(ge=0, description='累计错误次数')
    correct_streak: int = Field(ge=0, description='错题重练连续正确次数')
    first_wrong_time: datetime | None = Field(None, description='首次答错或录入时间')
    last_wrong_time: datetime | None = Field(None, description='最近答错时间')
    last_practice_time: datetime | None = Field(None, description='最近重练时间')
    last_wrong_response: Any | None = Field(None, description='最近错误答案快照')
    is_pinned: bool = Field(description='是否置顶')
    stem: str = Field(description='固定题目版本题干')
    content_format: str = Field(description='题干内容格式')
    question_type: str = Field(description='题型')
    option_data: list[dict[str, Any]] = Field(default_factory=list, description='有序选项')
    next_review_time: datetime | None = Field(None, description='FSRS 下次复习时间')


class GetQuestionReviewDetail(SchemaBase):
    """错题复盘事件详情"""

    id: int = Field(description='复盘事件 ID')
    wrong_state_id: int = Field(description='错题状态 ID')
    question_id: int = Field(description='稳定题目 ID')
    question_revision_id: int = Field(description='本次复盘题目版本 ID')
    source_attempt_id: int | None = Field(None, description='关联作答事实 ID')
    event_type: Literal['capture', 'review'] = Field(description='事件类型')
    rating: int | None = Field(None, ge=1, le=4, description='FSRS 评分')
    rating_source: ReviewRatingSource | None = Field(None, description='评分来源')
    duration_ms: int = Field(ge=0, description='复盘用时毫秒')
    summary: str | None = Field(None, description='学习者复盘总结')
    outcome: ReviewOutcome = Field(description='复盘后的错题状态意图')
    review_data: dict[str, Any] = Field(default_factory=dict, description='防错策略等结构化内容')
    tag_ids: list[int] = Field(default_factory=list, description='复盘标签 ID')
    knowledge_point_ids: list[int] = Field(default_factory=list, description='知识点 ID')
    algorithm_name: str | None = Field(None, description='调度算法名称')
    algorithm_version: str | None = Field(None, description='调度算法版本')
    due_before: datetime | None = Field(None, description='复盘前到期时间')
    due_after: datetime | None = Field(None, description='复盘后到期时间')
    reviewed_time: datetime = Field(description='复盘发生时间')


class SubmitQuestionReviewResult(SchemaBase):
    """复盘提交和调度结果"""

    review: GetQuestionReviewDetail = Field(description='复盘事件详情')
    wrong_status: WrongStateStatus = Field(description='复盘后的错题状态')
    next_review_time: datetime = Field(description='FSRS 下次复习时间')
    forecast: ReviewForecast = Field(description='更新后各评分对应的复习时间预览')


class GetDueWrongQuestionResult(SchemaBase):
    """到期错题结果"""

    total_due: int = Field(ge=0, description='当前到期错题总数')
    items: list[GetWrongQuestionListItem] = Field(default_factory=list, description='按到期时间排序的错题')
