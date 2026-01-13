#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime

from pydantic import ConfigDict, Field

from backend.common.schema import SchemaBase


# ==================== 群活码主表 ====================
class QunSchemaBase(SchemaBase):
    """群活码基础模型"""

    title: str = Field(max_length=128, description='标题')
    remark: str | None = Field(None, max_length=256, description='备注')
    entry_domain: str | None = Field(None, max_length=128, description='入口域名')
    redirect_domain: str | None = Field(None, max_length=128, description='中转域名')
    landing_domain: str | None = Field(None, max_length=128, description='落地域名')
    kf: int | None = Field(None, description='关联客服ID')
    kf_status: int = Field(0, ge=0, le=1, description='客服状态(0不显示 1显示)')


class CreateQunParam(QunSchemaBase):
    """创建群活码参数"""

    code: str | None = Field(None, max_length=16, description='自定义活码Key(可选)')


class UpdateQunParam(SchemaBase):
    """更新群活码参数"""

    title: str | None = Field(None, max_length=128, description='标题')
    remark: str | None = Field(None, max_length=256, description='备注')
    status: int | None = Field(None, ge=0, le=1, description='状态(0停用 1启用)')
    entry_domain: str | None = Field(None, max_length=128, description='入口域名')
    redirect_domain: str | None = Field(None, max_length=128, description='中转域名')
    landing_domain: str | None = Field(None, max_length=128, description='落地域名')
    domain_status: int | None = Field(None, ge=0, le=1, description='域名状态')
    kf: int | None = Field(None, description='关联客服ID')
    kf_status: int | None = Field(None, ge=0, le=1, description='客服状态')


class GetQunDetail(QunSchemaBase):
    """群活码详情"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='群活码ID')
    code: str = Field(description='活码Key')
    clicks: int = Field(description='访问量')
    status: int = Field(description='状态')
    domain_status: int = Field(description='域名状态')
    created_by: int = Field(description='创建者ID')
    created_time: datetime = Field(description='创建时间')
    updated_time: datetime | None = Field(None, description='更新时间')


class GetQunList(SchemaBase):
    """群活码列表项"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='群活码ID')
    code: str = Field(description='活码Key')
    title: str = Field(description='标题')
    clicks: int = Field(description='访问量')
    status: int = Field(description='状态')
    domain_status: int = Field(description='域名状态')
    created_time: datetime = Field(description='创建时间')


# ==================== 群活码子表 ====================
class QunItemSchemaBase(SchemaBase):
    """群活码子表基础模型"""

    qrcode: str = Field(max_length=512, description='群二维码图片URL')
    limit: int = Field(200, ge=1, description='扫码阈值')
    leader: str | None = Field(None, max_length=64, description='群主')


class CreateQunItemParam(QunItemSchemaBase):
    """创建群活码子项参数"""

    qun_id: int = Field(description='群活码ID')


class UpdateQunItemParam(SchemaBase):
    """更新群活码子项参数"""

    qrcode: str | None = Field(None, max_length=512, description='群二维码图片URL')
    limit: int | None = Field(None, ge=1, description='扫码阈值')
    leader: str | None = Field(None, max_length=64, description='群主')
    status: int | None = Field(None, ge=0, le=2, description='状态(0停用 1启用 2已满)')


class GetQunItemDetail(QunItemSchemaBase):
    """群活码子项详情"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='子项ID')
    qun_id: int = Field(description='群活码ID')
    clicks: int = Field(description='访问量')
    longpress: int = Field(description='长按次数')
    status: int = Field(description='状态')
    created_time: datetime = Field(description='创建时间')
