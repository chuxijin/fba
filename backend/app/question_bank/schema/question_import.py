#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from pydantic import Field

from backend.common.schema import SchemaBase


# ===== CSV 批量导入 Schema =====


class QuestionImportRow(SchemaBase):
    """单条题目导入数据"""

    ID: int | str | None = Field(None, description='序号')
    题目: str = Field(min_length=1, description='题干内容')
    题型: str = Field(description='题型: 单选/多选/判断/填空/简答')
    分数: int | None = Field(default=1, ge=0, description='分值')
    难度: str | None = Field(default='中等', description='难度: 简单/中等/困难')
    选项A: str | None = Field(None, description='选项 A')
    选项B: str | None = Field(None, description='选项 B')
    选项C: str | None = Field(None, description='选项 C')
    选项D: str | None = Field(None, description='选项 D')
    答案: str = Field(min_length=1, description='正确答案')
    解析: str | None = Field(None, description='解析内容')
    一级目录: str | None = Field(None, description='一级章节名称')
    二级目录: str | None = Field(None, description='二级章节名称')


class BatchImportParam(SchemaBase):
    """批量导入题目参数"""

    bank_id: int = Field(gt=0, description='题库 ID')
    questions: list[QuestionImportRow] = Field(min_length=1, description='题目列表')


class ImportResultItem(SchemaBase):
    """单条导入结果"""

    row_number: int = Field(description='行号')
    success: bool = Field(description='是否成功')
    question_id: int | None = Field(None, description='题目 ID')
    error_message: str | None = Field(None, description='错误信息')


class BatchImportResult(SchemaBase):
    """批量导入结果"""

    total: int = Field(ge=0, description='总数')
    success_count: int = Field(ge=0, description='成功数')
    fail_count: int = Field(ge=0, description='失败数')
    details: list[ImportResultItem] = Field(default_factory=list, description='详情列表')
