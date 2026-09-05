from decimal import Decimal
from typing import Any, Literal

from pydantic import Field

from backend.common.schema import SchemaBase

LocateInteractionType = Literal['numberLocate', 'evidenceLocate', 'regionLocate', 'anchorLocate']

LOCATE_INTERACTION_TYPES: tuple[str, ...] = ('numberLocate', 'evidenceLocate', 'regionLocate', 'anchorLocate')


class CreateLocateTrainingParam(SchemaBase):
    """创建找数训练会话参数"""

    count: int = Field(default=10, ge=1, le=50, description='训练题量')


class GetLocateAnchorDetail(SchemaBase):
    """找数训练候选锚点"""

    id: int = Field(description='材料锚点 ID')
    anchor_key: str = Field(description='锚点稳定键')
    anchor_type: str = Field(description='锚点类型')
    text: str | None = Field(None, description='锚点文本快照')
    semantic_role: str | None = Field(None, description='锚点语义角色')
    block_id: str | None = Field(None, description='材料结构块 ID')
    start_offset: int | None = Field(None, description='文本起始偏移')
    end_offset: int | None = Field(None, description='文本结束偏移')
    bbox: dict[str, Any] | None = Field(None, description='归一化矩形区域')
    polygon: list[dict[str, Any]] | None = Field(None, description='归一化多边形区域')
    table_cell: dict[str, Any] | None = Field(None, description='表格行列定位')
    candidate_role: str = Field(default='', description='候选语义分组或角色')
    candidate_label: str | None = Field(None, description='候选展示标签')


class GetLocateMaterialBlockDetail(SchemaBase):
    """找数训练材料结构块"""

    id: str = Field(description='结构块 ID')
    type: str = Field(default='text', description='结构块类型')
    title: str | None = Field(None, description='结构块标题')
    content: str | None = Field(None, description='文本内容')
    asset_url: str | None = Field(None, description='图片地址')
    natural_width: float | None = Field(None, description='图片原始宽度')
    natural_height: float | None = Field(None, description='图片原始高度')


class GetLocateRoleDetail(SchemaBase):
    """找数训练角色定义"""

    key: str = Field(description='角色键')
    label: str = Field(description='角色展示名')


class GetLocateQuestionDetail(SchemaBase):
    """找数训练题目"""

    order: int = Field(ge=1, description='题目序号，从 1 开始')
    question_id: int = Field(description='题目稳定身份 ID')
    stem: str = Field(description='题干')
    instruction: str = Field(description='交互指令')
    interaction_type: LocateInteractionType = Field(description='找数交互类型')
    selection_mode: str = Field(description='选择模式')
    target_count: int = Field(ge=1, description='需要找出的目标数量')
    material_title: str | None = Field(None, description='材料标题')
    content_hash: str | None = Field(None, description='材料内容哈希')
    blocks: list[GetLocateMaterialBlockDetail] = Field(default_factory=list, description='材料结构块')
    anchors: list[GetLocateAnchorDetail] = Field(default_factory=list, description='候选锚点')
    roles: list[GetLocateRoleDetail] = Field(default_factory=list, description='多角色定义')


class GetLocateTrainingSessionDetail(SchemaBase):
    """找数训练会话详情"""

    session_key: str = Field(description='会话标识')
    count: int = Field(ge=1, description='训练题量')
    expires_in: int = Field(ge=0, description='会话剩余有效秒数')
    questions: list[GetLocateQuestionDetail] = Field(default_factory=list, description='训练题目')


class SubmitLocateClickParam(SchemaBase):
    """提交单次找数点击参数"""

    question_order: int = Field(gt=0, description='题目序号，从 1 开始')
    anchor_id: int = Field(gt=0, description='点击的候选锚点 ID')


class GetLocateClickResult(SchemaBase):
    """单次找数点击判定结果"""

    is_correct: bool = Field(description='本次点击是否命中目标锚点')
    already_found: bool = Field(default=False, description='是否为已找到锚点的重复点击')
    found_count: int = Field(ge=0, description='当前题已找到数量')
    target_count: int = Field(ge=1, description='当前题目标数量')
    question_completed: bool = Field(default=False, description='当前题是否全部找齐')
    training_completed: bool = Field(default=False, description='整组训练是否全部完成')
    question_wrong_clicks: int = Field(default=0, ge=0, description='当前题累计错误点击次数')
    total_clicks: int = Field(default=0, ge=0, description='整组累计点击次数')
    wrong_clicks: int = Field(default=0, ge=0, description='整组累计错误点击次数')


class SubmitLocateCompletionParam(SchemaBase):
    """完成找数训练补充参数（客户端行为数据）"""

    question_meta: list[dict[str, Any]] = Field(
        default_factory=list,
        description='逐题行为数据：question_order / peek_count / given_up',
    )


class GetLocateTrainingResult(SchemaBase):
    """找数训练结算结果"""

    session_key: str = Field(description='会话标识')
    question_count: int = Field(ge=0, description='训练题量')
    completed_questions: int = Field(ge=0, description='已完成题目数')
    perfect_questions: int = Field(ge=0, description='无错误点击的完成题目数')
    total_clicks: int = Field(ge=0, description='累计点击次数')
    wrong_clicks: int = Field(ge=0, description='累计错误点击次数')
    click_accuracy: Decimal = Field(ge=0, l=1, description='点击命中率')
    duration_seconds: int = Field(ge=0, description='训练用时秒数')
    given_up_questions: int = Field(default=0, ge=0, description='放弃题目数')
    peeked_questions: int = Field(default=0, ge=0, description='偷看过题目的数量')
    total_peeks: int = Field(default=0, ge=0, description='累计偷看次数')
