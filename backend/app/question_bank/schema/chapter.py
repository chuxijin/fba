#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime

from pydantic import ConfigDict, Field

from backend.common.schema import SchemaBase


class ChapterSchemaBase(SchemaBase):
    """章节基础"""

    bank_id: int = Field(description='题库 ID')
    name: str = Field(description='章节名称')
    code: str | None = Field(None, description='章节编码')
    level: int = Field(default=1, description='章节层级')
    sort_order: int = Field(default=0, description='排序权重')
    parent_id: int | None = Field(None, description='父级章节 ID')
    is_trial: bool = Field(default=False, description='是否为试用章节')


class GetChapterDetail(ChapterSchemaBase):
    """章节详情"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='章节 ID')
    q_count: int = Field(description='题目数量')
    created_time: datetime = Field(description='创建时间')
    updated_time: datetime | None = Field(None, description='更新时间')


class GetChapterWithRelationDetail(GetChapterDetail):
    """章节关联详情"""

    model_config = ConfigDict(from_attributes=True)

    bank: dict | None = Field(None, description='题库信息')


class GetChapterTree(GetChapterDetail):
    """章节树"""

    children: list['GetChapterTree'] | None = Field(None, description='子章节')


class ChapterParam(SchemaBase):
    """章节参数"""

    bank_id: int = Field(description='题库 ID')


class CreateChapterParam(ChapterSchemaBase):
    """创建章节参数"""


class UpdateChapterParam(ChapterSchemaBase):
    """更新章节参数"""


class DeleteChapterParam(SchemaBase):
    """删除章节参数"""

    ids: list[int] = Field(description='章节 ID 列表')
