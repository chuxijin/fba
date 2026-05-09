#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from pydantic import Field

from backend.common.schema import SchemaBase


class VocabImportRow(SchemaBase):
    """单词导入行"""

    单词: str = Field(description='英文单词')
    美式音标: str | None = Field(None, description='美式音标')
    英式音标: str | None = Field(None, description='英式音标')
    常用释义: str | None = Field(None, description='常用释义（简短）')
    释义1_词性: str | None = Field(None, description='释义1 词性')
    释义1_中文: str | None = Field(None, description='释义1 中文释义')
    释义2_词性: str | None = Field(None, description='释义2 词性')
    释义2_中文: str | None = Field(None, description='释义2 中文释义')
    释义3_词性: str | None = Field(None, description='释义3 词性')
    释义3_中文: str | None = Field(None, description='释义3 中文释义')
    例句1_英文: str | None = Field(None, description='例句1 英文')
    例句1_中文: str | None = Field(None, description='例句1 中文翻译')
    例句2_英文: str | None = Field(None, description='例句2 英文')
    例句2_中文: str | None = Field(None, description='例句2 中文翻译')
    词频等级: int | None = Field(None, description='词频等级')


class VocabImportResultItem(SchemaBase):
    """单条导入结果"""

    row_number: int = Field(description='行号')
    word: str = Field(description='单词')
    success: bool = Field(description='是否成功')
    action: str = Field(description='操作类型: created / skipped / linked')
    word_id: int | None = Field(None, description='单词 ID')
    error_message: str | None = Field(None, description='错误信息')


class VocabExcelImportResult(SchemaBase):
    """Excel 导入结果"""

    total: int = Field(description='总行数')
    success_count: int = Field(description='成功数')
    created_count: int = Field(description='新建单词数')
    skipped_count: int = Field(description='跳过(已存在)数')
    linked_count: int = Field(description='已存在但新关联到词书的数量')
    fail_count: int = Field(description='失败数')
    details: list[VocabImportResultItem] = Field(default=[], description='逐行结果')
