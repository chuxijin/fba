#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Annotated

from fastapi import APIRouter, Path, Query, Request

from backend.app.memory_card.schema.card import (
    CreateCardParam,
    CreateDeckParam,
    CreateGroupParam,
    GetCardDetail,
    GetDeckDetail,
    GetGroupDetail,
    UpdateCardParam,
    UpdateDeckParam,
    UpdateGroupParam,
)
from backend.app.memory_card.service.card_service import card_service
from backend.app.memory_card.service.study_service import study_service
from backend.common.pagination import DependsPagination
from backend.common.response.response_schema import ResponseModel, ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.database.db import CurrentSession, CurrentSessionTransaction

router = APIRouter(prefix='/memory-cards/admin', tags=['记忆卡管理'], dependencies=[DependsJwtAuth])


# ============ 卡组管理 ============
@router.post('/decks', summary='创建记忆卡组', name='memory_admin_create_deck')
async def create_deck(
    request: Request,
    db: CurrentSessionTransaction,
    obj: CreateDeckParam,
) -> ResponseSchemaModel[GetDeckDetail]:
    """创建公共卡组"""
    data = await card_service.create_deck(db=db, user_id=request.user.id, obj=obj, scope='system')
    return response_base.success(data=data)


@router.get('/decks', summary='记忆卡组分页列表', name='memory_admin_get_decks', dependencies=[DependsPagination])
async def get_deck_list(
    db: CurrentSession,
    scope: Annotated[str | None, Query(description='范围 system/personal')] = None,
    status: Annotated[str | None, Query(description='状态')] = None,
    category_id: Annotated[int | None, Query(gt=0, description='领域分类 ID')] = None,
    keyword: Annotated[str | None, Query(description='搜索关键词')] = None,
) -> ResponseModel:
    """获取卡组分页列表"""
    data = await card_service.page_decks(db=db, scope=scope, status=status, category_id=category_id, keyword=keyword)
    return response_base.success(data=data)


@router.get('/decks/{pk}', summary='记忆卡组详情', name='memory_admin_get_deck_detail')
async def get_deck_detail(
    db: CurrentSession,
    pk: Annotated[int, Path(description='卡组 ID')],
) -> ResponseSchemaModel[GetDeckDetail]:
    """获取卡组详情"""
    data = await card_service.get_deck_detail(db=db, pk=pk)
    return response_base.success(data=data)


@router.get('/decks/{pk}/groups', summary='卡组分组树', name='memory_admin_get_deck_groups')
async def get_deck_groups(
    db: CurrentSession,
    pk: Annotated[int, Path(description='卡组 ID')],
) -> ResponseSchemaModel[list[GetGroupDetail]]:
    """获取卡组的分组树（章/节）"""
    data = await card_service.get_group_tree(db=db, deck_id=pk)
    return response_base.success(data=data)


@router.post('/groups', summary='创建分组', name='memory_admin_create_group')
async def create_group(
    request: Request,
    db: CurrentSessionTransaction,
    obj: CreateGroupParam,
) -> ResponseSchemaModel[GetGroupDetail]:
    """在卡组下创建分组（章/节）"""
    data = await card_service.create_group(db=db, user_id=request.user.id, obj=obj)
    return response_base.success(data=data)


@router.put('/groups/{pk}', summary='更新分组', name='memory_admin_update_group')
async def update_group(
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='分组 ID')],
    obj: UpdateGroupParam,
) -> ResponseModel:
    """更新分组（改名/移动/排序/状态）"""
    count = await card_service.update_group(db=db, pk=pk, obj=obj)
    return response_base.success(data={'updated': count})


@router.delete('/groups/{pk}', summary='删除分组', name='memory_admin_delete_group')
async def delete_group(
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='分组 ID')],
) -> ResponseModel:
    """删除分组及其子分组，组内卡片移回卡组根目录"""
    count = await card_service.delete_group(db=db, pk=pk)
    return response_base.success(data={'deleted': count})


@router.put('/decks/{pk}', summary='更新记忆卡组', name='memory_admin_update_deck')
async def update_deck(
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='卡组 ID')],
    obj: UpdateDeckParam,
) -> ResponseModel:
    """更新卡组"""
    count = await card_service.update_deck(db=db, pk=pk, obj=obj)
    return response_base.success(data={'updated': count})


@router.delete('/decks/{pk}', summary='删除记忆卡组', name='memory_admin_delete_deck')
async def delete_deck(
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='卡组 ID')],
) -> ResponseModel:
    """删除卡组"""
    count = await card_service.delete_deck(db=db, pk=pk)
    return response_base.success(data={'deleted': count})


# ============ 卡片管理 ============
@router.post('/cards', summary='创建记忆卡', name='memory_admin_create_card')
async def create_card(
    request: Request,
    db: CurrentSessionTransaction,
    obj: CreateCardParam,
) -> ResponseSchemaModel[GetCardDetail]:
    """创建卡片并发布初始版本"""
    data = await card_service.create_card(db=db, user_id=request.user.id, obj=obj)
    return response_base.success(data=data)


@router.get('/cards', summary='记忆卡分页列表', name='memory_admin_get_cards', dependencies=[DependsPagination])
async def get_card_list(
    db: CurrentSession,
    deck_id: Annotated[int | None, Query(gt=0, description='卡组 ID')] = None,
    group_id: Annotated[int | None, Query(gt=0, description='分组 ID')] = None,
    status: Annotated[str | None, Query(description='状态')] = None,
    keyword: Annotated[str | None, Query(description='搜索关键词')] = None,
) -> ResponseModel:
    """获取卡片分页列表"""
    data = await card_service.page_cards(db=db, deck_id=deck_id, group_id=group_id, status=status, keyword=keyword)
    return response_base.success(data=data)


@router.get('/cards/{pk}', summary='记忆卡详情', name='memory_admin_get_card_detail')
async def get_card_detail(
    db: CurrentSession,
    pk: Annotated[int, Path(description='卡片 ID')],
) -> ResponseSchemaModel[GetCardDetail]:
    """获取卡片详情（含当前发布内容）"""
    data = await card_service.get_card_detail(db=db, pk=pk)
    return response_base.success(data=data)


@router.put('/cards/{pk}', summary='更新记忆卡', name='memory_admin_update_card')
async def update_card(
    request: Request,
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='卡片 ID')],
    obj: UpdateCardParam,
) -> ResponseModel:
    """更新卡片；内容变化时发布新版本"""
    count = await card_service.update_card(db=db, pk=pk, obj=obj, user_id=request.user.id)
    return response_base.success(data={'updated': count})


@router.delete('/cards/{pk}', summary='删除记忆卡', name='memory_admin_delete_card')
async def delete_card(
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='卡片 ID')],
) -> ResponseModel:
    """删除卡片"""
    count = await card_service.delete_card(db=db, pk=pk)
    return response_base.success(data={'deleted': count})


# ============ 复习日志 ============
@router.get('/reviews', summary='复习日志分页列表', name='memory_admin_get_reviews', dependencies=[DependsPagination])
async def get_review_log_list(
    db: CurrentSession,
    user_id: Annotated[int | None, Query(gt=0, description='用户 ID')] = None,
    card_id: Annotated[int | None, Query(gt=0, description='卡片 ID')] = None,
    rating: Annotated[int | None, Query(ge=1, le=4, description='评分')] = None,
) -> ResponseModel:
    """获取复习日志分页列表"""
    stmt = study_service.review_log_list_select(user_id=user_id, card_id=card_id, rating=rating)
    data = await study_service.page_review_logs(db=db, stmt=stmt)
    return response_base.success(data=data)
