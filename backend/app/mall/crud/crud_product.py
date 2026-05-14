#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.mall.model.product import Product, ProductCategory, ProductSKU
from backend.app.mall.schema.product import (
    CreateProductCategoryParam,
    CreateProductParam,
    CreateProductSKUParam,
    UpdateProductCategoryParam,
    UpdateProductParam,
    UpdateProductSKUParam,
)


class CRUDProductCategory(CRUDPlus[ProductCategory]):
    """商品分类数据库操作类"""

    async def get(self, db: AsyncSession, category_id: int) -> ProductCategory | None:
        """
        获取分类详情

        :param db: 数据库会话
        :param category_id: 分类 ID
        :return:
        """
        return await self.select_model(db, category_id)

    async def get_by_parent(self, db: AsyncSession, parent_id: int | None = None) -> list[ProductCategory]:
        """
        获取子分类列表

        :param db: 数据库会话
        :param parent_id: 父级分类 ID
        :return:
        """
        filters = {'parent_id': parent_id}
        return await self.select_models(db, **filters)

    async def create(self, db: AsyncSession, obj_in: CreateProductCategoryParam, user_id: int) -> ProductCategory:
        """
        创建商品分类

        :param db: 数据库会话
        :param obj_in: 创建参数
        :param user_id: 创建者 ID
        :return:
        """
        return await self.create_model(db, obj_in, created_by=user_id)

    async def update(
        self, db: AsyncSession, category_id: int, obj_in: UpdateProductCategoryParam
    ) -> int:
        """
        更新商品分类

        :param db: 数据库会话
        :param category_id: 分类 ID
        :param obj_in: 更新参数
        :return:
        """
        update_data = obj_in.model_dump(exclude_unset=True)
        return await self.update_model(db, category_id, update_data)


class CRUDProduct(CRUDPlus[Product]):
    """商品数据库操作类"""

    async def get(self, db: AsyncSession, product_id: int) -> Product | None:
        """
        获取商品详情

        :param db: 数据库会话
        :param product_id: 商品 ID
        :return:
        """
        return await self.select_model(db, product_id)

    async def get_by_category(self, db: AsyncSession, category_id: int) -> list[Product]:
        """
        获取分类下的商品列表

        :param db: 数据库会话
        :param category_id: 分类 ID
        :return:
        """
        filters = {'category_id': category_id}
        return await self.select_models(db, **filters)

    async def get_on_sale_products(self, db: AsyncSession, limit: int = 20) -> list[Product]:
        """
        获取在售商品列表

        :param db: 数据库会话
        :param limit: 数量限制
        :return:
        """
        stmt = select(Product).where(Product.status == 'on_sale').order_by(Product.sort_order.desc()).limit(limit)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def create(self, db: AsyncSession, obj_in: CreateProductParam, user_id: int) -> Product:
        """
        创建商品

        :param db: 数据库会话
        :param obj_in: 创建参数
        :param user_id: 创建者 ID
        :return:
        """
        return await self.create_model(db, obj_in, created_by=user_id)

    async def update(self, db: AsyncSession, product_id: int, obj_in: UpdateProductParam) -> int:
        """
        更新商品

        :param db: 数据库会话
        :param product_id: 商品 ID
        :param obj_in: 更新参数
        :return:
        """
        update_data = obj_in.model_dump(exclude_unset=True)
        return await self.update_model(db, product_id, update_data)

    async def increment_view_count(self, db: AsyncSession, product_id: int) -> int:
        """
        增加商品浏览量

        :param db: 数据库会话
        :param product_id: 商品 ID
        :return:
        """
        product = await self.get(db, product_id)
        if not product:
            return 0
        return await self.update_model(db, product_id, {'view_count': product.view_count + 1})


class CRUDProductSKU(CRUDPlus[ProductSKU]):
    """商品 SKU 数据库操作类"""

    async def get(self, db: AsyncSession, sku_id: int) -> ProductSKU | None:
        """
        获取 SKU 详情

        :param db: 数据库会话
        :param sku_id: SKU ID
        :return:
        """
        return await self.select_model(db, sku_id)

    async def get_by_product(self, db: AsyncSession, product_id: int) -> list[ProductSKU]:
        """
        获取商品的 SKU 列表

        :param db: 数据库会话
        :param product_id: 商品 ID
        :return:
        """
        filters = {'product_id': product_id}
        return await self.select_models(db, **filters)

    async def get_by_code(self, db: AsyncSession, sku_code: str) -> ProductSKU | None:
        """
        通过 SKU 编码获取 SKU

        :param db: 数据库会话
        :param sku_code: SKU 编码
        :return:
        """
        stmt = select(ProductSKU).where(ProductSKU.sku_code == sku_code)
        result = await db.execute(stmt)
        return result.scalars().first()

    async def create(self, db: AsyncSession, obj_in: CreateProductSKUParam, user_id: int) -> ProductSKU:
        """
        创建 SKU

        :param db: 数据库会话
        :param obj_in: 创建参数
        :param user_id: 创建者 ID
        :return:
        """
        return await self.create_model(db, obj_in, created_by=user_id)

    async def update(self, db: AsyncSession, sku_id: int, obj_in: UpdateProductSKUParam) -> int:
        """
        更新 SKU

        :param db: 数据库会话
        :param sku_id: SKU ID
        :param obj_in: 更新参数
        :return:
        """
        update_data = obj_in.model_dump(exclude_unset=True)
        return await self.update_model(db, sku_id, update_data)

    async def deduct_stock(self, db: AsyncSession, sku_id: int, quantity: int) -> bool:
        """
        扣减库存

        :param db: 数据库会话
        :param sku_id: SKU ID
        :param quantity: 扣减数量
        :return:
        """
        sku = await self.get(db, sku_id)
        if not sku or sku.stock < quantity:
            return False
        await self.update_model(db, sku_id, {'stock': sku.stock - quantity})
        return True


product_category_dao = CRUDProductCategory(ProductCategory)
product_dao = CRUDProduct(Product)
product_sku_dao = CRUDProductSKU(ProductSKU)
