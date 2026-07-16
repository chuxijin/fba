#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import ConfigDict, Field

from backend.common.schema import SchemaBase

AnchorType = Literal['text_range', 'image_region', 'table_cell', 'text_block', 'image_point']
AnchorSource = Literal['manual', 'ocr', 'ai', 'import']
InteractionSelectionMode = Literal['single', 'multiple', 'multi_role']


class MaterialAnchorSchemaBase(SchemaBase):
    """材料锚点基础"""

    material_id: int = Field(ge=1, description='材料 ID')
    anchor_key: str = Field(max_length=128, description='锚点业务键')
    anchor_type: AnchorType = Field(description='锚点类型')
    text: str | None = Field(None, description='锚点文本')
    role: str | None = Field(None, max_length=64, description='锚点语义角色')
    block_id: str | None = Field(None, max_length=128, description='材料分块 ID')
    start_offset: int | None = Field(None, ge=0, description='文本起始偏移')
    end_offset: int | None = Field(None, ge=0, description='文本结束偏移')
    asset_url: str | None = Field(None, max_length=1024, description='图片或资源地址')
    asset_hash: str | None = Field(None, max_length=128, description='资源哈希')
    natural_width: int | None = Field(None, ge=1, description='资源原始宽度')
    natural_height: int | None = Field(None, ge=1, description='资源原始高度')
    bbox: dict[str, Any] | None = Field(None, description='归一化矩形区域')
    polygon: list[dict[str, Any]] | None = Field(None, description='归一化多边形区域')
    table_cell: dict[str, Any] | None = Field(None, description='表格单元格定位')
    ocr_confidence: Decimal | None = Field(None, ge=Decimal('0'), le=Decimal('1'), description='OCR 置信度')
    source: AnchorSource = Field(default='manual', description='来源')
    content_hash: str | None = Field(None, max_length=128, description='材料内容哈希')
    status: int = Field(default=10, description='状态')
    extra_data: dict[str, Any] = Field(default_factory=dict, description='扩展数据')


class CreateMaterialAnchorParam(MaterialAnchorSchemaBase):
    """创建材料锚点"""


class BatchCreateMaterialAnchorParam(SchemaBase):
    """批量创建材料锚点"""

    items: list[CreateMaterialAnchorParam] = Field(min_length=1, description='材料锚点列表')


class UpdateMaterialAnchorParam(SchemaBase):
    """更新材料锚点"""

    anchor_key: str | None = Field(None, max_length=128, description='锚点业务键')
    anchor_type: AnchorType | None = Field(None, description='锚点类型')
    text: str | None = Field(None, description='锚点文本')
    role: str | None = Field(None, max_length=64, description='锚点语义角色')
    block_id: str | None = Field(None, max_length=128, description='材料分块 ID')
    start_offset: int | None = Field(None, ge=0, description='文本起始偏移')
    end_offset: int | None = Field(None, ge=0, description='文本结束偏移')
    asset_url: str | None = Field(None, max_length=1024, description='图片或资源地址')
    asset_hash: str | None = Field(None, max_length=128, description='资源哈希')
    natural_width: int | None = Field(None, ge=1, description='资源原始宽度')
    natural_height: int | None = Field(None, ge=1, description='资源原始高度')
    bbox: dict[str, Any] | None = Field(None, description='归一化矩形区域')
    polygon: list[dict[str, Any]] | None = Field(None, description='归一化多边形区域')
    table_cell: dict[str, Any] | None = Field(None, description='表格单元格定位')
    ocr_confidence: Decimal | None = Field(None, ge=Decimal('0'), le=Decimal('1'), description='OCR 置信度')
    source: AnchorSource | None = Field(None, description='来源')
    content_hash: str | None = Field(None, max_length=128, description='材料内容哈希')
    status: int | None = Field(None, description='状态')
    extra_data: dict[str, Any] | None = Field(None, description='扩展数据')


class MaterialAnchorQueryParam(SchemaBase):
    """材料锚点查询"""

    material_id: int | None = Field(None, ge=1, description='材料 ID')
    anchor_type: AnchorType | None = Field(None, description='锚点类型')
    role: str | None = Field(None, max_length=64, description='锚点语义角色')
    status: int | None = Field(None, description='状态')


class GetMaterialAnchorDetail(MaterialAnchorSchemaBase):
    """材料锚点详情"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='锚点 ID')
    created_time: datetime = Field(description='创建时间')
    updated_time: datetime | None = Field(None, description='更新时间')


class QuestionInteractionAnnotationSchemaBase(SchemaBase):
    """题目交互标注基础"""

    question_id: int = Field(ge=1, description='题目 ID')
    material_id: int | None = Field(None, ge=1, description='材料 ID')
    annotation_key: str = Field(max_length=128, description='标注业务键')
    interaction_type: str = Field(max_length=32, description='交互类型')
    title: str | None = Field(None, max_length=128, description='标注标题')
    instruction: str = Field(description='交互指令')
    selection_mode: InteractionSelectionMode = Field(default='single', description='选择模式')
    candidate_anchor_ids: list[int] = Field(default_factory=list, description='候选锚点 ID')
    answer_data: dict[str, Any] = Field(default_factory=dict, description='答案数据')
    config: dict[str, Any] = Field(default_factory=dict, description='交互配置')
    content_hash: str | None = Field(None, max_length=128, description='材料内容哈希')
    version_no: int = Field(default=1, ge=1, description='版本号')
    is_default: bool = Field(default=True, description='是否默认使用')
    status: int = Field(default=10, description='状态')


class CreateQuestionInteractionAnnotationParam(QuestionInteractionAnnotationSchemaBase):
    """创建题目交互标注"""


class UpdateQuestionInteractionAnnotationParam(SchemaBase):
    """更新题目交互标注"""

    material_id: int | None = Field(None, ge=1, description='材料 ID')
    annotation_key: str | None = Field(None, max_length=128, description='标注业务键')
    interaction_type: str | None = Field(None, max_length=32, description='交互类型')
    title: str | None = Field(None, max_length=128, description='标注标题')
    instruction: str | None = Field(None, description='交互指令')
    selection_mode: InteractionSelectionMode | None = Field(None, description='选择模式')
    candidate_anchor_ids: list[int] | None = Field(None, description='候选锚点 ID')
    answer_data: dict[str, Any] | None = Field(None, description='答案数据')
    config: dict[str, Any] | None = Field(None, description='交互配置')
    content_hash: str | None = Field(None, max_length=128, description='材料内容哈希')
    version_no: int | None = Field(None, ge=1, description='版本号')
    is_default: bool | None = Field(None, description='是否默认使用')
    status: int | None = Field(None, description='状态')


class QuestionInteractionAnnotationQueryParam(SchemaBase):
    """题目交互标注查询"""

    question_id: int | None = Field(None, ge=1, description='题目 ID')
    material_id: int | None = Field(None, ge=1, description='材料 ID')
    interaction_type: str | None = Field(None, max_length=32, description='交互类型')
    is_default: bool | None = Field(None, description='是否默认使用')
    status: int | None = Field(None, description='状态')


class GetQuestionInteractionAnnotationDetail(QuestionInteractionAnnotationSchemaBase):
    """题目交互标注详情"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='标注 ID')
    created_time: datetime = Field(description='创建时间')
    updated_time: datetime | None = Field(None, description='更新时间')


class GetMaterialBlocksResult(SchemaBase):
    """材料分块结果"""

    material_id: int = Field(description='材料 ID')
    title: str = Field(description='材料标题')
    content_hash: str = Field(description='材料内容哈希')
    blocks: list[dict[str, Any]] = Field(default_factory=list, description='材料分块')


class GetMaterialQuestionPreview(SchemaBase):
    """材料题目预览"""

    id: int = Field(description='题目 ID')
    type: str = Field(description='题型')
    stem: str = Field(description='题干')
    options: list[dict[str, Any]] = Field(default_factory=list, description='选项列表')
    difficulty: Decimal | None = Field(None, description='难度')
    material_ids: list[int] = Field(default_factory=list, description='关联材料 ID 列表')


class DeleteInteractionIdsParam(SchemaBase):
    """删除交互数据"""

    ids: list[int] = Field(min_length=1, description='ID 列表')
