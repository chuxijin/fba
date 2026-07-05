#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from pydantic import Field

from backend.common.schema import SchemaBase


class HanyuWordbookParam(SchemaBase):
    """词语本参数"""

    name: str = Field(..., description='词语本名称')
    description: str | None = Field(None, description='词语本描述')
    cover_image: str | None = Field(None, description='封面图 URL')
    category: str = Field('custom', description='分类')


class AddHanyuWordbookEntryParam(SchemaBase):
    """添加词语条目参数"""

    hanyu_id: int = Field(..., description='汉语词汇 ID')
    group_name: str | None = Field(None, description='组名（如第一组 中华文明传统文化）')
    category: str | None = Field(None, description='子分类')
    meaning: str | None = Field(None, description='自定义释义')
    commentary: str | None = Field(None, description='讲解/备注')
    example: str | None = Field(None, description='例句')
    sort_order: int = Field(0, description='排序')