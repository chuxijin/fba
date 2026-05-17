#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime
from decimal import Decimal

from pydantic import Field, computed_field

from backend.common.schema import SchemaBase


class CreatePackageParam(SchemaBase):
    """创建套餐参数"""

    application_id: int = Field(description='应用ID')
    name: str = Field(description='套餐名称')
    description: str | None = Field(None, description='套餐描述')
    duration_days: int = Field(description='有效期天数')
    original_price: Decimal = Field(description='原价')
    discount_rate: Decimal | None = Field(None, description='折扣率')
    discount_start_time: datetime | None = Field(None, description='折扣开始时间')
    discount_end_time: datetime | None = Field(None, description='折扣结束时间')
    max_devices: int = Field(1, description='最大设备数量')
    template_code: str | None = Field(None, description='关联 access 订阅模板编码')
    sort_order: int = Field(0, description='排序')


class UpdatePackageParam(SchemaBase):
    """更新套餐参数"""

    name: str | None = Field(None, description='套餐名称')
    description: str | None = Field(None, description='套餐描述')
    duration_days: int | None = Field(None, description='有效期天数')
    original_price: Decimal | None = Field(None, description='原价')
    discount_rate: Decimal | None = Field(None, description='折扣率')
    discount_start_time: datetime | None = Field(None, description='折扣开始时间')
    discount_end_time: datetime | None = Field(None, description='折扣结束时间')
    max_devices: int | None = Field(None, description='最大设备数量')
    status: str | None = Field(None, description='套餐状态(active/inactive)')
    template_code: str | None = Field(None, description='关联 access 订阅模板编码')
    sort_order: int | None = Field(None, description='排序')


class GetPackageDetail(SchemaBase):
    """套餐详情"""

    id: int = Field(description='套餐ID')
    application_id: int = Field(description='应用ID')
    application_name: str | None = Field(None, description='应用名称')
    name: str = Field(description='套餐名称')
    description: str | None = Field(description='套餐描述')
    duration_days: int = Field(description='有效期天数')
    original_price: Decimal = Field(description='原价')
    discount_rate: Decimal | None = Field(description='折扣率')
    discount_start_time: datetime | None = Field(description='折扣开始时间')
    discount_end_time: datetime | None = Field(description='折扣结束时间')
    max_devices: int = Field(description='最大设备数量')
    status: str = Field(description='套餐状态')
    template_code: str | None = Field(description='关联 access 订阅模板编码')
    sort_order: int = Field(description='排序')
    created_time: datetime = Field(description='创建时间')
    updated_time: datetime | None = Field(description='更新时间')

    @computed_field
    @property
    def current_price(self) -> Decimal:
        """计算当前价格"""
        from backend.utils.timezone import timezone

        if not self.discount_rate:
            return self.original_price

        current_time = timezone.now()
        if self.discount_start_time and current_time < self.discount_start_time:
            return self.original_price
        if self.discount_end_time and current_time > self.discount_end_time:
            return self.original_price

        return self.original_price * self.discount_rate
