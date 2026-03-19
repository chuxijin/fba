#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.common.model import Base, TimeZone, UniversalText, UserMixin, id_key
from backend.utils.timezone import timezone

CompatibleJSONB = sa.JSON().with_variant(JSONB, 'postgresql')


class ProductCategory(Base, UserMixin):
    """商品分类表"""

    __tablename__ = 'mall_product_category'
    __table_args__ = (
        sa.Index('idx_category_parent_sort', 'parent_id', 'sort_order'),
        sa.CheckConstraint('sort_order >= 0', name='ck_category_sort'),
        sa.CheckConstraint('level >= 1', name='ck_category_level'),
        {'comment': '商品分类表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    name: Mapped[str] = mapped_column(sa.String(64), comment='分类名称')
    parent_id: Mapped[int | None] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('mall_product_category.id', ondelete='CASCADE'),
        default=None,
        comment='父级分类 ID',
    )
    level: Mapped[int] = mapped_column(sa.Integer, default=1, comment='分类层级')
    sort_order: Mapped[int] = mapped_column(sa.Integer, default=0, comment='排序权重')
    icon: Mapped[str | None] = mapped_column(sa.String(256), default=None, comment='分类图标')
    description: Mapped[str | None] = mapped_column(sa.String(512), default=None, comment='分类描述')
    is_active: Mapped[bool] = mapped_column(default=True, comment='是否启用')

    # ============ 关系 ============
    products: Mapped[list[Product]] = relationship(
        init=False,
        back_populates='category',
        lazy='noload',
        cascade='all, delete-orphan',
    )


class Product(Base, UserMixin):
    """商品表"""

    __tablename__ = 'mall_product'
    __table_args__ = (
        sa.Index('idx_product_category_status', 'category_id', 'status'),
        sa.Index('idx_product_type_status', 'product_type', 'status'),
        sa.CheckConstraint('sort_order >= 0', name='ck_product_sort'),
        sa.CheckConstraint(
            "product_type IN ('virtual','physical')",
            name='ck_product_type',
        ),
        sa.CheckConstraint(
            "status IN ('draft','on_sale','off_sale','deleted')",
            name='ck_product_status',
        ),
        {'comment': '商品表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    category_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('mall_product_category.id', ondelete='RESTRICT'),
        comment='分类 ID',
    )
    name: Mapped[str] = mapped_column(sa.String(256), comment='商品名称')
    subtitle: Mapped[str | None] = mapped_column(sa.String(512), default=None, comment='商品副标题')
    product_type: Mapped[str] = mapped_column(
        sa.String(16), default='virtual', comment='商品类型: virtual/physical'
    )
    cover_image: Mapped[str | None] = mapped_column(sa.String(512), default=None, comment='封面图')
    images: Mapped[list | None] = mapped_column(CompatibleJSONB, default=None, comment='商品图片列表')
    detail: Mapped[str | None] = mapped_column(UniversalText, default=None, comment='商品详情')
    status: Mapped[str] = mapped_column(
        sa.String(16), default='draft', comment='状态: draft/on_sale/off_sale/deleted'
    )
    sort_order: Mapped[int] = mapped_column(sa.Integer, default=0, comment='排序权重')
    sales_count: Mapped[int] = mapped_column(sa.Integer, default=0, comment='销量')
    virtual_sales: Mapped[int] = mapped_column(sa.Integer, default=0, comment='虚拟销量')
    view_count: Mapped[int] = mapped_column(sa.Integer, default=0, comment='浏览量')
    on_sale_time: Mapped[datetime | None] = mapped_column(TimeZone, default=None, comment='上架时间')
    off_sale_time: Mapped[datetime | None] = mapped_column(TimeZone, default=None, comment='下架时间')

    # ============ 关系 ============
    category: Mapped[ProductCategory] = relationship(init=False, back_populates='products', lazy='noload')
    skus: Mapped[list[ProductSKU]] = relationship(
        init=False,
        back_populates='product',
        lazy='noload',
        cascade='all, delete-orphan',
    )


class ProductSKU(Base, UserMixin):
    """商品 SKU 表"""

    __tablename__ = 'mall_product_sku'
    __table_args__ = (
        sa.Index('idx_sku_product_status', 'product_id', 'is_active'),
        sa.CheckConstraint('price >= 0', name='ck_sku_price'),
        sa.CheckConstraint('original_price >= 0', name='ck_sku_original_price'),
        sa.CheckConstraint('stock >= 0', name='ck_sku_stock'),
        sa.CheckConstraint('sales_count >= 0', name='ck_sku_sales'),
        {'comment': '商品 SKU 表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    product_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('mall_product.id', ondelete='CASCADE'),
        comment='商品 ID',
    )
    sku_name: Mapped[str] = mapped_column(sa.String(128), comment='SKU 名称')
    price: Mapped[Decimal] = mapped_column(sa.Numeric(10, 2), comment='售价')
    sku_code: Mapped[str | None] = mapped_column(sa.String(64), default=None, unique=True, comment='SKU 编码')
    specs: Mapped[dict | None] = mapped_column(CompatibleJSONB, default=None, comment='规格属性 JSON')
    original_price: Mapped[Decimal | None] = mapped_column(
        sa.Numeric(10, 2), default=None, comment='原价'
    )
    stock: Mapped[int] = mapped_column(sa.Integer, default=0, comment='库存')
    sales_count: Mapped[int] = mapped_column(sa.Integer, default=0, comment='销量')
    image: Mapped[str | None] = mapped_column(sa.String(512), default=None, comment='SKU 图片')
    is_active: Mapped[bool] = mapped_column(default=True, comment='是否启用')

    # ============ 关系 ============
    product: Mapped[Product] = relationship(init=False, back_populates='skus', lazy='noload')
