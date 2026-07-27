from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import Field

from backend.common.schema import SchemaBase

PracticeMode = Literal['practice', 'exam', 'mock', 'memorize', 'review', 'adaptive']


class CreatePracticeSessionParam(SchemaBase):
    """创建练习会话参数"""

    bank_id: int = Field(gt=0, description='题库稳定身份 ID')
    section_id: int | None = Field(None, gt=0, description='题库当前版本章节 ID')
    mode: PracticeMode = Field(default='practice', description='练习模式')
    limit: int | None = Field(None, ge=1, le=500, description='抽题数量上限，空则最多投递 500 题')
    shuffle: bool = Field(default=False, description='是否随机打乱题目')
    session_key: str | None = Field(None, min_length=8, max_length=64, description='客户端幂等会话标识')


class GetPracticeSessionItem(SchemaBase):
    """练习会话题目详情"""

    id: int = Field(description='会话题目 ID')
    position: int = Field(ge=0, description='题目顺序，从 0 开始')
    question_id: int = Field(description='题目稳定身份 ID')
    question_revision_id: int = Field(description='投递时固定的题目版本 ID')
    bank_item_id: int | None = Field(None, description='来源题库编排项 ID')
    max_score: Decimal = Field(ge=Decimal(0), description='本次作答满分')
    display_config: dict[str, Any] = Field(default_factory=dict, description='本次投递展示配置')
    question_type: str = Field(description='题型')
    stem: str = Field(description='题干内容')
    content_format: str = Field(description='题干内容格式')
    option_data: list[dict[str, Any]] = Field(default_factory=list, description='有序选项')
    difficulty: Decimal | None = Field(None, description='难度，范围 1-5')
    response_data: Any | None = Field(None, description='当前保存的用户答案')
    response_status: str | None = Field(None, description='当前作答状态')
    is_flagged: bool | None = Field(None, description='是否标记稍后检查')
    duration_ms: int | None = Field(None, ge=0, description='累计有效作答时长毫秒')
    save_version: int | None = Field(None, ge=0, description='自动保存乐观锁版本')


class GetPracticeSessionDetail(SchemaBase):
    """练习会话聚合详情"""

    id: int = Field(description='练习会话 ID')
    session_key: str = Field(description='对外会话标识')
    user_id: int = Field(description='答题用户 ID')
    bank_id: int = Field(description='题库稳定身份 ID')
    bank_revision_id: int = Field(description='固定的题库版本 ID')
    mode: PracticeMode = Field(description='练习模式')
    source_type: str = Field(description='组题来源类型')
    source_ref: str | None = Field(None, description='组题来源稳定引用')
    title_snapshot: str | None = Field(None, description='会话标题快照')
    status: str = Field(description='会话状态')
    started_time: datetime = Field(description='开始时间')
    submitted_time: datetime | None = Field(None, description='交卷时间')
    expires_time: datetime | None = Field(None, description='会话过期时间')
    total_items: int = Field(ge=0, description='投递题数')
    answered_items: int = Field(ge=0, description='已答题数')
    correct_items: int = Field(ge=0, description='答对题数')
    score: Decimal = Field(ge=Decimal(0), description='当前得分')
    delivery_config: dict[str, Any] = Field(default_factory=dict, description='投递参数快照')
    source_snapshot: dict[str, Any] = Field(default_factory=dict, description='组题来源快照')
    items: list[GetPracticeSessionItem] = Field(default_factory=list, description='投递题目，不含标准答案与解析')
    created_time: datetime = Field(description='创建时间')
    updated_time: datetime | None = Field(None, description='更新时间')


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


class SubmitPracticeItemResult(SchemaBase):
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
    language: str = Field(description='内容语言')
    is_default: bool = Field(description='是否默认解析')


class GetPracticeSolutionDetail(SchemaBase):
    """已提交题目的答案解析"""

    session_item_id: int = Field(description='会话题目 ID')
    question_id: int = Field(description='题目稳定身份 ID')
    question_revision_id: int = Field(description='本次投递的题目版本 ID')
    answer_data: dict[str, Any] = Field(description='结构化标准答案')
    grading_method: str = Field(description='标准判分方式')
    grading_config: dict[str, Any] = Field(default_factory=dict, description='判分配置')
    explanations: list[PracticeExplanationDetail] = Field(default_factory=list, description='已发布解析')


class SubmitPracticeSessionResult(SchemaBase):
    """练习会话交卷结果"""

    session_key: str = Field(description='会话标识')
    status: str = Field(description='交卷后会话状态')
    total_items: int = Field(ge=0, description='投递题数')
    answered_items: int = Field(ge=0, description='已提交题数')
    correct_items: int = Field(ge=0, description='答对题数')
    score: Decimal = Field(ge=Decimal(0), description='当前总得分')
    submitted_time: datetime = Field(description='交卷时间')
