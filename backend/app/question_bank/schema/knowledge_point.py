#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from pydantic import BaseModel, Field


class KpChildNode(BaseModel):
    """知识点子节点"""

    id: int = Field(description='分类 ID')
    name: str = Field(description='知识点名称')
    question_count: int = Field(default=0, description='题目数量')
    children: list['KpChildNode'] = Field(default_factory=list, description='子节点')


class GetKpDetailResponse(BaseModel):
    """知识点详情响应"""

    id: int = Field(description='分类 ID')
    name: str = Field(description='知识点名称')
    total_question_count: int = Field(default=0, description='总题目数量')
    children: list[KpChildNode] = Field(default_factory=list, description='子知识点列表')


class KpProgressNode(BaseModel):
    """知识点进度节点"""

    name: str = Field(description='知识点名称')
    question_count: int = Field(default=0, description='题目数量')
    answer_count: int = Field(default=0, description='已做数量')
    correct_count: int = Field(default=0, description='正确数量')
    correct_ratio: float = Field(default=0, description='正确率')


class GetKpProgressResponse(BaseModel):
    """知识点进度响应"""

    id: int = Field(description='分类 ID')
    name: str = Field(description='知识点名称')
    total_question_count: int = Field(default=0, description='总题目数量')
    total_answer_count: int = Field(default=0, description='已做总数')
    total_correct_count: int = Field(default=0, description='正确总数')
    items: list[KpProgressNode] = Field(default_factory=list, description='各知识点进度')
