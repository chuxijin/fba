from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import Field, model_validator

from backend.app.question_bank_v2.schema.material import (
    GetDeliveredMaterialDetail,
    GetQuestionInteractionDetail,
    GetQuestionMaterialReference,
)
from backend.app.question_bank_v2.schema.question import QuestionType
from backend.common.pagination import CursorPageData
from backend.common.schema import SchemaBase

PracticeMode = Literal['practice', 'exam', 'mock', 'memorize', 'review', 'adaptive']
PracticeSourceType = Literal['bank', 'wrong', 'favorite', 'note', 'custom']
PracticeSessionStatus = Literal['created', 'in_progress', 'submitted', 'graded', 'expired', 'cancelled']
PracticeAnswerCardStatus = Literal['correct', 'wrong', 'pending', 'unanswered']
#: 会话历史的时间范围筛选（按创建时间倒推）
PracticeSessionRange = Literal['all', '7d', '30d', '90d']
PRACTICE_SESSION_RANGE_DAYS: dict[str, int] = {'7d': 7, '30d': 30, '90d': 90}

#: 会套用限时的练习模式；其余模式即使题库版本配了时长也不设过期时间
TIMED_PRACTICE_MODES: frozenset[str] = frozenset({'exam', 'mock'})


class PracticeModuleQuota(SchemaBase):
    """效果检测组卷的模块配额，同题只能占一个模块名额。"""

    knowledge_point_id: int = Field(gt=0, description='模块知识点 ID，包含其后代')
    count: int = Field(ge=1, le=500, description='模块题量')


class CreatePracticeSessionParam(SchemaBase):
    """创建练习会话参数"""

    source_type: PracticeSourceType = Field(default='bank', description='组题来源类型')
    bank_id: int | None = Field(None, gt=0, description='题库稳定身份 ID；题库来源必填，其他来源可用于筛选')
    section_id: int | None = Field(None, gt=0, description='题库当前版本章节 ID')
    favorite_folder_id: int | None = Field(None, gt=0, description='收藏来源的收藏夹 ID')
    question_ids: list[int] = Field(default_factory=list, max_length=500, description='指定题目来源的稳定题目 ID')
    knowledge_system_id: int | None = Field(
        None,
        gt=0,
        description='知识体系 ID；空则按用户偏好回落到该领域 default 体系',
    )
    knowledge_point_ids: list[int] = Field(
        default_factory=list,
        max_length=100,
        description='知识点 ID，默认包含其后代节点；必须属于同一知识体系；custom 来源可仅按知识点组题',
    )
    include_knowledge_descendants: bool = Field(default=True, description='是否包含所选知识点的后代节点')
    question_types: list[QuestionType] = Field(default_factory=list, max_length=7, description='允许投递的题型')
    year_start: int | None = Field(None, ge=1900, le=2100, description='试题起始年份')
    year_end: int | None = Field(None, ge=1900, le=2100, description='试题结束年份')
    region: str | None = Field(None, max_length=100, description='地区关键字，模糊匹配题库名称、编码和描述')
    mode: PracticeMode = Field(default='practice', description='练习模式')
    annotations_enabled: bool = Field(default=True, description='入口标注开关；临时自选重练关闭，其他场景规则优先')
    duration_minutes: int | None = Field(
        None,
        gt=0,
        le=600,
        description='本场限时分钟数，仅 exam / mock 模式生效；空则沿用题库版本时长',
    )
    limit: int | None = Field(None, ge=1, le=500, description='抽题数量上限，空则最多投递 500 题')
    shuffle: bool = Field(default=False, description='是否随机打乱题目')
    title: str | None = Field(None, min_length=1, max_length=255, description='自由组题会话标题')
    session_key: str | None = Field(None, min_length=8, max_length=64, description='客户端幂等会话标识')
    module_quotas: list[PracticeModuleQuota] = Field(
        default_factory=list, max_length=30, description='按模块精确配额组卷'
    )
    selection_strategy: Literal['default', 'high_error'] = Field(
        default='default', description='普通抽题或平台高频易错'
    )
    paper_profile: Literal['kaoyan_politics'] | None = Field(
        None, description='考研政治客观卷：16道单选各1分、17道多选各2分；考试限时45分钟'
    )

    def _normalize_paper_profile(self) -> None:
        """固定卷型由服务端约束，不接受客户端自定题量和分值。"""
        if self.paper_profile is None:
            return
        if (
            self.source_type != 'custom'
            or not self.knowledge_point_ids
            or self.question_ids
            or self.bank_id is not None
            or self.section_id is not None
            or self.module_quotas
            or self.selection_strategy != 'default'
            or self.question_types
            or self.mode not in {'practice', 'exam'}
            or not self.include_knowledge_descendants
        ):
            raise ValueError('考研政治组卷仅支持按知识点范围练习或考试，不可叠加其他组卷策略')
        if self.limit not in {None, 33}:
            raise ValueError('考研政治组卷固定33题')
        if self.duration_minutes is not None and (self.mode != 'exam' or self.duration_minutes != 45):
            raise ValueError('考研政治考试限时45分钟，普通练习不限时')
        self.limit = 33
        self.duration_minutes = 45 if self.mode == 'exam' else None
        self.shuffle = True

    def _normalize_selection(self) -> None:
        """校验快捷入口策略，配额可以补齐知识点范围。"""
        if self.module_quotas:
            ids = [item.knowledge_point_id for item in self.module_quotas]
            if len(ids) != len(set(ids)):
                raise ValueError('模块不能重复')
            if (
                self.source_type != 'custom'
                or self.question_ids
                or self.selection_strategy != 'default'
                or self.section_id
            ):
                raise ValueError('模块配额仅适用于知识点自由组卷')
            if self.knowledge_point_ids and self.knowledge_point_ids != sorted(ids):
                raise ValueError('模块配额必须与所选知识点一致')
            if not self.include_knowledge_descendants:
                raise ValueError('模块配额需包含后代知识点')
            self.knowledge_point_ids = sorted(ids)
            total = sum(item.count for item in self.module_quotas)
            if total > 500 or self.limit != total:
                raise ValueError('模块题量之和必须等于总题数，且不超过500题')
        if self.selection_strategy == 'high_error' and (
            self.source_type != 'custom' or self.question_ids or not self.knowledge_point_ids
        ):
            raise ValueError('高频易错必须指定知识点范围')

    @model_validator(mode='after')
    def normalize_filters(self) -> 'CreatePracticeSessionParam':
        """规范化组合筛选条件并拒绝反向年份区间"""
        self.knowledge_point_ids = sorted(set(self.knowledge_point_ids))
        self.question_ids = list(dict.fromkeys(self.question_ids))
        self.question_types = sorted(set(self.question_types))
        self._normalize_selection()
        self._normalize_paper_profile()
        if any(item <= 0 for item in self.knowledge_point_ids):
            raise ValueError('知识点 ID 必须大于 0')
        if any(item <= 0 for item in self.question_ids):
            raise ValueError('题目 ID 必须大于 0')
        if self.year_start is not None and self.year_end is not None and self.year_start > self.year_end:
            raise ValueError('起始年份不能大于结束年份')
        if self.source_type == 'bank' and self.bank_id is None:
            raise ValueError('题库来源必须提供 bank_id')
        if self.section_id is not None and self.bank_id is None:
            raise ValueError('按篇章筛选必须提供 bank_id')
        if self.favorite_folder_id is not None and self.source_type != 'favorite':
            raise ValueError('favorite_folder_id 仅适用于收藏来源')
        if self.source_type == 'custom' and not self.question_ids and not self.knowledge_point_ids:
            raise ValueError('自由组题必须提供 question_ids 或 knowledge_point_ids')
        if self.source_type != 'custom' and self.question_ids:
            raise ValueError('question_ids 仅适用于指定题目来源')
        if self.knowledge_system_id is not None and not self.knowledge_point_ids:
            raise ValueError('knowledge_system_id 仅在按知识点组题时有效')
        return self


class GetPracticeSessionItem(SchemaBase):
    """练习会话题目详情"""

    id: int = Field(description='会话题目 ID')
    position: int = Field(ge=0, description='题目顺序，从 0 开始')
    question_id: int = Field(description='题目稳定身份 ID')
    bank_item_id: int | None = Field(None, description='来源题库编排项 ID')
    section_id: int | None = Field(None, description='来源章节 ID')
    section_name: str | None = Field(None, description='来源章节名称')
    exam_year: int | None = Field(None, description='试题年份')
    max_score: Decimal | None = Field(ge=Decimal(0), description='本次作答满分；导入来源未提供时为空')
    display_config: dict[str, Any] = Field(default_factory=dict, description='本次投递展示配置')
    question_type: str = Field(description='题型')
    stem: str = Field(description='题干内容')
    content_format: str = Field(description='题干内容格式')
    option_data: list[dict[str, Any]] = Field(default_factory=list, description='有序选项')
    difficulty: Decimal | None = Field(None, description='难度，范围 1-5')
    materials: list[GetQuestionMaterialReference] = Field(default_factory=list, description='题目使用的材料引用')
    interactions: list[GetQuestionInteractionDetail] = Field(default_factory=list, description='题目交互定义和候选锚点')
    response_data: Any | None = Field(None, description='当前保存的用户答案')
    response_status: str | None = Field(None, description='当前作答状态')
    is_correct: bool | None = Field(None, description='当前提交判定结果')
    score: Decimal | None = Field(None, ge=0, description='当前提交得分')
    is_flagged: bool | None = Field(None, description='是否标记稍后检查')
    duration_ms: int | None = Field(None, ge=0, description='累计有效作答时长毫秒')
    save_version: int | None = Field(None, ge=0, description='自动保存乐观锁版本')
    latest_attempt_id: int | None = Field(None, description='本题最新作答事实ID，AI判分使用，不能用会话题目ID代替')


class CreateRecallSessionParam(CreatePracticeSessionParam):
    """仅供服务端到期队列使用，不放宽普通创建接口的500题限制。"""

    question_ids: list[int] = Field(default_factory=list)
    limit: int | None = Field(None, ge=1)


class GetPracticeSessionDetail(SchemaBase):
    """练习会话聚合详情"""

    id: int = Field(description='练习会话 ID')
    session_key: str = Field(description='对外会话标识')
    user_id: int = Field(description='答题用户 ID')
    bank_id: int | None = Field(None, description='题库稳定身份 ID；自由组题时为空')
    bank_revision_id: int | None = Field(None, description='固定的题库版本 ID；自由组题时为空')
    mode: PracticeMode = Field(description='练习模式')
    source_type: str = Field(description='组题来源类型')
    source_ref: str | None = Field(None, description='组题来源稳定引用')
    title_snapshot: str | None = Field(None, description='会话标题快照')
    status: str = Field(description='会话状态')
    started_time: datetime | None = Field(description='实际开始时间；仅有日期的导入记录为空')
    practiced_at: date | None = None
    submitted_time: datetime | None = Field(None, description='交卷时间')
    expires_time: datetime | None = Field(None, description='会话过期时间')
    total_items: int = Field(ge=0, description='投递题数')
    answered_items: int = Field(ge=0, description='已答题数')
    correct_items: int = Field(ge=0, description='答对题数')
    score: Decimal | None = Field(ge=Decimal(0), description='当前得分；导入来源未提供时为空')
    delivery_config: dict[str, Any] = Field(default_factory=dict, description='投递参数快照')
    source_snapshot: dict[str, Any] = Field(default_factory=dict, description='组题来源快照')
    materials: list[GetDeliveredMaterialDetail] = Field(default_factory=list, description='本次会话去重后的材料内容')
    items: list[GetPracticeSessionItem] = Field(default_factory=list, description='投递题目，不含标准答案与解析')
    created_time: datetime = Field(description='创建时间')
    updated_time: datetime | None = Field(None, description='更新时间')
    recall_remaining: int | None = Field(None, ge=0, description='消息截止时已到期、尚未提交的题数，包含当前未答题')


class GetPracticeSessionListItem(SchemaBase):
    """练习会话历史列表项"""

    id: int = Field(description='练习会话 ID')
    session_key: str = Field(description='对外会话标识')
    bank_id: int | None = Field(None, description='题库稳定身份 ID；自由组题时为空')
    bank_revision_id: int | None = Field(None, description='固定题库版本 ID；自由组题时为空')
    mode: PracticeMode = Field(description='练习模式')
    source_type: str = Field(description='组题来源类型')
    source_ref: str | None = Field(None, description='组题来源稳定引用')
    title_snapshot: str | None = Field(None, description='会话标题快照')
    status: PracticeSessionStatus = Field(description='会话状态')
    total_items: int = Field(ge=0, description='投递题数')
    answered_items: int = Field(ge=0, description='已提交题数')
    graded_items: int = Field(ge=0, description='已判题数')
    correct_items: int = Field(ge=0, description='答对题数')
    wrong_items: int = Field(ge=0, description='答错题数')
    accuracy_rate: Decimal = Field(ge=0, le=1, description='已判题正确率')
    score: Decimal = Field(ge=0, description='当前得分')
    total_score: Decimal = Field(ge=0, description='整场满分')
    total_duration_ms: int = Field(ge=0, description='累计有效作答时长毫秒')
    delivery_config: dict[str, Any] = Field(default_factory=dict, description='投递参数快照')
    source_snapshot: dict[str, Any] = Field(default_factory=dict, description='来源快照')
    started_time: datetime = Field(description='开始时间')
    submitted_time: datetime | None = Field(None, description='交卷时间')
    expires_time: datetime | None = Field(None, description='过期时间')
    created_time: datetime = Field(description='创建时间')
    updated_time: datetime | None = Field(None, description='更新时间')


class GetPracticeSessionListPage(CursorPageData[GetPracticeSessionListItem]):
    """练习会话历史分页

    会话历史是会被不断插入的流水（每开一场练习就新增一条，用户还能左滑删除），
    所以沿用游标翻页，不用页码分页的 offset（否则翻页会出现重复/漏项）。

    total 只在首页（不传 cursor）返回：列表头要显示真实条数，但没必要每次翻页都 count。
    """

    total: int | None = Field(None, description='当前筛选条件下的记录总数；仅首页返回')


class SavePracticeResponseParam(SchemaBase):
    """自动保存题目作答参数"""

    response_data: Any | None = Field(description='当前用户答案，必须是 JSON 兼容数据')
    is_flagged: bool = Field(default=False, description='是否标记稍后检查')
    duration_ms: int = Field(default=0, ge=0, le=86_400_000, description='本题累计有效作答时长毫秒')
    save_version: int = Field(default=0, ge=0, description='客户端持有的乐观锁版本，首次保存为 0')


class GetPracticeResponseDetail(SchemaBase):
    """题目作答草稿详情"""

    session_item_id: int = Field(description='会话题目 ID')
    response_data: Any | None = Field(description='当前用户答案')
    status: str = Field(description='当前作答状态')
    is_flagged: bool = Field(description='是否标记稍后检查')
    duration_ms: int = Field(ge=0, description='累计有效作答时长毫秒')
    save_version: int = Field(ge=0, description='服务端最新乐观锁版本')
    is_correct: bool | None = Field(None, description='当前提交是否正确')
    score: Decimal | None = Field(None, ge=Decimal(0), description='当前提交得分')
    grading_status: str = Field(description='当前判分状态')
    last_saved_time: datetime | None = Field(None, description='最近保存时间')
    last_submitted_time: datetime | None = Field(None, description='最近提交时间')


class SubmitPracticeItemParam(SchemaBase):
    """提交单题答案参数"""

    response_data: Any = Field(description='本次提交的用户答案，必须是 JSON 兼容数据')
    duration_ms: int = Field(default=0, ge=0, le=86_400_000, description='本题累计有效作答时长毫秒')
    save_version: int | None = Field(None, ge=0, description='客户端持有的乐观锁版本，空则不校验')
    submission_key: str | None = Field(
        None, min_length=1, max_length=128, description='单次作答幂等键，网络重试必须复用'
    )


class PracticeQuestionStatistics(SchemaBase):
    """次数口径，比例统一为0到1；无已判样本时不伪装为0%。"""

    correct_rate: Decimal | None = Field(None, description='全站正确次数 / 已判次数，0到1')
    graded_count: int = Field(0, ge=0, description='已判样本次数')
    attempt_count: int = Field(0, ge=0, description='有效作答次数')
    option_select_stats: dict[str, int] = Field(default_factory=dict, description='每个选项的选择次数，多选拆分计数')


class PracticeQuestionStatisticsDetail(PracticeQuestionStatistics):
    """点击选择数据读取的详情，平均用时仅采用1秒至5分钟的在线有效作答。"""

    avg_duration_ms: Decimal | None = Field(None, ge=0, description='过滤后的平均用时毫秒，无样本为空')
    duration_sample_count: int = Field(0, ge=0, description='纳入平均用时的有效样本次数')
    duration_min_ms: int = Field(1_000, description='用时样本下限，含边界')
    duration_max_ms: int = Field(300_000, description='用时样本上限，含边界')


class SubmitPracticeItemResult(PracticeQuestionStatistics):
    """单题提交与判分结果"""

    attempt_id: int = Field(description='本次不可变作答事实 ID')
    attempt_no: int = Field(gt=0, description='此会话题目的提交次数')
    session_item_id: int = Field(description='会话题目 ID')
    grading_status: str = Field(description='判分状态')
    grading_method: str = Field(description='实际判分方式')
    is_correct: bool | None = Field(None, description='是否正确，待人工或 AI 判分时为空')
    score: Decimal | None = Field(None, ge=Decimal(0), description='本次得分')
    max_score: Decimal = Field(ge=Decimal(0), description='本题满分')
    response_status: str = Field(description='当前作答状态')
    save_version: int = Field(ge=0, description='服务端最新乐观锁版本')


class PracticeExplanationDetail(SchemaBase):
    """练习解析详情"""

    content: str = Field(description='解析内容')
    explanation_type: str = Field(description='解析类型')
    is_default: bool = Field(description='是否默认解析')


class GetPracticeSolutionDetail(PracticeQuestionStatistics):
    """已提交题目的答案解析"""

    session_item_id: int = Field(description='会话题目 ID')
    question_id: int = Field(description='题目稳定身份 ID')
    answer_data: dict[str, Any] | None = Field(description='结构化标准答案；导入缺失时为空')
    grading_method: str | None = Field(description='标准判分方式')
    grading_config: dict[str, Any] = Field(default_factory=dict, description='判分配置')
    explanations: list[PracticeExplanationDetail] = Field(default_factory=list, description='已发布解析')
    memory_feedback: dict[str, Any] | None = Field(None, description='回测评分与下次时间，仅提交后返回')
    review_archive: dict[str, Any] | None = Field(None, description='回测提交后用于对照的原复盘')


class ConfirmMemoryFeedbackParam(SchemaBase):
    rating: Literal[1, 2, 3, 4] = Field(description='Again/Hard/Good/Easy；同作答仅确认一次')


class SubmitPracticeSessionResult(SchemaBase):
    """练习会话交卷结果"""

    session_key: str = Field(description='会话标识')
    status: str = Field(description='交卷后会话状态')
    total_items: int = Field(ge=0, description='投递题数')
    answered_items: int = Field(ge=0, description='已提交题数')
    correct_items: int = Field(ge=0, description='答对题数')
    score: Decimal = Field(ge=Decimal(0), description='当前总得分')
    submitted_time: datetime = Field(description='交卷时间')
    reward_exp: int = Field(0, ge=0, description='本次奖励经验合计')
    practice_reward_exp: int = Field(0, ge=0, description='本次答题奖励经验')
    check_in_reward_exp: int = Field(0, ge=0, description='本次自动签到奖励经验')
    tier_grade: int | None = Field(None, description='发放后的成长等级')
    exp: int | None = Field(None, description='发放后的累计经验')
    available_exp: int | None = Field(None, description='发放后的可用经验')
    is_auto_checked_in: bool = Field(False, description='本次是否触发自动签到')
    check_in_streak: int | None = Field(None, description='自动签到后的连续签到天数')


class PracticeReportItem(SchemaBase):
    """整场报告答题卡项"""

    session_item_id: int = Field(description='会话题目 ID')
    position: int = Field(ge=0, description='题目顺序，从 0 开始')
    question_id: int = Field(description='题目稳定身份 ID')
    bank_item_id: int | None = Field(None, description='来源题库编排项 ID')
    section_id: int | None = Field(None, description='来源章节 ID')
    section_name: str | None = Field(None, description='来源章节名称')
    status: PracticeAnswerCardStatus = Field(description='答题卡状态')
    duration_ms: int | None = Field(ge=0, description='累计有效作答时长毫秒，导入未知时为空')
    score: Decimal | None = Field(None, ge=0, description='本题得分')
    max_score: Decimal | None = Field(ge=0, description='本题满分，导入未知时为空')


class GetPracticeSessionReport(SchemaBase):
    """整场练习结果报告"""

    session_id: int = Field(description='练习会话 ID')
    session_key: str = Field(description='会话标识')
    bank_id: int | None = Field(None, description='题库稳定身份 ID；自由组题时为空')
    mode: PracticeMode = Field(description='练习模式')
    source_type: str = Field(description='组题来源类型')
    title_snapshot: str | None = Field(None, description='会话标题快照')
    status: PracticeSessionStatus = Field(description='会话状态')
    total_items: int = Field(ge=0, description='总题数')
    answered_items: int = Field(ge=0, description='已提交题数')
    graded_items: int = Field(ge=0, description='已判题数')
    correct_items: int = Field(ge=0, description='答对题数')
    wrong_items: int = Field(ge=0, description='答错题数')
    pending_items: int = Field(ge=0, description='已提交待判题数')
    unanswered_items: int = Field(ge=0, description='未答题数')
    accuracy_rate: Decimal = Field(ge=0, le=1, description='已判题正确率')
    score: Decimal | None = Field(ge=0, description='当前总得分')
    total_score: Decimal | None = Field(ge=0, description='整场满分')
    total_duration_ms: int | None = Field(ge=0, description='累计有效作答时长毫秒')
    started_time: datetime | None = Field(description='实际开始时间；导入仅有日期时为空')
    practiced_at: date | None = None
    accuracy_basis: Literal['graded_questions', 'all_questions'] = 'graded_questions'
    source_snapshot: dict[str, Any] = Field(default_factory=dict)
    submitted_time: datetime | None = Field(None, description='交卷时间')
    items: list[PracticeReportItem] = Field(default_factory=list, description='答题卡')
    wrong_question_ids: list[int] = Field(default_factory=list, description='错题稳定身份 ID')


class GetPracticeSessionSolutionItem(PracticeQuestionStatistics):
    """整卷答案解析项"""

    session_item_id: int = Field(description='会话题目 ID')
    position: int = Field(ge=0, description='题目顺序，从 0 开始')
    question_id: int = Field(description='题目稳定身份 ID')
    response_data: Any | None = Field(None, description='用户最终答案')
    is_correct: bool | None = Field(None, description='是否正确')
    score: Decimal | None = Field(None, ge=0, description='本题得分')
    max_score: Decimal | None = Field(ge=0, description='本题满分')
    grading_status: str | None = Field(None, description='判分状态')
    answer_data: dict[str, Any] | None = Field(description='结构化标准答案；导入缺失时为空')
    grading_method: str | None = Field(description='标准判分方式')
    grading_config: dict[str, Any] = Field(default_factory=dict, description='判分配置')
    explanations: list[PracticeExplanationDetail] = Field(default_factory=list, description='已发布解析')
