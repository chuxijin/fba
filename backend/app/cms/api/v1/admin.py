#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Annotated

from fastapi import APIRouter, Path, Query, Request

from backend.app.cms.schema.slot import (
    CreateSlotParam,
    GetSlotDetail,
    SlotStatsResult,
    UpdateSlotParam,
)
from backend.app.cms.service.slot_service import slot_service
from backend.app.cms.service.stats_service import stats_service
from backend.common.pagination import DependsPagination
from backend.common.response.response_schema import ResponseModel, ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.database.db import CurrentSession

router = APIRouter(prefix='/cms/admin', tags=['内容运营位-管理端'])


@router.post('/slots', summary='创建运营位', dependencies=[DependsJwtAuth])
async def create_slot(
    request: Request,
    db: CurrentSession,
    obj: CreateSlotParam,
) -> ResponseSchemaModel[GetSlotDetail]:
    """创建运营位"""
    data = await slot_service.create_slot(db=db, user_id=request.user.id, obj=obj)
    return response_base.success(data=data)


@router.put('/slots/{pk}', summary='更新运营位', dependencies=[DependsJwtAuth])
async def update_slot(
    db: CurrentSession,
    pk: Annotated[int, Path(description='运营位 ID')],
    obj: UpdateSlotParam,
) -> ResponseModel:
    """更新运营位"""
    count = await slot_service.update_slot(db=db, pk=pk, obj=obj)
    return response_base.success(data={'updated': count})


@router.delete('/slots/{pk}', summary='删除运营位', dependencies=[DependsJwtAuth])
async def delete_slot(
    db: CurrentSession,
    pk: Annotated[int, Path(description='运营位 ID')],
) -> ResponseModel:
    """删除运营位(暂存请用 status=2 下线)"""
    count = await slot_service.delete_slot(db=db, pk=pk)
    return response_base.success(data={'deleted': count})


@router.get('/slots', summary='管理端获取运营位列表', dependencies=[DependsJwtAuth, DependsPagination])
async def get_slot_list(
    db: CurrentSession,
    status: Annotated[int | None, Query(description='状态过滤')] = None,
    slot_type: Annotated[str | None, Query(description='形态过滤')] = None,
    scene: Annotated[str | None, Query(description='场景过滤')] = None,
    keyword: Annotated[str | None, Query(description='搜索关键词')] = None,
) -> ResponseModel:
    """管理端获取运营位列表"""
    data = await slot_service.get_slot_list(
        db=db, status=status, slot_type=slot_type, scene=scene, keyword=keyword
    )
    return response_base.success(data=data)


@router.get('/slots/{pk}', summary='获取运营位详情', dependencies=[DependsJwtAuth])
async def get_slot_detail(
    db: CurrentSession,
    pk: Annotated[int, Path(description='运营位 ID')],
) -> ResponseSchemaModel[GetSlotDetail]:
    """获取运营位详情"""
    data = await slot_service.get_slot_detail(db=db, pk=pk)
    return response_base.success(data=data)


@router.get('/slots/{pk}/stats', summary='获取运营位数据统计', dependencies=[DependsJwtAuth])
async def get_slot_stats(
    db: CurrentSession,
    pk: Annotated[int, Path(description='运营位 ID')],
    days: Annotated[int, Query(ge=1, le=365, description='统计天数')] = 7,
) -> ResponseSchemaModel[SlotStatsResult]:
    """获取运营位数据统计(曝光/点击/关闭/CTR)"""
    data = await stats_service.get_slot_stats(db=db, slot_id=pk, days=days)
    return response_base.success(data=data)
