#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime

from pydantic import ConfigDict, Field

from backend.app.question_bank.schema.chapter import ChapterBankBrief
from backend.common.schema import SchemaBase


class MaterialSchemaBase(SchemaBase):
    """材料基础"""

    bank_id: int = Field(ge=1, description='题库 ID')
    title: str = Field(max_length=255, description='材料标题')
    content: str = Field(description='材料内容（富文本）')
    category_id: int | None = Field(None, ge=1, description='分类 ID')
    source: str | None = Field(None, max_length=255, description='来源')
    year: int | None = Field(None, ge=1900, le=2100, description='年份')
    sort_order: int = Field(default=0, ge=0, description='排序顺序')
    is_active: bool = Field(default=True, description='是否启用')


class GetMaterialDetail(MaterialSchemaBase):
    """材料详情"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='材料 ID')
    created_time: datetime = Field(description='创建时间')
    updated_time: datetime | None = Field(None, description='更新时间')


class GetMaterialWithRelationDetail(GetMaterialDetail):
    """材料关联详情"""

    model_config = ConfigDict(from_attributes=True)

    bank: ChapterBankBrief | None = Field(None, description='所属题库信息')
    question_count: int = Field(default=0, description='关联题目数量')


class GetMaterialListItem(SchemaBase):
    """材料列表项"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='材料 ID')
    bank_id: int = Field(description='题库 ID')
    title: str = Field(description='材料标题')
    source: str | None = Field(None, description='来源')
    year: int | None = Field(None, description='年份')
    sort_order: int = Field(description='排序顺序')
    is_active: bool = Field(description='是否启用')
    created_time: datetime = Field(description='创建时间')


class MaterialParam(SchemaBase):
    """材料查询参数"""

    bank_id: int | None = Field(None, ge=1, description='题库 ID')
    category_id: int | None = Field(None, ge=1, description='分类 ID')
    keyword: str | None = Field(None, description='关键字搜索（标题/来源）')
    is_active: bool | None = Field(None, description='是否启用')
    year: int | None = Field(None, ge=1900, le=2100, description='年份')


class CreateMaterialParam(MaterialSchemaBase):
    """创建材料参数"""


class UpdateMaterialParam(MaterialSchemaBase):
    """更新材料参数"""


class DeleteMaterialParam(SchemaBase):
    """删除材料参数"""

    ids: list[int] = Field(min_length=1, description='材料 ID 列表')


class LinkQuestionParam(SchemaBase):
    """关联题目参数"""

    question_ids: list[int] = Field(min_length=1, description='题目 ID 列表')
