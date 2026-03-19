#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import ConfigDict, Field

from backend.common.schema import SchemaBase

# ===== enums =====
ProductType = Literal['virtual', 'physical']
ProductStatus = Literal['draft', 'on_sale', 'off_sale', 'deleted']


# ===== category =====
class ProductCategoryBase(SchemaBase):
    """商品分类基础"""

    name: str = Field(max_length=64, description='分类名称')
    parent_id: int | None = Field(None, gt=0, description='父级分类 ID')
    level: int = Field(default=1, ge=1, description='分类层级')
    sort_order: int = Field(default=0, ge=0, description='排序权重')
    icon: str | None = Field(None, max_length=256, description='分类图标')
    description: str | None = Field(None, max_length=512, description='分类描述')
    is_active: bool = Field(default=True, description='是否启用')


class CreateProductCategoryParam(ProductCategoryBase):
    """创建商品分类参数"""


class UpdateProductCategoryParam(SchemaBase):
    """更新商品分类参数"""

    name: str | None = Field(None, max_length=64, description='分类名称')
    parent_id: int | None = Field(None, gt=0, description='父级分类 ID')
    sort_order: int | None = Field(None, ge=0, description='排序权重')
    icon: str | None = Field(None, max_length=256, description='分类图标')
    description: str | None = Field(None, max_length=512, description='分类描述')
    is_active: bool | None = Field(None, description='是否启用')


class GetProductCategoryListItem(SchemaBase):
    """商品分类列表项"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='分类 ID')
    name: str = Field(description='分类名称')
    parent_id: int | None = Field(None, description='父级分类 ID')
    level: int = Field(description='分类层级')
    sort_order: int = Field(description='排序权重')
    icon: str | None = Field(None, description='分类图标')
    description: str | None = Field(None, description='分类描述')
    is_active: bool = Field(description='是否启用')
    created_time: datetime = Field(description='创建时间')


# ===== product =====
class ProductBase(SchemaBase):
    """商品基础"""

    category_id: int = Field(gt=0, description='分类 ID')
    name: str = Field(max_length=256, description='商品名称')
    subtitle: str | None = Field(None, max_length=512, description='商品副标题')
    product_type: ProductType = Field(default='virtual', description='商品类型')
    cover_image: str | None = Field(None, max_length=512, description='封面图')
    images: list[str] | None = Field(None, description='商品图片列表')
    detail: str | None = Field(None, description='商品详情')
    sort_order: int = Field(default=0, ge=0, description='排序权重')
    virtual_sales: int = Field(default=0, ge=0, description='虚拟销量')


class CreateProductParam(ProductBase):
    """创建商品参数"""


class UpdateProductParam(SchemaBase):
    """更新商品参数"""

    category_id: int | None = Field(None, gt=0, description='分类 ID')
    name: str | None = Field(None, max_length=256, description='商品名称')
    subtitle: str | None = Field(None, max_length=512, description='商品副标题')
    product_type: ProductType | None = Field(None, description='商品类型')
    cover_image: str | None = Field(None, max_length=512, description='封面图')
    images: list[str] | None = Field(None, description='商品图片列表')
    detail: str | None = Field(None, description='商品详情')
    status: ProductStatus | None = Field(None, description='商品状态')
    sort_order: int | None = Field(None, ge=0, description='排序权重')
    virtual_sales: int | None = Field(None, ge=0, description='虚拟销量')


class GetProductListItem(SchemaBase):
    """商品列表项"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='商品 ID')
    category_id: int = Field(description='分类 ID')
    name: str = Field(description='商品名称')
    subtitle: str | None = Field(None, description='商品副标题')
    product_type: ProductType = Field(description='商品类型')
    cover_image: str | None = Field(None, description='封面图')
    status: ProductStatus = Field(description='商品状态')
    sort_order: int = Field(description='排序权重')
    sales_count: int = Field(description='实际销量')
    virtual_sales: int = Field(description='虚拟销量')
    view_count: int = Field(description='浏览量')
    created_time: datetime = Field(description='创建时间')


class GetProductDetail(GetProductListItem):
    """商品详情"""

    images: list[str] | None = Field(None, description='商品图片列表')
    detail: str | None = Field(None, description='商品详情')
    on_sale_time: datetime | None = Field(None, description='上架时间')
    off_sale_time: datetime | None = Field(None, description='下架时间')


# ===== sku =====
class ProductSKUBase(SchemaBase):
    """商品 SKU 基础"""

    product_id: int = Field(gt=0, description='商品 ID')
    sku_name: str = Field(max_length=128, description='SKU 名称')
    sku_code: str | None = Field(None, max_length=64, description='SKU 编码')
    specs: dict[str, Any] | None = Field(None, description='规格属性')
    price: Decimal = Field(ge=Decimal('0'), description='售价')
    original_price: Decimal | None = Field(None, ge=Decimal('0'), description='原价')
    stock: int = Field(default=0, ge=0, description='库存')
    image: str | None = Field(None, max_length=512, description='SKU 图片')
    is_active: bool = Field(default=True, description='是否启用')


class CreateProductSKUParam(ProductSKUBase):
    """创建商品 SKU 参数"""


class UpdateProductSKUParam(SchemaBase):
    """更新商品 SKU 参数"""

    sku_name: str | None = Field(None, max_length=128, description='SKU 名称')
    sku_code: str | None = Field(None, max_length=64, description='SKU 编码')
    specs: dict[str, Any] | None = Field(None, description='规格属性')
    price: Decimal | None = Field(None, ge=Decimal('0'), description='售价')
    original_price: Decimal | None = Field(None, ge=Decimal('0'), description='原价')
    stock: int | None = Field(None, ge=0, description='库存')
    image: str | None = Field(None, max_length=512, description='SKU 图片')
    is_active: bool | None = Field(None, description='是否启用')


class GetProductSKUListItem(SchemaBase):
    """商品 SKU 列表项"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='SKU ID')
    product_id: int = Field(description='商品 ID')
    sku_name: str = Field(description='SKU 名称')
    sku_code: str | None = Field(None, description='SKU 编码')
    specs: dict[str, Any] | None = Field(None, description='规格属性')
    price: Decimal = Field(description='售价')
    original_price: Decimal | None = Field(None, description='原价')
    stock: int = Field(description='库存')
    sales_count: int = Field(description='销量')
    image: str | None = Field(None, description='SKU 图片')
    is_active: bool = Field(description='是否启用')
    created_time: datetime = Field(description='创建时间')
