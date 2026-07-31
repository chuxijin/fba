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
from backend.app.question_bank_v2.schema.user_content import ContentGroupNode
from backend.common.schema import SchemaBase

WrongEntrySource = Literal['attempt', 'manual', 'ocr', 'import']
WrongEntryScope = Literal['all', 'bank', 'external']
WrongStateStatus = Literal['active', 'resolved', 'suspended']
WrongStateAction = Literal['resolve', 'reopen', 'suspend', 'resume', 'pin', 'unpin']
MasteryState = Literal['new', 'learning', 'review', 'mastered', 'suspended']
ReviewTagType = Literal['reason', 'method', 'other']
QuestionAssetRole = Literal['stem', 'option', 'explanation', 'attachment', 'ocr_source', 'other']

EXTERNAL_ENTRY_SOURCES: tuple[str, ...] = ('manual', 'ocr', 'import')


class ExternalQuestionAssetParam(SchemaBase):
    """外部错题版本资产关联参数"""

    asset_id: int = Field(gt=0, description='已托管题库资产 ID')
    link_key: str = Field(min_length=1, max_length=64, description='题目版本内稳定引用键')
    role: QuestionAssetRole = Field(default='ocr_source', description='资产用途')
    locator: dict[str, Any] = Field(default_factory=dict, description='选项或内容块定位信息')
    sort_order: int = Field(default=0, ge=0, description='同用途资产排序')


class GetExternalQuestionAssetUploadResult(SchemaBase):
    """用户错题图片上传结果"""

    asset_id: int = Field(description='V2 题库资产 ID')
    url: str = Field(description='可直接展示的资产地址')
    object_key: str = Field(description='对象存储键')
    mime_type: str = Field(description='媒体类型')
    size_bytes: int = Field(ge=0, description='文件字节数')


class RecognizeExternalWrongQuestionParam(SchemaBase):
    """识别外部错题图片参数"""

    images: list[str] = Field(min_length=1, max_length=1, description='本地题图 Base64 Data URL 数组')


class RecognizedExternalQuestionOption(SchemaBase):
    """识别出的题目选项"""

    option_code: str = Field(description='选项编码')
    content: str = Field(description='选项富文本内容')


class RecognizeExternalWrongQuestionResult(SchemaBase):
    """外部错题图片识别草稿"""

    stem: str = Field(default='', description='题干富文本')
    options: list[RecognizedExternalQuestionOption] = Field(default_factory=list, description='选项列表')
    answer: str = Field(default='', description='参考答案')
    explanation: str = Field(default='', description='题目解析')
    warnings: list[str] = Field(default_factory=list, description='识别警告')


class CreateExternalWrongQuestionParam(SchemaBase):
    """录入用户在外部遇到的错题参数"""

    idempotency_key: str = Field(min_length=8, max_length=128, description='客户端录入幂等键')
    entry_source: Literal['manual', 'ocr', 'import'] = Field(description='错题录入来源')
    stem: str = Field(min_length=1, max_length=1_000_000, description='题干内容；图片题可填写简短占位说明')
    content_format: ContentFormat = Field(default='html', description='题干内容格式')
    question_type: QuestionType = Field(default='single_choice', description='题型')
    options: list[QuestionOption] = Field(default_factory=list, max_length=20, description='有序选项')
    default_score: Decimal = Field(default=Decimal('1.00'), ge=0, description='默认分值')
    answer: QuestionAnswerParam = Field(description='权威答案；录入后即可进入刷题系统重练')
    explanations: list[QuestionExplanationParam] = Field(
        default_factory=list,
        max_length=20,
        description='可选解析列表',
    )
    assets: list[ExternalQuestionAssetParam] = Field(
        default_factory=list,
        max_length=20,
        description='题干、选项或 OCR 来源资产',
    )
    source_system: str | None = Field(None, min_length=1, max_length=64, description='外部来源系统')
    external_key: str | None = Field(None, min_length=1, max_length=255, description='外部来源唯一键')
    source_url: str | None = Field(None, max_length=1024, description='外部来源地址')
    entry_metadata: dict[str, Any] = Field(default_factory=dict, description='OCR 置信度等采集上下文')
    summary: str | None = Field(None, max_length=100_000, description='录入时的初步反思')
    review_data: dict[str, Any] = Field(default_factory=dict, description='录入时的防错策略等结构化信息')
    tag_ids: list[int] = Field(default_factory=list, max_length=20, description='录入时选择的复盘标签 ID')
    knowledge_point_ids: list[int] = Field(default_factory=list, max_length=50, description='录入时选择的知识点 ID')

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
    """提交一次错题复盘参数

    复盘只记录学习者的主观反思，不打分、不影响重练调度。
    重练等级由客观作答（对错 × 用时）自动派生，见 practice_schedule_service。
    """

    idempotency_key: str = Field(min_length=8, max_length=128, description='客户端复盘提交幂等键')
    source_attempt_id: int | None = Field(None, gt=0, description='本次复盘关联的作答事实 ID')
    duration_ms: int = Field(default=0, ge=0, le=86_400_000, description='复盘用时毫秒')
    summary: str | None = Field(None, max_length=100_000, description='学习者复盘总结')
    review_data: dict[str, Any] = Field(default_factory=dict, description='防错策略等结构化内容')
    tag_ids: list[int] = Field(default_factory=list, max_length=20, description='复盘标签 ID')
    knowledge_point_ids: list[int] = Field(default_factory=list, max_length=50, description='知识点 ID')

    @model_validator(mode='after')
    def deduplicate_links(self) -> 'CreateQuestionReviewParam':
        """去重复盘标签和知识点"""
        self.tag_ids = list(dict.fromkeys(self.tag_ids))
        self.knowledge_point_ids = list(dict.fromkeys(self.knowledge_point_ids))
        return self


class UpdateWrongStateParam(SchemaBase):
    """手动调整错题本状态参数"""

    action: WrongStateAction = Field(description='resolve/reopen/suspend/resume/pin/unpin')


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
    review_count: int = Field(default=0, ge=0, description='已复盘次数')
    last_reviewed_time: datetime | None = Field(None, description='最近复盘时间')
    practice_level: int = Field(default=0, ge=0, description='重练阶梯等级')
    last_rating: int | None = Field(None, ge=1, le=4, description='最近派生重练等级')
    next_practice_time: datetime | None = Field(None, description='下次重练时间')
    mastery_state: MasteryState = Field(default='new', description='掌握状态，供差异化导出')


class GetWrongQuestionDetail(GetWrongQuestionListItem):
    """用户错题详情"""

    answer_data: Any | None = Field(None, description='权威答案')
    explanation: str | None = Field(None, description='默认解析')
    bank_name: str | None = Field(None, description='来源题库名称')
    section_name: str | None = Field(None, description='来源篇章名称')
    resolve_threshold: int = Field(ge=1, description='移出错题本还需达到的连对次数')


class GetQuestionReviewDetail(SchemaBase):
    """错题复盘事件详情"""

    id: int = Field(description='复盘事件 ID')
    wrong_state_id: int = Field(description='错题状态 ID')
    question_id: int = Field(description='稳定题目 ID')
    source_attempt_id: int | None = Field(None, description='关联作答事实 ID')
    event_type: Literal['capture', 'review'] = Field(description='事件类型')
    duration_ms: int = Field(ge=0, description='复盘用时毫秒')
    summary: str | None = Field(None, description='学习者复盘总结')
    review_data: dict[str, Any] = Field(default_factory=dict, description='防错策略等结构化内容')
    tag_ids: list[int] = Field(default_factory=list, description='复盘标签 ID')
    knowledge_point_ids: list[int] = Field(default_factory=list, description='知识点 ID')
    reviewed_time: datetime = Field(description='复盘发生时间')


class SubmitQuestionReviewResult(SchemaBase):
    """复盘提交结果；复盘不改错题本状态，也不影响重练排期"""

    review: GetQuestionReviewDetail = Field(description='复盘事件详情')
    wrong_status: WrongStateStatus = Field(description='当前错题状态')
    review_count: int = Field(ge=0, description='累计复盘次数')
    next_practice_time: datetime | None = Field(None, description='下次重练时间，由作答推进')


class GetDueWrongQuestionResult(SchemaBase):
    """到期重练错题结果"""

    total_due: int = Field(ge=0, description='当前到期重练总数')
    items: list[GetWrongQuestionListItem] = Field(default_factory=list, description='按到期时间排序的错题')


class WrongQuestionStatistics(SchemaBase):
    """用户错题汇总统计"""

    total_count: int = Field(ge=0, description='错题总数')
    active_count: int = Field(ge=0, description='活跃错题数')
    resolved_count: int = Field(ge=0, description='已移出错题本数')
    due_count: int = Field(ge=0, description='当前到期重练数')
    reviewed_count: int = Field(ge=0, description='已复盘错题数')
    pending_review_count: int = Field(ge=0, description='待复盘错题数')
    wrong_occurrence_count: int = Field(ge=0, description='累计错误发生次数')
    groups: list[ContentGroupNode] = Field(default_factory=list, description='题库或知识点分组')


class WrongReviewDistributionItem(SchemaBase):
    """复盘看板分布项"""

    id: int = Field(description='标签或知识点 ID')
    name: str = Field(description='展示名称')
    color: str | None = Field(None, description='展示颜色')
    count: int = Field(ge=0, description='出现次数')


class GetWrongReviewDashboard(SchemaBase):
    """错因与知识点复盘看板

    分布来自用户复盘时主观选择的标签和知识点，与题目客观知识点标注不是一回事。
    """

    reviewed_count: int = Field(ge=0, description='已复盘错题数')
    pending_review_count: int = Field(ge=0, description='待复盘错题数')
    review_event_count: int = Field(ge=0, description='统计窗口内复盘事件数')
    reason_distribution: list[WrongReviewDistributionItem] = Field(default_factory=list, description='错因分布')
    knowledge_point_distribution: list[WrongReviewDistributionItem] = Field(
        default_factory=list,
        description='知识点分布',
    )
