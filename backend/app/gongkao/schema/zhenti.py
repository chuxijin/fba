#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime
from decimal import Decimal

from pydantic import ConfigDict, Field

from backend.common.schema import SchemaBase


# ==================== 题目 Schema ====================
class QuestionSchemaBase(SchemaBase):
    """题目基础"""

    title: str = Field(description='题目题干')
    type: str = Field(description='题型')
    category_id: int = Field(description='关联分类 ID')
    material_ids: list[int] | None = Field(None, description='关联材料 ID 列表')
    difficulty: Decimal | None = Field(None, description='难度')
    year: int | None = Field(None, description='年份')
    source: str | None = Field(None, description='来源')
    tags: list[str] | None = Field(None, description='标签')
    score: Decimal | None = Field(None, description='分值')
    view_count: int = Field(0, description='浏览量')
    status: bool = Field(True, description='状态')
    sort_order: int = Field(0, description='排序权重')


class QuestionParam(SchemaBase):
    """题目查询参数"""

    title: str | None = Field(None, description='题目题干')
    type: str | None = Field(None, description='题型')
    category_id: int | None = Field(None, description='关联分类 ID')
    material_id: int | None = Field(None, description='关联材料 ID（筛选包含此材料的题目）')
    year: int | None = Field(None, description='年份')
    source: str | None = Field(None, description='来源')
    status: bool | None = Field(None, description='状态')


class CreateQuestionParam(QuestionSchemaBase):
    """创建题目参数"""


class UpdateQuestionParam(SchemaBase):
    """更新题目参数"""

    title: str | None = Field(None, description='题目题干')
    type: str | None = Field(None, description='题型')
    category_id: int | None = Field(None, description='关联分类 ID')
    material_ids: list[int] | None = Field(None, description='关联材料 ID 列表')
    difficulty: Decimal | None = Field(None, description='难度')
    year: int | None = Field(None, description='年份')
    source: str | None = Field(None, description='来源')
    tags: list[str] | None = Field(None, description='标签')
    score: Decimal | None = Field(None, description='分值')
    status: bool | None = Field(None, description='状态')
    sort_order: int | None = Field(None, description='排序权重')


class DeleteQuestionParam(SchemaBase):
    """删除题目参数"""

    ids: list[int] = Field(description='题目 ID 列表')


class GetQuestionDetail(QuestionSchemaBase):
    """题目详情"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='题目 ID')
    created_by: int = Field(description='创建者')
    updated_by: int | None = Field(None, description='修改者')
    created_time: datetime = Field(description='创建时间')
    updated_time: datetime | None = Field(None, description='更新时间')


# ==================== 题目选项 Schema ====================
class QuestionOptionSchemaBase(SchemaBase):
    """题目选项基础"""

    question_id: int = Field(description='关联题目 ID')
    option_key: str = Field(description='选项标识')
    option_content: str = Field(description='选项内容')
    sort_order: int = Field(0, description='排序')


class CreateQuestionOptionParam(QuestionOptionSchemaBase):
    """创建题目选项参数"""


class UpdateQuestionOptionParam(SchemaBase):
    """更新题目选项参数"""

    option_key: str | None = Field(None, description='选项标识')
    option_content: str | None = Field(None, description='选项内容')
    sort_order: int | None = Field(None, description='排序')


class DeleteQuestionOptionParam(SchemaBase):
    """删除题目选项参数"""

    ids: list[int] = Field(description='选项 ID 列表')


class GetQuestionOptionDetail(QuestionOptionSchemaBase):
    """题目选项详情"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='选项 ID')
    created_time: datetime = Field(description='创建时间')
    updated_time: datetime | None = Field(None, description='更新时间')


# ==================== 题目答案 Schema ====================
class QuestionAnswerSchemaBase(SchemaBase):
    """题目答案基础"""

    question_id: int = Field(description='关联题目 ID')
    source: str = Field(description='答案来源')
    answer_keys: str | None = Field(None, description='客观题答案')
    answer: str | None = Field(None, description='主观题答案')
    analysis: str | None = Field(None, description='答案解析')
    analysis_video_url: str | None = Field(None, description='视频解析链接')
    knowledge_points: list[str] | None = Field(None, description='知识点')
    reference_materials: str | None = Field(None, description='参考资料')
    is_official: bool = Field(False, description='是否官方答案')


class CreateQuestionAnswerParam(QuestionAnswerSchemaBase):
    """创建题目答案参数"""


class UpdateQuestionAnswerParam(SchemaBase):
    """更新题目答案参数"""

    source: str | None = Field(None, description='答案来源')
    answer_keys: str | None = Field(None, description='客观题答案')
    answer: str | None = Field(None, description='主观题答案')
    analysis: str | None = Field(None, description='答案解析')
    analysis_video_url: str | None = Field(None, description='视频解析链接')
    knowledge_points: list[str] | None = Field(None, description='知识点')
    reference_materials: str | None = Field(None, description='参考资料')
    is_official: bool | None = Field(None, description='是否官方答案')


class DeleteQuestionAnswerParam(SchemaBase):
    """删除题目答案参数"""

    ids: list[int] = Field(description='答案 ID 列表')


class GetQuestionAnswerDetail(QuestionAnswerSchemaBase):
    """题目答案详情"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='答案 ID')
    created_time: datetime = Field(description='创建时间')
    updated_time: datetime | None = Field(None, description='更新时间')


# ==================== 材料 Schema ====================
class MaterialSchemaBase(SchemaBase):
    """材料基础"""

    title: str = Field(description='材料标题')
    content: str = Field(description='材料内容')
    category_id: int = Field(description='关联分类 ID')
    year: int | None = Field(None, description='年份')
    source: str | None = Field(None, description='来源')
    tags: list[str] | None = Field(None, description='标签')
    view_count: int = Field(0, description='浏览量')
    status: bool = Field(True, description='状态')
    sort_order: int = Field(0, description='排序权重')


class MaterialParam(SchemaBase):
    """材料查询参数"""

    title: str | None = Field(None, description='材料标题')
    category_id: int | None = Field(None, description='关联分类 ID')
    year: int | None = Field(None, description='年份')
    source: str | None = Field(None, description='来源')
    status: bool | None = Field(None, description='状态')


class CreateMaterialParam(MaterialSchemaBase):
    """创建材料参数"""


class UpdateMaterialParam(SchemaBase):
    """更新材料参数"""

    title: str | None = Field(None, description='材料标题')
    content: str | None = Field(None, description='材料内容')
    category_id: int | None = Field(None, description='关联分类 ID')
    year: int | None = Field(None, description='年份')
    source: str | None = Field(None, description='来源')
    tags: list[str] | None = Field(None, description='标签')
    status: bool | None = Field(None, description='状态')
    sort_order: int | None = Field(None, description='排序权重')


class DeleteMaterialParam(SchemaBase):
    """删除材料参数"""

    ids: list[int] = Field(description='材料 ID 列表')


class GetMaterialDetail(MaterialSchemaBase):
    """材料详情"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='材料 ID')
    created_by: int = Field(description='创建者')
    updated_by: int | None = Field(None, description='修改者')
    created_time: datetime = Field(description='创建时间')
    updated_time: datetime | None = Field(None, description='更新时间')
