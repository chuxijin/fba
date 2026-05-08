#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime

from pydantic import ConfigDict, Field

from backend.common.schema import SchemaBase


class CreateGroupParam(SchemaBase):
    """创建学习组参数"""

    name: str = Field(min_length=1, max_length=50, description='组名')
    description: str | None = Field(None, max_length=200, description='描述')
    color: str | None = Field(None, max_length=20, description='标签颜色')
    sort_order: int = Field(default=0, description='排序')


class UpdateGroupParam(SchemaBase):
    """更新学习组参数"""

    name: str | None = Field(None, max_length=50, description='组名')
    description: str | None = Field(None, max_length=200, description='描述')
    color: str | None = Field(None, max_length=20, description='标签颜色')
    sort_order: int | None = Field(None, description='排序')


class GetGroupDetail(SchemaBase):
    """学习组详情"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='学习组 ID')
    user_id: int = Field(description='用户 ID')
    name: str = Field(description='组名')
    description: str | None = Field(None, description='描述')
    color: str | None = Field(None, description='标签颜色')
    sort_order: int = Field(description='排序')
    word_count: int = Field(default=0, description='组内单词数')
    created_time: datetime = Field(description='创建时间')


class GroupAddWordsParam(SchemaBase):
    """向学习组添加单词参数"""

    word_ids: list[int] = Field(min_length=1, description='单词 ID 列表')


class GroupRemoveWordsParam(SchemaBase):
    """从学习组移除单词参数"""

    word_ids: list[int] = Field(min_length=1, description='单词 ID 列表')
