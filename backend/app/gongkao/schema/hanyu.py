#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime

from pydantic import ConfigDict, Field

from backend.common.schema import SchemaBase


class HanyuSchemaBase(SchemaBase):
    """汉语词汇基础"""

    name: str = Field(description='词语名称')
    type: str | None = Field(None, description='类型')
    pinyin: str | None = Field(None, description='拼音')
    baobian: str | None = Field(None, description='褒贬色彩')
    structure: str | None = Field(None, description='结构')
    voice: str | None = Field(None, description='语音 URL')
    definition_info: dict | None = Field(None, description='定义信息')
    detail_means: list | None = Field(None, description='详细含义')
    liju: list | None = Field(None, description='例句')
    antonym: list | None = Field(None, description='反义词')
    synonyms: list | None = Field(None, description='近义词')
    chu_chu: list | None = Field(None, description='出处')
    yin_zheng: list | None = Field(None, description='引证')
    frequency: list | None = Field(None, description='相关题目ID列表')


class HanyuParam(SchemaBase):
    """汉语词汇查询"""

    name: str | None = Field(None, description='词语名称关键字')
    type: str | None = Field(None, description='类型')
    baobian: str | None = Field(None, description='褒贬色彩')
    structure: str | None = Field(None, description='结构')
    min_frequency: int | None = Field(None, description='最小使用频次')
    notebook_only: bool | None = Field(None, description='是否只显示生词本里的词汇')
    user_id: int | None = Field(None, description='用户 ID')


class CreateHanyuParam(HanyuSchemaBase):
    """创建汉语词汇"""


class UpdateHanyuParam(SchemaBase):
    """更新汉语词汇"""

    name: str | None = Field(None, description='词语名称')
    type: str | None = Field(None, description='类型')
    pinyin: str | None = Field(None, description='拼音')
    baobian: str | None = Field(None, description='褒贬色彩')
    structure: str | None = Field(None, description='结构')
    voice: str | None = Field(None, description='语音 URL')
    definition_info: dict | None = Field(None, description='定义信息')
    detail_means: list | None = Field(None, description='详细含义')
    liju: list | None = Field(None, description='例句')
    antonym: list | None = Field(None, description='反义词')
    synonyms: list | None = Field(None, description='近义词')
    chu_chu: list | None = Field(None, description='出处')
    yin_zheng: list | None = Field(None, description='引证')
    frequency: list | None = Field(None, description='相关题目ID列表')


class DeleteHanyuParam(SchemaBase):
    """删除汉语词汇"""

    ids: list[int] = Field(description='id 列表')


class GetHanyuDetail(HanyuSchemaBase):
    """汉语词汇详情"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='id')
    created_by: int = Field(description='创建人')
    updated_by: int | None = Field(None, description='更新人')
    created_time: datetime = Field(description='创建时间')
    updated_time: datetime | None = Field(None, description='更新时间')
    in_notebook: bool | None = Field(None, description='是否已加入生词本')
    question_count: int = Field(default=0, description='相关题目数量')


class GetHanyuListDetail(SchemaBase):
    """汉语词汇列表项"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='id')
    name: str = Field(description='词语名称')
    type: str | None = Field(None, description='类型')
    pinyin: str | None = Field(None, description='拼音')
    baobian: str | None = Field(None, description='褒贬色彩')
    structure: str | None = Field(None, description='结构')
    frequency: list | None = Field(None, description='相关题目ID列表')
    question_count: int = Field(default=0, description='相关题目数量')
    created_time: datetime = Field(description='创建时间')
    in_notebook: bool | None = Field(None, description='是否已加入生词本')
