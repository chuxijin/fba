#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from pydantic import ConfigDict, Field

from backend.app.access.schema.template import TemplatePackBrief
from backend.common.schema import SchemaBase


class CatalogTemplate(SchemaBase):
    """面向游客的在售套餐信息，不包含管理元数据或用户权益"""

    model_config = ConfigDict(from_attributes=True)

    code: str = Field(description='套餐编码')
    name: str = Field(description='套餐名称')
    tier_code: str | None = Field(description='会员档位编码')
    tier_name: str | None = Field(description='会员档位名称')
    tier_weight: int = Field(description='档位排序权重')
    is_paid_membership: bool = Field(description='是否属于付费会员')
    tier_badge_color: str | None = Field(description='会员徽章主题色')
    duration_days: int | None = Field(description='期限天数，空表示长期有效')
    price_cents: int = Field(description='售价，单位分')
    cover_image: str | None = Field(description='封面图')
    description: str | None = Field(description='套餐说明')
    pack_codes: list[str] = Field(description='关联的上架权益包编码')
    domain_codes: list[str] = Field(description='适用领域编码')
    packs: list[TemplatePackBrief] = Field(description='关联的上架权益包摘要')


class CatalogPack(SchemaBase):
    """在售套餐引用的上架权益包"""

    code: str = Field(description='权益包编码')
    name: str = Field(description='权益包名称')
    description: str | None = Field(description='权益包说明')
    entitlement_codes: list[str] = Field(description='有效权益编码')


class CatalogEntitlement(SchemaBase):
    """用于购买前对比的权益说明"""

    model_config = ConfigDict(from_attributes=True)

    code: str = Field(description='权益编码')
    name: str = Field(description='权益名称')
    category: str = Field(description='权益类型')
    description: str | None = Field(description='权益说明')


class GetSubscriptionCatalog(SchemaBase):
    """公开销售目录"""

    templates: list[CatalogTemplate] = Field(description='在售套餐')
    packs: list[CatalogPack] = Field(description='在售套餐引用的权益包')
    entitlements: list[CatalogEntitlement] = Field(description='在售套餐引用的权益说明')
