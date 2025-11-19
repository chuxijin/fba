#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
收藏相关 Schema

设计原则：
- 支持收藏夹分组（类似 LeetCode）
- 支持自定义标签
- 支持置顶功能
"""
from datetime import datetime

from pydantic import ConfigDict, Field

from backend.common.schema import SchemaBase


# ============ 题目收藏 Schema ============


class QuestionFavoriteSchemaBase(SchemaBase):
    """题目收藏基础 Schema"""

    question_id: int = Field(description='题目 ID')
    folder_name: str | None = Field(None, description='收藏夹名称')
    tags: list[str] | None = Field(None, description='自定义标签')
    remark: str | None = Field(None, description='备注')


class CreateQuestionFavoriteParam(QuestionFavoriteSchemaBase):
    """创建收藏参数"""

    user_id: int = Field(description='用户 ID')


class UpdateQuestionFavoriteParam(SchemaBase):
    """更新收藏参数"""

    folder_name: str | None = Field(None, description='收藏夹名称')
    tags: list[str] | None = Field(None, description='自定义标签')
    remark: str | None = Field(None, description='备注')


class GetQuestionFavoriteDetail(QuestionFavoriteSchemaBase):
    """收藏详情"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='收藏 ID')
    user_id: int = Field(description='用户 ID')
    is_pinned: bool = Field(description='是否置顶')
    pinned_time: datetime | None = Field(None, description='置顶时间')
    created_time: datetime = Field(description='收藏时间')


class GetQuestionFavoriteListItem(SchemaBase):
    """收藏列表项"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='收藏 ID')
    question_id: int = Field(description='题目 ID')
    folder_name: str | None = Field(None, description='收藏夹名称')
    tags: list[str] | None = Field(None, description='自定义标签')
    is_pinned: bool = Field(description='是否置顶')
    created_time: datetime = Field(description='收藏时间')
    # 扁平化字段，方便前端显示
    question_stem: str | None = Field(None, description='题目题干')
    question_type: str | None = Field(None, description='题型')
    question_difficulty: str | None = Field(None, description='难度')
    bank_name: str | None = Field(None, description='题库名称')
    chapter_name: str | None = Field(None, description='章节名称')


class SetFavoritePinParam(SchemaBase):
    """设置收藏置顶参数"""

    favorite_id: int = Field(description='收藏 ID')
    is_pinned: bool = Field(description='是否置顶')


class BatchDeleteFavoritesParam(SchemaBase):
    """批量删除收藏参数"""

    favorite_ids: list[int] = Field(description='收藏 ID 列表')


class ClearFolderParam(SchemaBase):
    """清空收藏夹参数"""

    folder_name: str = Field(description='收藏夹名称')


class FolderInfo(SchemaBase):
    """收藏夹信息"""

    folder_name: str = Field(description='收藏夹名称')
    count: int = Field(description='收藏数量')


class FavoriteStatistics(SchemaBase):
    """收藏统计"""

    total_count: int = Field(description='总收藏数')
    folder_count: int = Field(description='收藏夹数量')
    folders: list[FolderInfo] = Field(description='收藏夹列表')
