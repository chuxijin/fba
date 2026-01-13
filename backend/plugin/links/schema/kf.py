#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime

from pydantic import ConfigDict, Field

from backend.common.schema import SchemaBase


# ==================== 客服码主表 ====================
class KfSchemaBase(SchemaBase):
    """客服码基础模型"""

    title: str = Field(max_length=128, description='标题')
    remark: str | None = Field(None, max_length=256, description='备注')
    online: str | None = Field(None, max_length=1024, description='在线规则(JSON)')
    entry_domain: str | None = Field(None, max_length=128, description='入口域名')
    redirect_domain: str | None = Field(None, max_length=128, description='中转域名')
    landing_domain: str | None = Field(None, max_length=128, description='落地域名')


class CreateKfParam(KfSchemaBase):
    """创建客服码参数"""

    code: str | None = Field(None, max_length=16, description='自定义客服码Key(可选)')


class UpdateKfParam(SchemaBase):
    """更新客服码参数"""

    title: str | None = Field(None, max_length=128, description='标题')
    remark: str | None = Field(None, max_length=256, description='备注')
    status: int | None = Field(None, ge=0, le=1, description='状态(0停用 1启用)')
    online: str | None = Field(None, max_length=1024, description='在线规则(JSON)')
    entry_domain: str | None = Field(None, max_length=128, description='入口域名')
    redirect_domain: str | None = Field(None, max_length=128, description='中转域名')
    landing_domain: str | None = Field(None, max_length=128, description='落地域名')
    domain_status: int | None = Field(None, ge=0, le=1, description='域名状态')


class GetKfDetail(KfSchemaBase):
    """客服码详情"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='客服码ID')
    code: str = Field(description='客服码Key')
    clicks: int = Field(description='访问量')
    status: int = Field(description='状态')
    domain_status: int = Field(description='域名状态')
    created_by: int = Field(description='创建者ID')
    created_time: datetime = Field(description='创建时间')
    updated_time: datetime | None = Field(None, description='更新时间')


class GetKfList(SchemaBase):
    """客服码列表项"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='客服码ID')
    code: str = Field(description='客服码Key')
    title: str = Field(description='标题')
    clicks: int = Field(description='访问量')
    status: int = Field(description='状态')
    domain_status: int = Field(description='域名状态')
    created_time: datetime = Field(description='创建时间')


# ==================== 客服码子表 ====================
class KfItemSchemaBase(SchemaBase):
    """客服码子表基础模型"""

    qrcode: str = Field(max_length=512, description='客服二维码图片URL')
    limit: int = Field(200, ge=1, description='扫码阈值')
    leader: str | None = Field(None, max_length=64, description='客服名称')


class CreateKfItemParam(KfItemSchemaBase):
    """创建客服码子项参数"""

    kf_id: int = Field(description='客服码ID')


class UpdateKfItemParam(SchemaBase):
    """更新客服码子项参数"""

    qrcode: str | None = Field(None, max_length=512, description='客服二维码图片URL')
    limit: int | None = Field(None, ge=1, description='扫码阈值')
    leader: str | None = Field(None, max_length=64, description='客服名称')
    status: int | None = Field(None, ge=0, le=2, description='状态(0停用 1启用 2已满)')


class GetKfItemDetail(KfItemSchemaBase):
    """客服码子项详情"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='子项ID')
    kf_id: int = Field(description='客服码ID')
    clicks: int = Field(description='访问量')
    longpress: int = Field(description='长按次数')
    status: int = Field(description='状态')
    created_time: datetime = Field(description='创建时间')
