#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import logging

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.mall.crud.crud_product import product_category_dao, product_dao, product_sku_dao
from backend.app.mall.model.product import Product, ProductCategory, ProductSKU
from backend.app.mall.schema.product import (
    CreateProductCategoryParam,
    CreateProductParam,
    CreateProductSKUParam,
    UpdateProductCategoryParam,
    UpdateProductParam,
    UpdateProductSKUParam,
)
from backend.common.exception import errors

log = logging.getLogger(__name__)


class ProductService:
    """商品服务类"""

    @staticmethod
    async def get_category(*, db: AsyncSession, category_id: int) -> ProductCategory:
        """
        获取商品分类详情

        :param db: 数据库会话
        :param category_id: 分类 ID
        :return:
        """
        category = await product_category_dao.get(db, category_id)
        if not category:
            raise errors.NotFoundError(msg='商品分类不存在')
        return category

    @staticmethod
    async def get_category_list(*, db: AsyncSession, parent_id: int | None = None) -> list[ProductCategory]:
        """
        获取商品分类列表

        :param db: 数据库会话
        :param parent_id: 父级分类 ID
        :return:
        """
        return await product_category_dao.get_by_parent(db, parent_id)

    @staticmethod
    async def create_category(
        *, db: AsyncSession, obj: CreateProductCategoryParam, user_id: int
    ) -> ProductCategory:
        """
        创建商品分类

        :param db: 数据库会话
        :param obj: 创建参数
        :param user_id: 创建者 ID
        :return:
        """
        if obj.parent_id:
            parent = await product_category_dao.get(db, obj.parent_id)
            if not parent:
                raise errors.NotFoundError(msg='父级分类不存在')
        return await product_category_dao.create(db, obj, user_id)

    @staticmethod
    async def update_category(
        *, db: AsyncSession, category_id: int, obj: UpdateProductCategoryParam
    ) -> int:
        """
        更新商品分类

        :param db: 数据库会话
        :param category_id: 分类 ID
        :param obj: 更新参数
        :return:
        """
        category = await product_category_dao.get(db, category_id)
        if not category:
            raise errors.NotFoundError(msg='商品分类不存在')
        return await product_category_dao.update(db, category_id, obj)

    @staticmethod
    async def delete_category(*, db: AsyncSession, category_id: int) -> int:
        """
        删除商品分类

        :param db: 数据库会话
        :param category_id: 分类 ID
        :return:
        """
        category = await product_category_dao.get(db, category_id)
        if not category:
            raise errors.NotFoundError(msg='商品分类不存在')
        products = await product_dao.get_by_category(db, category_id)
        if products:
            raise errors.ForbiddenError(msg='该分类下存在商品，无法删除')
        return await product_category_dao.delete_model(db, category_id)

    @staticmethod
    async def get_product(*, db: AsyncSession, product_id: int, increment_view: bool = False) -> Product:
        """
        获取商品详情

        :param db: 数据库会话
        :param product_id: 商品 ID
        :param increment_view: 是否增加浏览量
        :return:
        """
        product = await product_dao.get(db, product_id)
        if not product:
            raise errors.NotFoundError(msg='商品不存在')
        if increment_view:
            await product_dao.increment_view_count(db, product_id)
        return product

    @staticmethod
    async def get_product_list(*, db: AsyncSession, category_id: int | None = None) -> list[Product]:
        """
        获取商品列表

        :param db: 数据库会话
        :param category_id: 分类 ID
        :return:
        """
        if category_id:
            return await product_dao.get_by_category(db, category_id)
        return await product_dao.get_on_sale_products(db)

    @staticmethod
    async def create_product(*, db: AsyncSession, obj: CreateProductParam, user_id: int) -> Product:
        """
        创建商品

        :param db: 数据库会话
        :param obj: 创建参数
        :param user_id: 创建者 ID
        :return:
        """
        category = await product_category_dao.get(db, obj.category_id)
        if not category:
            raise errors.NotFoundError(msg='商品分类不存在')
        return await product_dao.create(db, obj, user_id)

    @staticmethod
    async def update_product(*, db: AsyncSession, product_id: int, obj: UpdateProductParam) -> int:
        """
        更新商品

        :param db: 数据库会话
        :param product_id: 商品 ID
        :param obj: 更新参数
        :return:
        """
        product = await product_dao.get(db, product_id)
        if not product:
            raise errors.NotFoundError(msg='商品不存在')
        if obj.category_id:
            category = await product_category_dao.get(db, obj.category_id)
            if not category:
                raise errors.NotFoundError(msg='商品分类不存在')
        return await product_dao.update(db, product_id, obj)

    @staticmethod
    async def delete_product(*, db: AsyncSession, product_id: int) -> int:
        """
        删除商品

        :param db: 数据库会话
        :param product_id: 商品 ID
        :return:
        """
        product = await product_dao.get(db, product_id)
        if not product:
            raise errors.NotFoundError(msg='商品不存在')
        return await product_dao.delete_model(db, product_id)

    @staticmethod
    async def get_sku(*, db: AsyncSession, sku_id: int) -> ProductSKU:
        """
        获取 SKU 详情

        :param db: 数据库会话
        :param sku_id: SKU ID
        :return:
        """
        sku = await product_sku_dao.get(db, sku_id)
        if not sku:
            raise errors.NotFoundError(msg='SKU 不存在')
        return sku

    @staticmethod
    async def get_sku_list(*, db: AsyncSession, product_id: int) -> list[ProductSKU]:
        """
        获取商品的 SKU 列表

        :param db: 数据库会话
        :param product_id: 商品 ID
        :return:
        """
        return await product_sku_dao.get_by_product(db, product_id)

    @staticmethod
    async def create_sku(*, db: AsyncSession, obj: CreateProductSKUParam, user_id: int) -> ProductSKU:
        """
        创建 SKU

        :param db: 数据库会话
        :param obj: 创建参数
        :param user_id: 创建者 ID
        :return:
        """
        product = await product_dao.get(db, obj.product_id)
        if not product:
            raise errors.NotFoundError(msg='商品不存在')
        if obj.sku_code:
            existing_sku = await product_sku_dao.get_by_code(db, obj.sku_code)
            if existing_sku:
                raise errors.ForbiddenError(msg='SKU 编码已存在')
        return await product_sku_dao.create(db, obj, user_id)

    @staticmethod
    async def update_sku(*, db: AsyncSession, sku_id: int, obj: UpdateProductSKUParam) -> int:
        """
        更新 SKU

        :param db: 数据库会话
        :param sku_id: SKU ID
        :param obj: 更新参数
        :return:
        """
        sku = await product_sku_dao.get(db, sku_id)
        if not sku:
            raise errors.NotFoundError(msg='SKU 不存在')
        if obj.sku_code and obj.sku_code != sku.sku_code:
            existing_sku = await product_sku_dao.get_by_code(db, obj.sku_code)
            if existing_sku:
                raise errors.ForbiddenError(msg='SKU 编码已存在')
        return await product_sku_dao.update(db, sku_id, obj)

    @staticmethod
    async def delete_sku(*, db: AsyncSession, sku_id: int) -> int:
        """
        删除 SKU

        :param db: 数据库会话
        :param sku_id: SKU ID
        :return:
        """
        sku = await product_sku_dao.get(db, sku_id)
        if not sku:
            raise errors.NotFoundError(msg='SKU 不存在')
        return await product_sku_dao.delete_model(db, sku_id)


product_service = ProductService()
