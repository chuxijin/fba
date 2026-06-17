#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import ConfigDict, Field

from backend.common.schema import SchemaBase

# ===== enums =====
ActivityStatus = Literal['draft', 'active', 'paused', 'ended']


# ===== ladder price =====
class GroupBuyLadderPriceBase(SchemaBase):
    """拼团阶梯价格基础"""

    people_count: int = Field(ge=2, description='成团人数')
    price: Decimal = Field(ge=Decimal('0'), description='拼团价格')
    original_price: Decimal | None = Field(None, ge=Decimal('0'), description='原价')


class CreateGroupBuyLadderPriceParam(GroupBuyLadderPriceBase):
    """创建拼团阶梯价格参数"""


class GetGroupBuyLadderPriceItem(SchemaBase):
    """拼团阶梯价格列表项"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='阶梯价格 ID')
    activity_id: int = Field(description='活动 ID')
    people_count: int = Field(description='成团人数')
    price: Decimal = Field(description='拼团价格')
    original_price: Decimal | None = Field(None, description='原价')


# ===== activity =====
class GroupBuyActivityBase(SchemaBase):
    """拼团活动基础"""

    product_id: int = Field(gt=0, description='商品 ID')
    sku_id: int = Field(gt=0, description='SKU ID')
    activity_name: str = Field(max_length=256, description='活动名称')
    min_people: int = Field(ge=2, description='最小成团人数')
    max_people: int = Field(ge=2, description='最大成团人数')
    time_limit: int = Field(gt=0, description='成团时限（小时）')
    stock: int = Field(default=0, ge=0, description='活动库存')
    start_time: datetime = Field(description='活动开始时间')
    end_time: datetime = Field(description='活动结束时间')
    enable_mock_team: bool = Field(default=False, description='是否启用模拟成团')
    mock_team_threshold: int | None = Field(None, ge=1, description='模拟成团阈值')
    share_config: dict[str, Any] | None = Field(None, description='分享配置')
    rules: str | None = Field(None, description='活动规则说明')


class CreateGroupBuyActivityParam(GroupBuyActivityBase):
    """创建拼团活动参数"""

    ladder_prices: list[CreateGroupBuyLadderPriceParam] = Field(min_length=1, max_length=10, description='阶梯价格列表')


class UpdateGroupBuyActivityParam(SchemaBase):
    """更新拼团活动参数"""

    activity_name: str | None = Field(None, max_length=256, description='活动名称')
    time_limit: int | None = Field(None, gt=0, description='成团时限（小时）')
    stock: int | None = Field(None, ge=0, description='活动库存')
    status: ActivityStatus | None = Field(None, description='活动状态')
    start_time: datetime | None = Field(None, description='活动开始时间')
    end_time: datetime | None = Field(None, description='活动结束时间')
    enable_mock_team: bool | None = Field(None, description='是否启用模拟成团')
    mock_team_threshold: int | None = Field(None, ge=1, description='模拟成团阈值')
    share_config: dict[str, Any] | None = Field(None, description='分享配置')
    rules: str | None = Field(None, description='活动规则说明')


class GetGroupBuyActivityListItem(SchemaBase):
    """拼团活动列表项"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='活动 ID')
    product_id: int = Field(description='商品 ID')
    sku_id: int = Field(description='SKU ID')
    activity_name: str = Field(description='活动名称')
    min_people: int = Field(description='最小成团人数')
    max_people: int = Field(description='最大成团人数')
    time_limit: int = Field(description='成团时限（小时）')
    stock: int = Field(description='活动库存')
    sales_count: int = Field(description='已售数量')
    status: ActivityStatus = Field(description='活动状态')
    start_time: datetime = Field(description='活动开始时间')
    end_time: datetime = Field(description='活动结束时间')
    enable_mock_team: bool = Field(description='是否启用模拟成团')
    created_time: datetime = Field(description='创建时间')


class GetGroupBuyActivityDetail(GetGroupBuyActivityListItem):
    """拼团活动详情"""

    mock_team_threshold: int | None = Field(None, description='模拟成团阈值')
    share_config: dict[str, Any] | None = Field(None, description='分享配置')
    rules: str | None = Field(None, description='活动规则说明')
    ladder_prices: list[GetGroupBuyLadderPriceItem] = Field(default_factory=list, description='阶梯价格列表')
