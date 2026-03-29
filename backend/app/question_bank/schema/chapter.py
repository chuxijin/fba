#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime
from typing import Literal

from pydantic import ConfigDict, Field

from backend.common.schema import SchemaBase


class ChapterBankBrief(SchemaBase):
    """章节关联题库摘要"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='题库 ID')
    name: str = Field(description='题库名称')
    code: str = Field(description='业务编码')


class ChapterSchemaBase(SchemaBase):
    """章节基础"""

    bank_id: int = Field(ge=1, description='题库 ID')
    name: str = Field(max_length=128, description='章节名称')
    code: str | None = Field(None, max_length=64, description='章节编码')
    level: int = Field(default=1, ge=1, description='章节层级')
    sort_order: int = Field(default=0, ge=0, description='排序权重')
    parent_id: int | None = Field(None, ge=1, description='父级章节 ID')
    status: Literal[0, 1] = Field(default=1, description='状态: 0=禁用, 1=启用')


class GetChapterDetail(ChapterSchemaBase):
    """章节详情"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='章节 ID')
    q_count_cache: int = Field(description='缓存题量')
    created_time: datetime = Field(description='创建时间')
    updated_time: datetime | None = Field(None, description='更新时间')


class GetChapterWithRelationDetail(GetChapterDetail):
    """章节关联详情"""

    model_config = ConfigDict(from_attributes=True)

    bank: ChapterBankBrief | None = Field(None, description='所属题库信息')


class GetChapterTree(GetChapterDetail):
    """章节树"""

    children: list['GetChapterTree'] = Field(default_factory=list, description='子章节')


class ChapterParam(SchemaBase):
    """章节查询参数"""

    bank_id: int = Field(ge=1, description='题库 ID')


class CreateChapterParam(ChapterSchemaBase):
    """创建章节参数"""


class UpdateChapterParam(ChapterSchemaBase):
    """更新章节参数"""


class DeleteChapterParam(SchemaBase):
    """删除章节参数"""

    ids: list[int] = Field(description='章节 ID 列表')
