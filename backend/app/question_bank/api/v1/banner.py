#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query

from backend.app.question_bank.schema.banner import (
    CreateBannerParam,
    GetActiveBanner,
    GetBannerDetail,
    UpdateBannerParam,
)
from backend.app.question_bank.service.banner_service import BannerService
from backend.common.response.response_schema import ResponseModel, ResponseSchemaModel, response_base
from backend.common.security.permission import RequestPermission
from backend.common.security.rbac import DependsRBAC
from backend.database.db import CurrentSession, CurrentSessionTransaction

router = APIRouter()

banner_service = BannerService()


@router.get('', summary='获取启用的轮播图列表', name='qbank_get_active_banners')
async def get_active_banners(
    db: CurrentSession,
    scene: Annotated[str | None, Query(description='展示场景筛选')] = None,
) -> ResponseSchemaModel[list[GetActiveBanner]]:
    """🌍 公开接口 - 获取启用且在有效期内的轮播图"""
    data = await banner_service.get_active_list(db=db, scene=scene)
    return response_base.success(data=data)


@router.post('/{pk}/click', summary='记录轮播图点击', name='qbank_click_banner')
async def click_banner(
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='轮播图 ID')],
) -> ResponseModel:
    """🌍 公开接口 - 记录轮播图点击次数"""
    await banner_service.increment_click(db=db, pk=pk)
    return response_base.success()


@router.get(
    '/admin',
    summary='获取轮播图列表（管理）',
    name='qbank_admin_get_banners',
    dependencies=[
        Depends(RequestPermission('question_bank:banner:read')),
        DependsRBAC,
    ],
)
async def get_banners(
    db: CurrentSession,
    status: Annotated[int | None, Query(description='状态筛选')] = None,
    scene: Annotated[str | None, Query(description='展示场景筛选')] = None,
) -> ResponseSchemaModel[list[GetBannerDetail]]:
    """🔐 管理员接口 - 获取轮播图列表"""
    data = await banner_service.get_list(db=db, status=status, scene=scene)
    return response_base.success(data=data)


@router.get(
    '/{pk}',
    summary='获取轮播图详情（管理）',
    name='qbank_admin_get_banner',
    dependencies=[
        Depends(RequestPermission('question_bank:banner:read')),
        DependsRBAC,
    ],
)
async def get_banner(
    db: CurrentSession,
    pk: Annotated[int, Path(description='轮播图 ID')],
) -> ResponseSchemaModel[GetBannerDetail]:
    """🔐 管理员接口 - 获取轮播图详情"""
    data = await banner_service.get(db=db, pk=pk)
    return response_base.success(data=data)


@router.post(
    '',
    summary='创建轮播图',
    name='qbank_admin_create_banner',
    dependencies=[
        Depends(RequestPermission('question_bank:banner:create')),
        DependsRBAC,
    ],
)
async def create_banner(db: CurrentSessionTransaction, obj: CreateBannerParam) -> ResponseModel:
    """🔐 管理员接口 - 创建轮播图"""
    await banner_service.create(db=db, obj_in=obj)
    return response_base.success()


@router.put(
    '/{pk}',
    summary='更新轮播图',
    name='qbank_admin_update_banner',
    dependencies=[
        Depends(RequestPermission('question_bank:banner:update')),
        DependsRBAC,
    ],
)
async def update_banner(
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='轮播图 ID')],
    obj: UpdateBannerParam,
) -> ResponseModel:
    """🔐 管理员接口 - 更新轮播图"""
    await banner_service.update(db=db, pk=pk, obj_in=obj)
    return response_base.success()


@router.delete(
    '/{pk}',
    summary='删除轮播图',
    name='qbank_admin_delete_banner',
    dependencies=[
        Depends(RequestPermission('question_bank:banner:delete')),
        DependsRBAC,
    ],
)
async def delete_banner(
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='轮播图 ID')],
) -> ResponseModel:
    """🔐 管理员接口 - 删除轮播图"""
    await banner_service.delete(db=db, pk=pk)
    return response_base.success()

