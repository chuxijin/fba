#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime

from pydantic import ConfigDict, Field

from backend.common.schema import SchemaBase


class CiyuSchemaBase(SchemaBase):
    """词语基础"""

    word: str = Field(description='词语')
    meaning: str | None = Field(None, description='释义')
    pinyin: str | None = Field(None, description='拼音')
    synonym: str | None = Field(None, description='近义词')
    antonym: str | None = Field(None, description='反义词')
    example: str | None = Field(None, description='例句')
    category: str | None = Field(None, description='分类')
    source: str | None = Field(None, description='出处')
    emotion: str | None = Field(None, description='感情色彩')
    confusion: str | None = Field(None, description='易混辨析')
    frequency: int | None = Field(None, description='考频')


class CiyuParam(SchemaBase):
    """词语查询参数"""

    word: str | None = Field(None, description='词语')
    category: str | None = Field(None, description='分类')
    emotion: str | None = Field(None, description='感情色彩')
    frequency: int | None = Field(None, description='考频')


class CreateCiyuParam(CiyuSchemaBase):
    """创建词语参数"""


class UpdateCiyuParam(SchemaBase):
    """更新词语参数"""

    word: str | None = Field(None, description='词语')
    meaning: str | None = Field(None, description='释义')
    pinyin: str | None = Field(None, description='拼音')
    synonym: str | None = Field(None, description='近义词')
    antonym: str | None = Field(None, description='反义词')
    example: str | None = Field(None, description='例句')
    category: str | None = Field(None, description='分类')
    source: str | None = Field(None, description='出处')
    emotion: str | None = Field(None, description='感情色彩')
    confusion: str | None = Field(None, description='易混辨析')
    frequency: int | None = Field(None, description='考频')


class DeleteCiyuParam(SchemaBase):
    """删除词语参数"""

    ids: list[int] = Field(description='词语 ID 列表')


class GetCiyuDetail(CiyuSchemaBase):
    """词语详情"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='词语 ID')
    view_count: int = Field(description='阅读量')
    created_by: int = Field(description='创建者')
    updated_by: int | None = Field(None, description='修改者')
    created_time: datetime = Field(description='创建时间')
    updated_time: datetime | None = Field(None, description='更新时间')
