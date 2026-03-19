#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Annotated

from fastapi import APIRouter, Path, Query, Request

from backend.app.mall.schema.group_buy import (
    CreateGroupBuyActivityParam,
    CreateGroupBuyLadderPriceParam,
    GetGroupBuyActivityDetail,
    GetGroupBuyActivityListItem,
    GetGroupBuyLadderPriceItem,
    UpdateGroupBuyActivityParam,
)
from backend.app.mall.service.group_buy_service import group_buy_service
from backend.common.response.response_schema import ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.database.db import CurrentSession, CurrentSessionTransaction

router = APIRouter(prefix='/group-buy', tags=['拼团活动'])


# ===== 拼团活动 =====
@router.get('/activity/list', summary='获取拼团活动列表')
async def get_activity_list(
    db: CurrentSession,
    product_id: Annotated[int | None, Query(description='商品 ID')] = None,
) -> ResponseSchemaModel[list[GetGroupBuyActivityListItem]]:
    """获取拼团活动列表"""
    activities = await group_buy_service.get_activity_list(db=db, product_id=product_id)
    data = [GetGroupBuyActivityListItem.model_validate(act) for act in activities]
    return response_base.success(data=data)


@router.get('/activity/{activity_id}', summary='获取拼团活动详情')
async def get_activity_detail(
    db: CurrentSession,
    activity_id: Annotated[int, Path(description='活动 ID')],
) -> ResponseSchemaModel[GetGroupBuyActivityDetail]:
    """获取拼团活动详情"""
    activity = await group_buy_service.get_activity(db=db, activity_id=activity_id, with_prices=True)
    return response_base.success(data=GetGroupBuyActivityDetail.model_validate(activity))


@router.post('/activity', summary='创建拼团活动', dependencies=[DependsJwtAuth])
async def create_activity(
    request: Request,
    db: CurrentSessionTransaction,
    obj: CreateGroupBuyActivityParam,
) -> ResponseSchemaModel[GetGroupBuyActivityDetail]:
    """创建拼团活动"""
    activity = await group_buy_service.create_activity(db=db, obj=obj, user_id=request.user.id)
    activity_with_prices = await group_buy_service.get_activity(db=db, activity_id=activity.id, with_prices=True)
    return response_base.success(data=GetGroupBuyActivityDetail.model_validate(activity_with_prices))


@router.put('/activity/{activity_id}', summary='更新拼团活动', dependencies=[DependsJwtAuth])
async def update_activity(
    db: CurrentSession,
    activity_id: Annotated[int, Path(description='活动 ID')],
    obj: UpdateGroupBuyActivityParam,
) -> ResponseSchemaModel[int]:
    """更新拼团活动"""
    count = await group_buy_service.update_activity(db=db, activity_id=activity_id, obj=obj)
    return response_base.success(data=count)


@router.delete('/activity/{activity_id}', summary='删除拼团活动', dependencies=[DependsJwtAuth])
async def delete_activity(
    db: CurrentSession,
    activity_id: Annotated[int, Path(description='活动 ID')],
) -> ResponseSchemaModel[int]:
    """删除拼团活动"""
    count = await group_buy_service.delete_activity(db=db, activity_id=activity_id)
    return response_base.success(data=count)


# ===== 阶梯价格 =====
@router.get('/activity/{activity_id}/ladder-price/list', summary='获取阶梯价格列表')
async def get_ladder_price_list(
    db: CurrentSession,
    activity_id: Annotated[int, Path(description='活动 ID')],
) -> ResponseSchemaModel[list[GetGroupBuyLadderPriceItem]]:
    """获取阶梯价格列表"""
    prices = await group_buy_service.get_ladder_price_list(db=db, activity_id=activity_id)
    data = [GetGroupBuyLadderPriceItem.model_validate(price) for price in prices]
    return response_base.success(data=data)


@router.post('/activity/{activity_id}/ladder-price', summary='添加阶梯价格', dependencies=[DependsJwtAuth])
async def add_ladder_price(
    request: Request,
    db: CurrentSessionTransaction,
    activity_id: Annotated[int, Path(description='活动 ID')],
    obj: CreateGroupBuyLadderPriceParam,
) -> ResponseSchemaModel[GetGroupBuyLadderPriceItem]:
    """添加阶梯价格"""
    price = await group_buy_service.add_ladder_price(db=db, activity_id=activity_id, obj=obj, user_id=request.user.id)
    return response_base.success(data=GetGroupBuyLadderPriceItem.model_validate(price))


@router.delete('/ladder-price/{price_id}', summary='删除阶梯价格', dependencies=[DependsJwtAuth])
async def delete_ladder_price(
    db: CurrentSession,
    price_id: Annotated[int, Path(description='价格 ID')],
) -> ResponseSchemaModel[int]:
    """删除阶梯价格"""
    count = await group_buy_service.delete_ladder_price(db=db, price_id=price_id)
    return response_base.success(data=count)
