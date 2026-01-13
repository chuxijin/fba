#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
笔记相关 Schema

设计原则：
- 支持公开/私密设置
- 公开笔记可被点赞/点踩
- 管理员可精选优质笔记
"""
from datetime import datetime

from pydantic import ConfigDict, Field

from backend.common.schema import SchemaBase


# ============ 题目笔记 Schema ============


class QuestionNoteSchemaBase(SchemaBase):
    """题目笔记基础 Schema"""

    question_id: int = Field(description='题目 ID')
    content: str = Field(description='笔记内容（Markdown 格式）')
    is_public: bool = Field(default=False, description='是否公开')


class CreateQuestionNoteParam(QuestionNoteSchemaBase):
    """创建笔记参数"""


class UpdateQuestionNoteParam(SchemaBase):
    """更新笔记参数"""

    content: str = Field(description='笔记内容')
    is_public: bool | None = Field(None, description='是否公开')


class GetQuestionNoteDetail(QuestionNoteSchemaBase):
    """笔记详情"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='笔记 ID')
    user_id: int = Field(description='用户 ID')
    like_count: int = Field(description='点赞数')
    dislike_count: int = Field(description='点踩数')
    view_count: int = Field(description='浏览次数')
    quality_score: int = Field(description='质量分')
    is_featured: bool = Field(description='是否精选')
    featured_time: datetime | None = Field(None, description='精选时间')
    created_time: datetime = Field(description='创建时间')
    updated_time: datetime = Field(description='更新时间')


class GetQuestionNoteListItem(SchemaBase):
    """笔记列表项"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='笔记 ID')
    user_id: int = Field(description='用户 ID')
    question_id: int = Field(description='题目 ID')
    content: str = Field(description='笔记内容（预览）')
    is_public: bool = Field(description='是否公开')
    like_count: int = Field(description='点赞数')
    dislike_count: int = Field(description='点踩数')
    quality_score: int = Field(description='质量分')
    is_featured: bool = Field(description='是否精选')
    updated_time: datetime = Field(description='更新时间')
    # 扩展字段
    user_nickname: str | None = Field(None, description='用户昵称')
    user_avatar: str | None = Field(None, description='用户头像')


class SetNoteFeaturedParam(SchemaBase):
    """设置笔记精选参数（管理员功能）"""

    note_id: int = Field(description='笔记 ID')
    is_featured: bool = Field(description='是否精选')


# ============ 笔记投票 Schema ============


class VoteQuestionNoteParam(SchemaBase):
    """笔记投票参数"""

    note_id: int = Field(description='笔记 ID')
    vote_value: int = Field(description='投票值：1=点赞，-1=点踩')


class GetUserNoteVoteDetail(SchemaBase):
    """用户笔记投票详情"""

    model_config = ConfigDict(from_attributes=True)

    user_id: int = Field(description='用户 ID')
    note_id: int = Field(description='笔记 ID')
    vote_value: int = Field(description='投票值：1=点赞，-1=点踩')
    created_time: datetime = Field(description='投票时间')
    updated_time: datetime = Field(description='更新时间')


class NoteVoteStatistics(SchemaBase):
    """笔记投票统计"""

    like_count: int = Field(description='点赞数')
    dislike_count: int = Field(description='点踩数')
    quality_score: int = Field(description='质量分')
