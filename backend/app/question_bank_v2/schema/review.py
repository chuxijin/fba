import re

from collections.abc import Mapping
from datetime import datetime
from decimal import Decimal
from html import unescape
from typing import Any, Literal

from pydantic import AwareDatetime, Field, model_validator

from backend.app.question_bank_v2.schema.material import GetQuestionMaterialDetail
from backend.app.question_bank_v2.schema.question import (
    ContentFormat,
    QuestionAnswerParam,
    QuestionExplanationParam,
    QuestionOption,
    QuestionType,
)
from backend.app.question_bank_v2.schema.user_content import ContentGroupNode
from backend.common.pagination import CursorPageData
from backend.common.schema import SchemaBase

WrongEntrySource = Literal['attempt', 'manual', 'ocr', 'import']
WrongEntryScope = Literal['all', 'bank', 'external']
WrongStateStatus = Literal['active', 'resolved', 'suspended']
WrongStateAction = Literal['resolve', 'reopen', 'suspend', 'resume', 'pin', 'unpin']
WrongBrowseMode = Literal['pending', 'reviewed', 'mastered']
WrongQuestionListView = Literal['full', 'summary', 'outline']
MasteryState = Literal['new', 'learning', 'review', 'mastered', 'suspended']
ReviewTagType = Literal['reason', 'method', 'other']
QuestionAssetRole = Literal['stem', 'option', 'explanation', 'attachment', 'ocr_source', 'other']

EXTERNAL_ENTRY_SOURCES: tuple[str, ...] = ('manual', 'ocr', 'import')
# 自主录入的错题没有题库归属，录入时把当时的领域写进 entry_metadata，列表按它做领域筛选。
# 键名由服务端写、服务端读，客户端传入的同名键会被丢弃。
ENTRY_METADATA_DOMAIN_KEY = 'domain_category_id'
# entry_metadata 其余约定键：统一在 schema 定义，避免 service / crud 各写一份字面量
ENTRY_METADATA_BATCH_KEY = 'import_batch_id'
ENTRY_METADATA_SOURCE_SYSTEM_KEY = 'source_system'
ENTRY_METADATA_EXTERNAL_KEY_KEY = 'external_key'
ENTRY_METADATA_SECTION_KEY = 'section_name'
# 原试卷模块路径（如 ["判断推理", "图形推理", "数量规律"]），用于章节内按题型聚拢
ENTRY_METADATA_MODULE_PATH_KEY = 'module_path'
# 章节筛选的虚拟值：题库错题可回退到题库章节，仍无章节的外部题归入此项
UNSECTIONED_SECTION_NAME = '__unsectioned__'
REVIEW_THOUGHT_REQUIRED_MESSAGE = '请至少记录一种思路（错误思路或正确解法）'


def has_review_thought(summary: str | None, review_data: Mapping[str, Any]) -> bool:
    """错误思路与正确解法任选其一，标签或知识点不能替代思路记录。"""
    prevention = review_data.get('prevention')
    return bool(summary and summary.strip()) or (isinstance(prevention, str) and bool(prevention.strip()))


class WrongQuestionFilters(SchemaBase):
    """错题列表和章节统计共用的请求筛选，不包含用户身份和已展开的领域范围。"""

    status: WrongStateStatus | None = Field(default='active', description='错题状态；空表示全部')
    entry_source: WrongEntrySource | None = Field(None, description='首次录入来源')
    entry_scope: WrongEntryScope | None = Field(None, description='题库错题或自主录入')
    domain_category_id: int | None = Field(None, gt=0, description='领域分类 ID；不传取用户当前领域')
    import_batch_id: str | None = Field(None, min_length=8, max_length=64, description='导入批次 ID')
    bank_id: int | None = Field(None, gt=0, description='题库 ID；用于集合详情')
    external_unbatched: bool = Field(default=False, description='只看无批次的散题')
    unassigned: bool = Field(default=False, description='只看无题库来源和导入批次的系统错题')
    since: AwareDatetime | None = Field(None, description='最近答错或录入时间下界（含），ISO 8601 时间需带时区')
    review_state: Literal['reviewed', 'pending'] | None = Field(
        None, description='复盘子状态：reviewed=已复盘，pending=待复盘（含复盘后再次答错）'
    )


class WrongQuestionListQuery(WrongQuestionFilters):
    """列表在共享范围上补充章节筛选与固定响应视图。"""

    section_name: str | None = Field(None, max_length=160, description='按章节/模块筛选；不传集合参数时跨集合')
    view: WrongQuestionListView = Field(
        default='full', description='full=兼容完整列表，summary=列表摘要，outline=仅 ID 和章节（答题卡）'
    )


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


class ExternalMaterialParam(SchemaBase):
    """外部错题附带的材料

    传内联内容，由服务端创建材料实体、发布版本并建立题目关联；
    客户端不需要也不应该预先创建材料。
    """

    link_key: str | None = Field(
        None,
        max_length=64,
        description='同批次内的材料复用键：键相同只创建一份材料，供多道题共享',
    )
    title: str = Field(default='材料', min_length=1, max_length=255, description='材料标题')
    content: str = Field(min_length=1, max_length=4_000_000, description='材料正文')
    content_format: Literal['html', 'markdown', 'plain', 'json'] = Field(default='html', description='正文格式')
    role: Literal['passage', 'prompt', 'reference', 'attachment'] = Field(default='passage', description='材料用途')
    sort_order: int = Field(default=0, ge=0, description='材料展示顺序')


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
    wrong_response: Any | None = Field(
        None,
        description='用户当时的作答快照；仅用于错题本回显，不参与判分',
    )
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
    materials: list[ExternalMaterialParam] = Field(
        default_factory=list,
        max_length=5,
        description='题目材料（篇章、资料等），服务端负责建材料实体并关联',
    )
    source_system: str | None = Field(None, min_length=1, max_length=64, description='外部来源系统')
    external_key: str | None = Field(None, min_length=1, max_length=255, description='外部来源唯一键')
    source_url: str | None = Field(None, max_length=1024, description='外部来源地址')
    entry_metadata: dict[str, Any] = Field(default_factory=dict, description='OCR 置信度等采集上下文')
    summary: str | None = Field(None, max_length=100_000, description='当时做题的错误思路')
    review_data: dict[str, Any] = Field(
        default_factory=dict,
        description='正确思路等结构化信息，约定键 prevention=正确的解题步骤',
    )
    tag_ids: list[int] = Field(default_factory=list, max_length=20, description='录入时选择的复盘标签 ID')
    knowledge_point_ids: list[int] = Field(default_factory=list, max_length=50, description='录入时选择的知识点 ID')

    @model_validator(mode='after')
    def validate_content(self) -> 'CreateExternalWrongQuestionParam':
        """校验选项、解析和外部来源参数"""
        source = str(self.entry_metadata.get('source') or '').strip()
        if not source:
            raise ValueError('错题来源不能为空')
        # 领域归属必须由服务端按当前领域写入，不能让客户端自己声明
        metadata = {key: value for key, value in self.entry_metadata.items() if key != ENTRY_METADATA_DOMAIN_KEY}
        self.entry_metadata = {**metadata, 'source': source}
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


class BatchImportItemResult(SchemaBase):
    """批量录入中单条成功记录"""

    external_key: str | None = Field(None, description='客户端外部来源唯一键')
    question_id: int = Field(description='新建的稳定题目 ID')
    wrong_state_id: int = Field(description='新建的错题状态 ID')


class BatchImportFailure(SchemaBase):
    """批量录入中单条失败记录"""

    index: int = Field(ge=0, description='在请求数组中的下标')
    external_key: str | None = Field(None, description='客户端外部来源唯一键')
    reason: str = Field(description='失败原因，可直接展示给用户')


class BatchImportResult(SchemaBase):
    """批量录入结果：逐条独立成败，单条失败不影响其余题目入库"""

    import_batch_id: str = Field(description='本次导入批次 ID，用于整批撤销')
    total: int = Field(ge=0, description='请求总条数')
    succeeded: int = Field(ge=0, description='成功条数')
    failed: int = Field(ge=0, description='失败条数')
    items: list[BatchImportItemResult] = Field(default_factory=list, description='成功记录')
    failures: list[BatchImportFailure] = Field(default_factory=list, description='失败记录')


class BatchUndoResult(SchemaBase):
    """批次撤销结果"""

    import_batch_id: str = Field(description='被撤销的导入批次 ID')
    deleted_states: int = Field(ge=0, description='移除的错题本状态数')
    deleted_questions: int = Field(ge=0, description='清理的私有题目数')
    deleted_reviews: int = Field(ge=0, description='清理的复盘事件数')
    deleted_materials: int = Field(default=0, ge=0, description='回收的孤儿材料数')


class ImportHistoryBatchItem(SchemaBase):
    """一次批量导入的聚合记录"""

    import_batch_id: str = Field(description='导入批次 ID')
    source: str | None = Field(None, description='导入时记录的来源（试卷名）')
    total: int = Field(ge=0, description='该批次题目总数')
    active: int = Field(ge=0, description='仍在错题本中的数量')
    first_time: datetime = Field(description='批次首个题目的创建时间')
    last_time: datetime = Field(description='批次最后一个题目的创建时间')


class ImportHistorySingleItem(SchemaBase):
    """无批次的单条外部录入（散题）"""

    id: int = Field(description='错题状态 ID')
    question_id: int = Field(description='稳定题目 ID')
    entry_source: WrongEntrySource = Field(description='录入来源')
    source: str | None = Field(None, description='录入时记录的来源')
    stem: str = Field(description='题干')
    created_time: datetime = Field(description='创建时间')


class ImportHistoryResult(SchemaBase):
    """导入记录：批量导入按批次聚合，散题按条列出"""

    batches: list[ImportHistoryBatchItem] = Field(default_factory=list, description='批量导入批次')
    singles: list[ImportHistorySingleItem] = Field(default_factory=list, description='散题')


class ImportBatchPage(CursorPageData[ImportHistoryBatchItem]):
    """批量导入批次的游标分页结果"""

    has_more: bool = Field(default=False, description='是否还有更多')


class ImportSinglePage(CursorPageData[ImportHistorySingleItem]):
    """散题的游标分页结果"""

    has_more: bool = Field(default=False, description='是否还有更多')


class WrongCollectionItem(SchemaBase):
    """错题集合：题库 / 导入批次 / 无批次散题"""

    collection_type: Literal['bank', 'import', 'single', 'unassigned'] = Field(description='集合类型')
    collection_id: str = Field(default='', description='集合标识：题库 ID 或导入批次 ID；散题为空')
    title: str = Field(description='集合名称')
    total: int = Field(ge=0, description='集合内错题总数')
    reviewed: int = Field(ge=0, description='已复盘数')
    pending: int = Field(ge=0, description='待复盘数')
    mastered: int = Field(default=0, ge=0, description='已掌握数')
    last_time: datetime | None = Field(None, description='最近错题时间')


class WrongCollectionPage(CursorPageData[WrongCollectionItem]):
    """错题集合列表（游标分页）"""

    total: int = Field(default=0, ge=0, description='当前状态和领域的错题总数，不累加可能重叠的集合')
    has_more: bool = Field(default=False, description='是否还有更多')


class GetWrongSectionFacet(SchemaBase):
    """当前浏览范围按原试卷章节/模块统计的题量"""

    section_name: str = Field(description='章节或模块名，如「政治理论」')
    total: int = Field(ge=0, description='该章节的题量')


class GetWrongSectionFacetsResult(SchemaBase):
    """集合章节筛选项"""

    total: int = Field(ge=0, description='当前浏览范围全部题量（含未标章节）')
    items: list[GetWrongSectionFacet] = Field(default_factory=list, description='章节及题量列表')


class CreateQuestionReviewParam(SchemaBase):
    """提交一次错题复盘参数

    复盘只记录学习者的主观反思，不打分、不影响重练调度。
    重练等级由客观作答（对错 × 用时）自动派生，见 practice_schedule_service。
    """

    idempotency_key: str = Field(min_length=8, max_length=128, description='客户端复盘提交幂等键')
    source_attempt_id: int | None = Field(None, gt=0, description='本次复盘关联的作答事实 ID')
    duration_ms: int = Field(default=0, ge=0, le=86_400_000, description='复盘用时毫秒')
    summary: str | None = Field(None, max_length=100_000, description='当时做题的错误思路')
    review_data: dict[str, Any] = Field(
        default_factory=dict,
        description='正确思路等结构化内容，约定键 prevention=正确的解题步骤',
    )
    tag_ids: list[int] = Field(default_factory=list, max_length=20, description='复盘标签 ID')
    knowledge_point_ids: list[int] = Field(default_factory=list, max_length=50, description='知识点 ID')

    @model_validator(mode='after')
    def validate_content(self) -> 'CreateQuestionReviewParam':
        """校验至少一种思路，并去重复盘标签和知识点。"""
        if not has_review_thought(self.summary, self.review_data):
            raise ValueError(REVIEW_THOUGHT_REQUIRED_MESSAGE)
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


class GetWrongQuestionOutlineItem(SchemaBase):
    """答题卡只读取 ID 和章节，不携带题干、掌握度或其他列表字段。"""

    id: int = Field(description='错题状态 ID')
    section_name: str | None = Field(None, description='原试卷章节/模块名，供答题卡分组')
    module_group: str | None = Field(None, description='原试卷模块二级分类，用于章节内按题型聚拢')


class GetWrongQuestionSummaryItem(GetWrongQuestionOutlineItem):
    """列表卡片需要的摘要与状态字段。"""

    stem_preview: str = Field(max_length=161, description='去标签后的单行题干摘要，最多 160 字及省略号')
    status: WrongStateStatus = Field(description='错题当前状态')
    wrong_count: int = Field(ge=0, description='累计错误次数')
    review_count: int = Field(ge=0, description='已复盘次数')

    @model_validator(mode='before')
    @classmethod
    def build_preview(cls, data: Any) -> Any:
        """仅转换 SQL 内部题干列，避免响应再次验证时把比较符当 HTML 清除。"""
        if isinstance(data, Mapping) and '_stem' in data:
            text = ' '.join(unescape(re.sub(r'<[^>]+>', ' ', str(data['_stem'] or ''))).split())
            return {**data, 'stem_preview': f'{text[:160]}…' if len(text) > 160 else text}
        return data


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
    section_name: str | None = Field(None, description='原试卷章节/模块名（导入时记录），用于答题卡分组')
    module_group: str | None = Field(None, description='原试卷模块二级分类（导入时记录），用于章节内按题型聚拢')


class GetWrongAnswerHistoryItem(SchemaBase):
    """错题详情中的一次错误作答历史"""

    answer: Any | None = Field(None, description='当次错误答案快照')
    attempt_no: int = Field(ge=1, description='同题第几次提交')
    submitted_time: datetime = Field(description='提交时间')
    duration_ms: int | None = Field(None, ge=0, description='当次作答用时毫秒')


class GetWrongQuestionDetail(GetWrongQuestionListItem):
    """用户错题详情"""

    answer_data: Any | None = Field(None, description='权威答案')
    explanation: str | None = Field(None, description='默认解析')
    bank_name: str | None = Field(None, description='来源题库名称')
    section_name: str | None = Field(None, description='来源篇章名称')
    resolve_threshold: int = Field(ge=1, description='移出错题本还需达到的连对次数')
    materials: list[GetQuestionMaterialDetail] = Field(default_factory=list, description='题目材料')
    last_wrong_duration_ms: int | None = Field(None, ge=0, description='最近一次错误作答用时毫秒')
    wrong_answer_history: list[GetWrongAnswerHistoryItem] = Field(
        default_factory=list, description='错误作答历史，最近一次在前'
    )


class GetQuestionReviewDetail(SchemaBase):
    """错题复盘事件详情"""

    id: int = Field(description='复盘事件 ID')
    wrong_state_id: int = Field(description='错题状态 ID')
    question_id: int = Field(description='稳定题目 ID')
    source_attempt_id: int | None = Field(None, description='关联作答事实 ID')
    event_type: Literal['capture', 'review'] = Field(description='事件类型')
    duration_ms: int = Field(ge=0, description='复盘用时毫秒')
    summary: str | None = Field(None, description='当时做题的错误思路')
    review_data: dict[str, Any] = Field(
        default_factory=dict,
        description='正确思路等结构化内容，约定键 prevention=正确的解题步骤',
    )
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
    active_reviewed_count: int = Field(default=0, ge=0, description='仍在错题本中的已复盘错题数')
    pending_review_count: int = Field(ge=0, description='待复盘错题数')
    wrong_occurrence_count: int = Field(ge=0, description='累计错误发生次数')
    groups: list[ContentGroupNode] = Field(default_factory=list, description='题库或知识点分组')


class WrongReviewDistributionItem(SchemaBase):
    """复盘看板分布项"""

    id: int = Field(description='标签或知识点 ID')
    name: str = Field(description='展示名称')
    color: str | None = Field(None, description='展示颜色')
    count: int = Field(ge=0, description='出现次数')
    children: list['WrongReviewDistributionItem'] = Field(
        default_factory=list, description='有复盘记录的下级模块或考点；次数按复盘事件去重向上汇总'
    )


class GetWrongReviewDashboard(SchemaBase):
    """错因与知识点复盘看板

    分布来自用户复盘时主观选择的标签和知识点，与题目客观知识点标注不是一回事。
    """

    reviewed_count: int = Field(ge=0, description='已复盘错题数')
    active_reviewed_count: int = Field(default=0, ge=0, description='已复盘浏览入口题量，仅统计活跃错题')
    pending_review_count: int = Field(ge=0, description='待复盘错题数')
    review_event_count: int = Field(ge=0, description='统计窗口内复盘事件数')
    reason_distribution: list[WrongReviewDistributionItem] = Field(default_factory=list, description='错因分布')
    knowledge_point_distribution: list[WrongReviewDistributionItem] = Field(
        default_factory=list,
        description='知识点分布',
    )
