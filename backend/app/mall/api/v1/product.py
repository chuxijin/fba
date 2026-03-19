#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Annotated

from fastapi import APIRouter, Path, Query, Request

from backend.app.mall.schema.product import (
    CreateProductCategoryParam,
    CreateProductParam,
    CreateProductSKUParam,
    GetProductCategoryListItem,
    GetProductDetail,
    GetProductListItem,
    GetProductSKUListItem,
    UpdateProductCategoryParam,
    UpdateProductParam,
    UpdateProductSKUParam,
)
from backend.app.mall.service.product_service import product_service
from backend.common.response.response_schema import ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.database.db import CurrentSession

router = APIRouter(prefix='/product', tags=['商品管理'])


# ===== 商品分类 =====
@router.get('/category/list', summary='获取商品分类列表')
async def get_category_list(
    db: CurrentSession,
    parent_id: Annotated[int | None, Query(description='父级分类 ID')] = None,
) -> ResponseSchemaModel[list[GetProductCategoryListItem]]:
    """获取商品分类列表"""
    categories = await product_service.get_category_list(db=db, parent_id=parent_id)
    data = [GetProductCategoryListItem.model_validate(cat) for cat in categories]
    return response_base.success(data=data)


@router.get('/category/{category_id}', summary='获取商品分类详情')
async def get_category_detail(
    db: CurrentSession,
    category_id: Annotated[int, Path(description='分类 ID')],
) -> ResponseSchemaModel[GetProductCategoryListItem]:
    """获取商品分类详情"""
    category = await product_service.get_category(db=db, category_id=category_id)
    return response_base.success(data=GetProductCategoryListItem.model_validate(category))


@router.post('/category', summary='创建商品分类', dependencies=[DependsJwtAuth])
async def create_category(
    request: Request,
    db: CurrentSession,
    obj: CreateProductCategoryParam,
) -> ResponseSchemaModel[GetProductCategoryListItem]:
    """创建商品分类"""
    category = await product_service.create_category(db=db, obj=obj, user_id=request.user.id)
    return response_base.success(data=GetProductCategoryListItem.model_validate(category))


@router.put('/category/{category_id}', summary='更新商品分类', dependencies=[DependsJwtAuth])
async def update_category(
    db: CurrentSession,
    category_id: Annotated[int, Path(description='分类 ID')],
    obj: UpdateProductCategoryParam,
) -> ResponseSchemaModel[int]:
    """更新商品分类"""
    count = await product_service.update_category(db=db, category_id=category_id, obj=obj)
    return response_base.success(data=count)


@router.delete('/category/{category_id}', summary='删除商品分类', dependencies=[DependsJwtAuth])
async def delete_category(
    db: CurrentSession,
    category_id: Annotated[int, Path(description='分类 ID')],
) -> ResponseSchemaModel[int]:
    """删除商品分类"""
    count = await product_service.delete_category(db=db, category_id=category_id)
    return response_base.success(data=count)


# ===== 商品 =====
@router.get('/list', summary='获取商品列表')
async def get_product_list(
    db: CurrentSession,
    category_id: Annotated[int | None, Query(description='分类 ID')] = None,
) -> ResponseSchemaModel[list[GetProductListItem]]:
    """获取商品列表"""
    products = await product_service.get_product_list(db=db, category_id=category_id)
    data = [GetProductListItem.model_validate(prod) for prod in products]
    return response_base.success(data=data)


@router.get('/{product_id}', summary='获取商品详情')
async def get_product_detail(
    db: CurrentSession,
    product_id: Annotated[int, Path(description='商品 ID')],
    increment_view: Annotated[bool, Query(description='是否增加浏览量')] = False,
) -> ResponseSchemaModel[GetProductDetail]:
    """获取商品详情"""
    product = await product_service.get_product(db=db, product_id=product_id, increment_view=increment_view)
    return response_base.success(data=GetProductDetail.model_validate(product))


@router.post('', summary='创建商品', dependencies=[DependsJwtAuth])
async def create_product(
    request: Request,
    db: CurrentSession,
    obj: CreateProductParam,
) -> ResponseSchemaModel[GetProductDetail]:
    """创建商品"""
    product = await product_service.create_product(db=db, obj=obj, user_id=request.user.id)
    return response_base.success(data=GetProductDetail.model_validate(product))


@router.put('/{product_id}', summary='更新商品', dependencies=[DependsJwtAuth])
async def update_product(
    db: CurrentSession,
    product_id: Annotated[int, Path(description='商品 ID')],
    obj: UpdateProductParam,
) -> ResponseSchemaModel[int]:
    """更新商品"""
    count = await product_service.update_product(db=db, product_id=product_id, obj=obj)
    return response_base.success(data=count)


@router.delete('/{product_id}', summary='删除商品', dependencies=[DependsJwtAuth])
async def delete_product(
    db: CurrentSession,
    product_id: Annotated[int, Path(description='商品 ID')],
) -> ResponseSchemaModel[int]:
    """删除商品"""
    count = await product_service.delete_product(db=db, product_id=product_id)
    return response_base.success(data=count)


# ===== SKU =====
@router.get('/{product_id}/sku/list', summary='获取商品 SKU 列表')
async def get_sku_list(
    db: CurrentSession,
    product_id: Annotated[int, Path(description='商品 ID')],
) -> ResponseSchemaModel[list[GetProductSKUListItem]]:
    """获取商品 SKU 列表"""
    skus = await product_service.get_sku_list(db=db, product_id=product_id)
    data = [GetProductSKUListItem.model_validate(sku) for sku in skus]
    return response_base.success(data=data)


@router.get('/sku/{sku_id}', summary='获取 SKU 详情')
async def get_sku_detail(
    db: CurrentSession,
    sku_id: Annotated[int, Path(description='SKU ID')],
) -> ResponseSchemaModel[GetProductSKUListItem]:
    """获取 SKU 详情"""
    sku = await product_service.get_sku(db=db, sku_id=sku_id)
    return response_base.success(data=GetProductSKUListItem.model_validate(sku))


@router.post('/sku', summary='创建 SKU', dependencies=[DependsJwtAuth])
async def create_sku(
    request: Request,
    db: CurrentSession,
    obj: CreateProductSKUParam,
) -> ResponseSchemaModel[GetProductSKUListItem]:
    """创建 SKU"""
    sku = await product_service.create_sku(db=db, obj=obj, user_id=request.user.id)
    return response_base.success(data=GetProductSKUListItem.model_validate(sku))


@router.put('/sku/{sku_id}', summary='更新 SKU', dependencies=[DependsJwtAuth])
async def update_sku(
    db: CurrentSession,
    sku_id: Annotated[int, Path(description='SKU ID')],
    obj: UpdateProductSKUParam,
) -> ResponseSchemaModel[int]:
    """更新 SKU"""
    count = await product_service.update_sku(db=db, sku_id=sku_id, obj=obj)
    return response_base.success(data=count)


@router.delete('/sku/{sku_id}', summary='删除 SKU', dependencies=[DependsJwtAuth])
async def delete_sku(
    db: CurrentSession,
    sku_id: Annotated[int, Path(description='SKU ID')],
) -> ResponseSchemaModel[int]:
    """删除 SKU"""
    count = await product_service.delete_sku(db=db, sku_id=sku_id)
    return response_base.success(data=count)
