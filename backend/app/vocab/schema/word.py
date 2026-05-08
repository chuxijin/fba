#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime

from pydantic import ConfigDict, Field

from backend.common.schema import SchemaBase


# ============ 释义 ============
class DefinitionParam(SchemaBase):
    """释义参数"""

    part_of_speech: str | None = Field(None, max_length=20, description='词性')
    meaning: str = Field(min_length=1, max_length=500, description='中文释义')
    meaning_en: str | None = Field(None, max_length=500, description='英文释义')
    sort_order: int = Field(default=0, description='排序')


class GetDefinitionDetail(SchemaBase):
    """释义详情"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='释义 ID')
    word_id: int = Field(description='单词 ID')
    part_of_speech: str | None = Field(None, description='词性')
    meaning: str = Field(description='中文释义')
    meaning_en: str | None = Field(None, description='英文释义')
    sort_order: int = Field(description='排序')


# ============ 例句 ============
class ExampleParam(SchemaBase):
    """例句参数"""

    definition_id: int | None = Field(None, description='关联释义 ID')
    sentence_en: str = Field(min_length=1, max_length=500, description='英文例句')
    sentence_zh: str | None = Field(None, max_length=500, description='中文翻译')
    source: str | None = Field(None, max_length=100, description='来源')
    sort_order: int = Field(default=0, description='排序')


class GetExampleDetail(SchemaBase):
    """例句详情"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='例句 ID')
    word_id: int = Field(description='单词 ID')
    definition_id: int | None = Field(None, description='关联释义 ID')
    sentence_en: str = Field(description='英文例句')
    sentence_zh: str | None = Field(None, description='中文翻译')
    source: str | None = Field(None, description='来源')
    sort_order: int = Field(description='排序')


# ============ 单词 ============
class CreateWordParam(SchemaBase):
    """创建单词参数"""

    word: str = Field(min_length=1, max_length=100, description='单词')
    phonetic_us: str | None = Field(None, max_length=100, description='美式音标')
    phonetic_uk: str | None = Field(None, max_length=100, description='英式音标')
    audio_us_url: str | None = Field(None, max_length=255, description='美式发音 URL')
    audio_uk_url: str | None = Field(None, max_length=255, description='英式发音 URL')
    common_meaning: str | None = Field(None, max_length=200, description='常用释义')
    frequency: int = Field(default=0, description='词频等级')
    definitions: list[DefinitionParam] = Field(default=[], description='释义列表')
    examples: list[ExampleParam] = Field(default=[], description='例句列表')


class UpdateWordParam(SchemaBase):
    """更新单词参数"""

    phonetic_us: str | None = Field(None, max_length=100, description='美式音标')
    phonetic_uk: str | None = Field(None, max_length=100, description='英式音标')
    audio_us_url: str | None = Field(None, max_length=255, description='美式发音 URL')
    audio_uk_url: str | None = Field(None, max_length=255, description='英式发音 URL')
    common_meaning: str | None = Field(None, max_length=200, description='常用释义')
    frequency: int | None = Field(None, description='词频等级')
    definitions: list[DefinitionParam] | None = Field(None, description='释义列表(全量替换)')
    examples: list[ExampleParam] | None = Field(None, description='例句列表(全量替换)')


class GetWordDetail(SchemaBase):
    """单词详情"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='单词 ID')
    word: str = Field(description='单词')
    phonetic_us: str | None = Field(None, description='美式音标')
    phonetic_uk: str | None = Field(None, description='英式音标')
    audio_us_url: str | None = Field(None, description='美式发音 URL')
    audio_uk_url: str | None = Field(None, description='英式发音 URL')
    common_meaning: str | None = Field(None, description='常用释义')
    frequency: int = Field(description='词频等级')
    definitions: list[GetDefinitionDetail] = Field(default=[], description='释义列表')
    examples: list[GetExampleDetail] = Field(default=[], description='例句列表')
    created_time: datetime = Field(description='创建时间')


class GetWordBrief(SchemaBase):
    """单词简要信息(卡片用)"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='单词 ID')
    word: str = Field(description='单词')
    phonetic_us: str | None = Field(None, description='美式音标')
    phonetic_uk: str | None = Field(None, description='英式音标')
    common_meaning: str | None = Field(None, description='常用释义')
