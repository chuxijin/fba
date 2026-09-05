#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime

from pydantic import ConfigDict, Field

from backend.common.schema import SchemaBase


class HanyuGroupItemSchemaBase(SchemaBase):
    """辨析组成员基础"""

    word: str = Field(description='词语名称')
    hanyu_id: int | None = Field(None, description='关联汉语词汇 ID')
    emphasis: str | None = Field(None, description='对比侧重点/释义')
    collocation: str | None = Field(None, description='常见搭配/适用对象')
    sort_order: int = Field(0, description='组内排序')


class HanyuGroupSchemaBase(SchemaBase):
    """辨析组基础"""

    title: str = Field(description='辨析组标题')
    group_no: str | None = Field(None, description='序号/题号')
    category: str = Field('实词辨析', description='分类')
    summary: str | None = Field(None, description='辨析概要与核心差异解析')
    example: str | None = Field(None, description='典型例句/考题')
    sort_order: int = Field(0, description='排序')


class HanyuGroupParam(SchemaBase):
    """辨析组查询"""

    title: str | None = Field(None, description='标题关键字')
    category: str | None = Field(None, description='分类')
    group_no: str | None = Field(None, description='序号/题号')


class CreateHanyuGroupItemParam(HanyuGroupItemSchemaBase):
    """创建辨析组成员"""


class CreateHanyuGroupParam(HanyuGroupSchemaBase):
    """创建辨析组"""

    items: list[CreateHanyuGroupItemParam] = Field(default_factory=list, description='成员明细')


class UpdateHanyuGroupParam(SchemaBase):
    """更新辨析组"""

    title: str | None = Field(None, description='辨析组标题')
    group_no: str | None = Field(None, description='序号/题号')
    category: str | None = Field(None, description='分类')
    summary: str | None = Field(None, description='辨析概要与核心差异解析')
    example: str | None = Field(None, description='典型例句/考题')
    sort_order: int | None = Field(None, description='排序')
    items: list[CreateHanyuGroupItemParam] | None = Field(None, description='成员明细（传入则整体替换）')


class DeleteHanyuGroupParam(SchemaBase):
    """删除辨析组"""

    ids: list[int] = Field(description='id 列表')


class GetHanyuGroupItemDetail(HanyuGroupItemSchemaBase):
    """辨析组成员详情"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='id')
    group_id: int = Field(description='所属辨析组 ID')


class GetHanyuGroupDetail(HanyuGroupSchemaBase):
    """辨析组详情"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='id')
    created_by: int = Field(description='创建人')
    updated_by: int | None = Field(None, description='更新人')
    created_time: datetime = Field(description='创建时间')
    updated_time: datetime | None = Field(None, description='更新时间')
    items: list[GetHanyuGroupItemDetail] = Field(default_factory=list, description='成员明细')


class GetHanyuGroupListDetail(SchemaBase):
    """辨析组列表项"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='id')
    title: str = Field(description='辨析组标题')
    group_no: str | None = Field(None, description='序号/题号')
    category: str = Field(description='分类')
    summary: str | None = Field(None, description='辨析概要与核心差异解析')
    sort_order: int = Field(description='排序')
    item_count: int = Field(default=0, description='成员数量')
    created_time: datetime = Field(description='创建时间')
