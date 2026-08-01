from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import ConfigDict, Field, model_validator

from backend.common.schema import SchemaBase

MaterialContentFormat = Literal['html', 'markdown', 'plain', 'json']
MaterialStatus = Literal['active', 'disabled', 'archived']
MaterialRevisionStatus = Literal['draft', 'published', 'retired']
QuestionMaterialRole = Literal['passage', 'prompt', 'reference', 'attachment']
MaterialAnchorType = Literal['text_range', 'text_block', 'image_region', 'image_point', 'table_cell']
MaterialAnchorSource = Literal['manual', 'ocr', 'ai', 'import']
MaterialAnchorStatus = Literal['draft', 'active', 'retired']
InteractionSelectionMode = Literal['single', 'multiple', 'multi_role']
InteractionStatus = Literal['draft', 'active', 'retired']


class MaterialRevisionSchemaBase(SchemaBase):
    """材料版本内容基础模型"""

    title: str = Field(min_length=1, max_length=255, description='材料标题')
    content: str = Field(min_length=1, max_length=4_000_000, description='材料正文')
    content_format: MaterialContentFormat = Field(default='html', description='正文格式')
    structured_data: dict[str, Any] = Field(default_factory=dict, description='OCR 块、表格等结构化数据')
    source_name: str | None = Field(None, max_length=255, description='材料来源名称')
    source_url: str | None = Field(None, max_length=1024, description='材料来源地址')


class CreateMaterialRevisionParam(MaterialRevisionSchemaBase):
    """创建材料草稿版本参数"""


class UpdateMaterialRevisionParam(SchemaBase):
    """更新材料草稿版本参数"""

    title: str | None = Field(None, min_length=1, max_length=255, description='材料标题')
    content: str | None = Field(None, min_length=1, max_length=4_000_000, description='材料正文')
    content_format: MaterialContentFormat | None = Field(None, description='正文格式')
    structured_data: dict[str, Any] | None = Field(None, description='OCR 块、表格等结构化数据')
    source_name: str | None = Field(None, max_length=255, description='材料来源名称')
    source_url: str | None = Field(None, max_length=1024, description='材料来源地址')


class CreateMaterialParam(SchemaBase):
    """创建材料及首个草稿版本参数"""

    code: str = Field(
        min_length=1,
        max_length=64,
        pattern=r'^[A-Za-z0-9][A-Za-z0-9_.-]*$',
        description='稳定业务编码',
    )
    status: MaterialStatus = Field(default='active', description='材料身份状态')
    revision: CreateMaterialRevisionParam = Field(description='首个草稿版本')


class UpdateMaterialParam(SchemaBase):
    """更新材料稳定身份参数"""

    code: str | None = Field(
        None,
        min_length=1,
        max_length=64,
        pattern=r'^[A-Za-z0-9][A-Za-z0-9_.-]*$',
        description='稳定业务编码',
    )
    status: MaterialStatus | None = Field(None, description='材料身份状态')


class QuestionMaterialParam(SchemaBase):
    """题目版本材料关联参数"""

    material_id: int = Field(gt=0, description='材料稳定身份 ID')
    material_revision_id: int = Field(gt=0, description='固定材料版本 ID')
    role: QuestionMaterialRole = Field(default='passage', description='材料在题目中的用途')
    sort_order: int = Field(default=0, ge=0, description='材料展示顺序')
    display_config: dict[str, Any] = Field(default_factory=dict, description='折叠、节选等展示配置')


class GetQuestionMaterialDetail(QuestionMaterialParam):
    """题目版本材料详情"""

    id: int = Field(description='题目材料关联 ID')
    question_id: int = Field(description='题目稳定身份 ID')
    material_status: MaterialStatus = Field(description='材料身份状态')
    revision_status: MaterialRevisionStatus = Field(description='材料版本状态')
    title: str = Field(description='材料标题')
    content: str = Field(description='材料正文')
    content_format: MaterialContentFormat = Field(description='正文格式')
    structured_data: dict[str, Any] = Field(default_factory=dict, description='结构化材料数据')
    source_name: str | None = Field(None, description='材料来源名称')
    source_url: str | None = Field(None, description='材料来源地址')
    content_hash: str | None = Field(None, description='材料版本内容 SHA-256')


class GetQuestionMaterialReference(QuestionMaterialParam):
    """练习题目中的轻量材料引用"""

    id: int = Field(description='题目材料关联 ID')
    question_id: int = Field(description='题目稳定身份 ID')


class GetDeliveredMaterialDetail(SchemaBase):
    """练习会话中去重后的材料内容"""

    material_id: int = Field(description='材料稳定身份 ID')
    material_revision_id: int = Field(description='固定材料版本 ID')
    title: str = Field(description='材料标题')
    content: str = Field(description='材料正文')
    content_format: MaterialContentFormat = Field(description='正文格式')
    structured_data: dict[str, Any] = Field(default_factory=dict, description='结构化材料数据')
    source_name: str | None = Field(None, description='材料来源名称')
    source_url: str | None = Field(None, description='材料来源地址')
    content_hash: str | None = Field(None, description='材料版本内容 SHA-256')


class GetMaterialRevisionDetail(MaterialRevisionSchemaBase):
    """材料版本详情"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='材料版本 ID')
    material_id: int = Field(description='材料稳定身份 ID')
    revision_no: int = Field(description='材料版本号')
    content_hash: str | None = Field(None, description='规范化内容 SHA-256')
    status: MaterialRevisionStatus = Field(description='版本状态')
    published_by: int | None = Field(None, description='发布人 ID')
    published_time: datetime | None = Field(None, description='发布时间')
    created_by: int = Field(description='创建者 ID')
    updated_by: int | None = Field(None, description='修改者 ID')
    created_time: datetime = Field(description='创建时间')
    updated_time: datetime | None = Field(None, description='更新时间')


class GetMaterialDetail(SchemaBase):
    """材料聚合详情"""

    id: int = Field(description='材料稳定身份 ID')
    code: str = Field(description='稳定业务编码')
    current_revision_id: int | None = Field(None, description='当前发布版本 ID')
    status: MaterialStatus = Field(description='材料身份状态')
    revision: GetMaterialRevisionDetail | None = Field(None, description='请求的材料版本')
    created_by: int = Field(description='创建者 ID')
    updated_by: int | None = Field(None, description='修改者 ID')
    created_time: datetime = Field(description='创建时间')
    updated_time: datetime | None = Field(None, description='更新时间')


class GetMaterialListItem(SchemaBase):
    """材料管理列表项"""

    id: int = Field(description='材料稳定身份 ID')
    code: str = Field(description='稳定业务编码')
    status: MaterialStatus = Field(description='材料身份状态')
    revision_id: int = Field(description='最近材料版本 ID')
    revision_no: int = Field(description='最近材料版本号')
    revision_status: MaterialRevisionStatus = Field(description='最近版本状态')
    title: str = Field(description='材料标题')
    content_format: MaterialContentFormat = Field(description='正文格式')
    source_name: str | None = Field(None, description='材料来源名称')
    updated_time: datetime | None = Field(None, description='最近更新时间')


class MaterialAnchorSchemaBase(SchemaBase):
    """材料版本锚点基础模型"""

    anchor_key: str = Field(min_length=1, max_length=128, description='材料版本内稳定锚点键')
    anchor_type: MaterialAnchorType = Field(description='锚点类型')
    text: str | None = Field(None, max_length=100_000, description='锚点文本快照')
    semantic_role: str | None = Field(None, max_length=64, description='锚点语义角色')
    block_id: str | None = Field(None, max_length=128, description='材料结构块 ID')
    start_offset: int | None = Field(None, ge=0, description='文本起始偏移')
    end_offset: int | None = Field(None, gt=0, description='文本结束偏移')
    asset_id: int | None = Field(None, gt=0, description='图片或页面资产 ID')
    bbox: dict[str, Any] | None = Field(None, description='归一化矩形区域')
    polygon: list[dict[str, Any]] | None = Field(None, max_length=100, description='归一化多边形区域')
    table_cell: dict[str, Any] | None = Field(None, description='表格行列定位')
    source: MaterialAnchorSource = Field(default='manual', description='锚点产生方式')
    confidence: Decimal | None = Field(None, ge=0, le=1, description='OCR 或 AI 置信度')
    status: MaterialAnchorStatus = Field(default='draft', description='锚点状态')
    extra_data: dict[str, Any] = Field(default_factory=dict, description='锚点类型扩展数据')

    @model_validator(mode='after')
    def validate_locator(self) -> 'MaterialAnchorSchemaBase':
        """校验文本偏移成对出现且范围有效"""
        if (self.start_offset is None) != (self.end_offset is None):
            raise ValueError('文本起止偏移必须同时提供')
        if self.start_offset is not None and self.end_offset is not None and self.end_offset <= self.start_offset:
            raise ValueError('文本结束偏移必须大于起始偏移')
        return self


class CreateMaterialAnchorParam(MaterialAnchorSchemaBase):
    """创建材料锚点参数"""


class UpdateMaterialAnchorParam(SchemaBase):
    """更新材料锚点参数"""

    anchor_key: str | None = Field(None, min_length=1, max_length=128, description='材料版本内稳定锚点键')
    anchor_type: MaterialAnchorType | None = Field(None, description='锚点类型')
    text: str | None = Field(None, description='锚点文本快照')
    semantic_role: str | None = Field(None, max_length=64, description='锚点语义角色')
    block_id: str | None = Field(None, max_length=128, description='材料结构块 ID')
    start_offset: int | None = Field(None, ge=0, description='文本起始偏移')
    end_offset: int | None = Field(None, gt=0, description='文本结束偏移')
    asset_id: int | None = Field(None, gt=0, description='图片或页面资产 ID')
    bbox: dict[str, Any] | None = Field(None, description='归一化矩形区域')
    polygon: list[dict[str, Any]] | None = Field(None, description='归一化多边形区域')
    table_cell: dict[str, Any] | None = Field(None, description='表格行列定位')
    source: MaterialAnchorSource | None = Field(None, description='锚点产生方式')
    confidence: Decimal | None = Field(None, ge=0, le=1, description='OCR 或 AI 置信度')
    status: MaterialAnchorStatus | None = Field(None, description='锚点状态')
    extra_data: dict[str, Any] | None = Field(None, description='锚点类型扩展数据')


class GetMaterialAnchorDetail(MaterialAnchorSchemaBase):
    """材料锚点详情"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='材料锚点 ID')
    material_id: int = Field(description='材料稳定身份 ID')
    material_revision_id: int = Field(description='材料版本 ID')
    content_hash: str | None = Field(None, description='创建锚点时的材料内容哈希')


class QuestionInteractionCandidateParam(SchemaBase):
    """交互题候选锚点参数"""

    anchor_id: int = Field(gt=0, description='材料锚点 ID')
    candidate_role: str = Field(default='', max_length=64, description='候选分组或角色')
    label: str | None = Field(None, max_length=160, description='候选展示标签')
    sort_order: int = Field(default=0, ge=0, description='候选顺序')


class CreateQuestionInteractionParam(SchemaBase):
    """创建题目版本交互定义参数"""

    interaction_key: str = Field(min_length=1, max_length=128, description='题目版本内稳定交互键')
    interaction_type: str = Field(min_length=1, max_length=32, description='可扩展交互类型')
    instruction: str = Field(min_length=1, max_length=100_000, description='交互指令')
    question_material_id: int | None = Field(None, gt=0, description='题目材料关联 ID')
    title: str | None = Field(None, max_length=160, description='交互标题')
    selection_mode: InteractionSelectionMode = Field(default='single', description='选择模式')
    min_selections: int = Field(default=0, ge=0, description='最少选择数')
    max_selections: int | None = Field(None, ge=0, description='最多选择数')
    config: dict[str, Any] = Field(default_factory=dict, description='角色、显示和交互扩展配置')
    status: InteractionStatus = Field(default='draft', description='交互状态')
    candidates: list[QuestionInteractionCandidateParam] = Field(
        default_factory=list,
        max_length=500,
        description='候选锚点',
    )

    @model_validator(mode='after')
    def validate_candidates(self) -> 'CreateQuestionInteractionParam':
        """校验选择数量和候选锚点唯一性"""
        keys = [(item.anchor_id, item.candidate_role) for item in self.candidates]
        if len(keys) != len(set(keys)):
            raise ValueError('同一角色不能重复使用同一候选锚点')
        if self.question_material_id is None and self.candidates:
            raise ValueError('使用候选锚点时必须指定题目材料关联')
        if self.max_selections is not None and self.max_selections < self.min_selections:
            raise ValueError('最多选择数不能小于最少选择数')
        if self.min_selections > len(self.candidates):
            raise ValueError('最少选择数不能超过候选数量')
        if self.max_selections is not None and self.max_selections > len(self.candidates):
            raise ValueError('最多选择数不能超过候选数量')
        return self


class UpdateQuestionInteractionParam(CreateQuestionInteractionParam):
    """全量更新题目版本交互定义参数"""


class GetQuestionInteractionCandidateDetail(QuestionInteractionCandidateParam):
    """交互题候选锚点详情"""

    id: int = Field(description='候选项 ID')
    material_revision_id: int = Field(description='材料版本 ID')
    anchor: GetMaterialAnchorDetail = Field(description='候选材料锚点')


class GetQuestionInteractionDetail(SchemaBase):
    """题目版本交互定义详情"""

    id: int = Field(description='交互定义 ID')
    question_id: int = Field(description='题目稳定身份 ID')
    interaction_key: str = Field(description='题目版本内稳定交互键')
    interaction_type: str = Field(description='交互类型')
    instruction: str = Field(description='交互指令')
    question_material_id: int | None = Field(None, description='题目材料关联 ID')
    material_revision_id: int | None = Field(None, description='候选材料版本 ID')
    title: str | None = Field(None, description='交互标题')
    selection_mode: InteractionSelectionMode = Field(description='选择模式')
    min_selections: int = Field(ge=0, description='最少选择数')
    max_selections: int | None = Field(None, ge=0, description='最多选择数')
    config: dict[str, Any] = Field(default_factory=dict, description='交互扩展配置')
    status: InteractionStatus = Field(description='交互状态')
    candidates: list[GetQuestionInteractionCandidateDetail] = Field(default_factory=list, description='候选锚点')
