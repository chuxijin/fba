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
    UpdateGroupParam,
)
from backend.app.memory_card.schema.study import (
    CheckMemoryCardParam,
    CheckMemoryCardResult,
    GetMemoryCurve,
    GetMemoryDeckItem,
    GetMemoryForecast,
    GetMemoryOverview,
    GetStudyQueue,
    SubmitMemoryReviewParam,
    SubmitMemoryReviewResult,
)
from backend.app.memory_card.service.study_service import study_service
from backend.common.fsrs import ReviewForecast
from backend.common.response.response_schema import ResponseModel, ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.database.db import CurrentSession, CurrentSessionTransaction

router = APIRouter(prefix='/memory-cards', tags=['记忆卡学习'], dependencies=[DependsJwtAuth])


# ============ 概览与卡组 ============
@router.get('/overview', summary='记忆学习概览', name='memory_get_overview')
async def get_overview(
    request: Request,
    db: CurrentSession,
    category_id: Annotated[int | None, Query(gt=0, description='领域分类 ID，按当前领域过滤')] = None,
) -> ResponseSchemaModel[GetMemoryOverview]:
    """获取今日待复习、新卡与卡组概览"""
    data = await study_service.overview(db=db, user_id=request.user.id, category_id=category_id)
    return response_base.success(data=data)


@router.get('/decks', summary='可学习卡组列表', name='memory_get_decks')
async def get_decks(
    request: Request,
    db: CurrentSession,
    category_id: Annotated[int | None, Query(gt=0, description='领域分类 ID，按当前领域过滤')] = None,
) -> ResponseSchemaModel[list[GetMemoryDeckItem]]:
    """获取公共卡组与我的私人卡组"""
    data = await study_service.list_decks(db=db, user_id=request.user.id, category_id=category_id)
    return response_base.success(data=data)


@router.post('/decks', summary='创建私人卡组', name='memory_create_deck')
async def create_personal_deck(
    request: Request,
    db: CurrentSessionTransaction,
    obj: CreateDeckParam,
) -> ResponseSchemaModel[GetDeckDetail]:
    """用户创建私人卡组"""
    data = await study_service.create_personal_deck(db=db, user_id=request.user.id, obj=obj)
    return response_base.success(data=data)


@router.post('/decks/{deck_id}/subscribe', summary='订阅公共卡组', name='memory_subscribe_deck')
async def subscribe_deck(
    request: Request,
    db: CurrentSessionTransaction,
    deck_id: Annotated[int, Path(description='卡组 ID')],
) -> ResponseModel:
    """订阅公共卡组"""
    await study_service.subscribe_deck(db=db, user_id=request.user.id, deck_id=deck_id)
    return response_base.success()


@router.delete('/decks/{deck_id}/subscribe', summary='取消订阅公共卡组', name='memory_unsubscribe_deck')
async def unsubscribe_deck(
    request: Request,
    db: CurrentSessionTransaction,
    deck_id: Annotated[int, Path(description='卡组 ID')],
) -> ResponseModel:
    """取消订阅公共卡组"""
    await study_service.unsubscribe_deck(db=db, user_id=request.user.id, deck_id=deck_id)
    return response_base.success()


# ============ 分组管理（私人卡组） ============
@router.get('/decks/{deck_id}/groups', summary='卡组分组树', name='memory_get_deck_groups')
async def get_deck_groups(
    request: Request,
    db: CurrentSession,
    deck_id: Annotated[int, Path(description='卡组 ID')],
) -> ResponseSchemaModel[list[GetGroupDetail]]:
    """获取已订阅公共卡组或我的私人卡组的分组树（章/节）"""
    data = await study_service.get_deck_group_tree(db=db, user_id=request.user.id, deck_id=deck_id)
    return response_base.success(data=data)


@router.post('/decks/{deck_id}/groups', summary='创建私人分组', name='memory_create_group')
async def create_personal_group(
    request: Request,
    db: CurrentSessionTransaction,
    deck_id: Annotated[int, Path(description='卡组 ID')],
    obj: CreateGroupParam,
) -> ResponseSchemaModel[GetGroupDetail]:
    """在用户私人卡组下创建分组（章/节）"""
    data = await study_service.create_personal_group(db=db, user_id=request.user.id, deck_id=deck_id, obj=obj)
    return response_base.success(data=data)


@router.put('/groups/{group_id}', summary='更新私人分组', name='memory_update_group')
async def update_personal_group(
    request: Request,
    db: CurrentSessionTransaction,
    group_id: Annotated[int, Path(description='分组 ID')],
    obj: UpdateGroupParam,
) -> ResponseModel:
    """更新用户私人分组（改名/移动/排序/状态）"""
    count = await study_service.update_personal_group(db=db, user_id=request.user.id, group_id=group_id, obj=obj)
    return response_base.success(data={'updated': count})


@router.delete('/groups/{group_id}', summary='删除私人分组', name='memory_delete_group')
async def delete_personal_group(
    request: Request,
    db: CurrentSessionTransaction,
    group_id: Annotated[int, Path(description='分组 ID')],
) -> ResponseModel:
    """删除用户私人分组及其子分组，组内卡片移回根目录"""
    count = await study_service.delete_personal_group(db=db, user_id=request.user.id, group_id=group_id)
    return response_base.success(data={'deleted': count})


# ============ 个人卡片 ============
@router.get('/my/cards', summary='我的私人卡片列表', name='memory_get_my_cards')
async def get_my_cards(
    request: Request,
    db: CurrentSession,
) -> ResponseSchemaModel[list[dict]]:
    """获取用户私人卡组下的全部卡片"""
    data = await study_service.list_my_cards(db=db, user_id=request.user.id)
    return response_base.success(data=data)


@router.post('/cards', summary='创建私人卡片', name='memory_create_card')
async def create_personal_card(
    request: Request,
    db: CurrentSessionTransaction,
    obj: CreateCardParam,
) -> ResponseSchemaModel[GetCardDetail]:
    """在私人卡组下创建卡片"""
    data = await study_service.create_personal_card(db=db, user_id=request.user.id, obj=obj)
    return response_base.success(data=data)


@router.get('/cards/{card_id}', summary='卡片详情', name='memory_get_card_detail')
async def get_card_detail(
    request: Request,
    db: CurrentSession,
    card_id: Annotated[int, Path(description='卡片 ID')],
) -> ResponseSchemaModel[GetCardDetail]:
    """获取卡片详情（含内容）"""
    data = await study_service.load_card_detail(db=db, user_id=request.user.id, card_id=card_id)
    return response_base.success(data=data)


@router.put('/cards/{card_id}', summary='更新私人卡片', name='memory_update_card')
async def update_personal_card(
    request: Request,
    db: CurrentSessionTransaction,
    card_id: Annotated[int, Path(description='卡片 ID')],
    obj: CreateCardParam,
) -> ResponseSchemaModel[GetCardDetail]:
    """更新私人卡片内容（发布新版本）"""
    data = await study_service.update_personal_card(db=db, user_id=request.user.id, card_id=card_id, obj=obj)
    return response_base.success(data=data)


@router.delete('/cards/{card_id}', summary='删除私人卡片', name='memory_delete_card')
async def delete_personal_card(
    request: Request,
    db: CurrentSessionTransaction,
    card_id: Annotated[int, Path(description='卡片 ID')],
) -> ResponseModel:
    """删除私人卡片"""
    await study_service.delete_personal_card(db=db, user_id=request.user.id, card_id=card_id)
    return response_base.success()


# ============ 学习会话 ============
@router.get('/study/queue', summary='获取学习队列', name='memory_get_study_queue')
async def get_study_queue(
    request: Request,
    db: CurrentSession,
    mode: Annotated[str, Query(description='模式: all 全部 / review 仅复习 / learn 仅新卡')] = 'all',
    limit: Annotated[int, Query(ge=1, le=200, description='队列上限')] = 50,
    category_id: Annotated[int | None, Query(gt=0, description='领域分类 ID，按当前领域过滤')] = None,
    deck_id: Annotated[int | None, Query(gt=0, description='限定卡组 ID')] = None,
    group_id: Annotated[int | None, Query(gt=0, description='限定章节/分组 ID（需同时传 deck_id）')] = None,
) -> ResponseSchemaModel[GetStudyQueue]:
    """到期优先，再补新卡；可按卡组/章节范围过滤"""
    data = await study_service.get_queue(
        db=db,
        user_id=request.user.id,
        mode=mode,
        limit=limit,
        category_id=category_id,
        deck_id=deck_id,
        group_id=group_id,
    )
    return response_base.success(data=data)


@router.post('/cards/{card_id}/check', summary='判定作答并揭晓', name='memory_check_card')
async def check_memory_card(
    request: Request,
    db: CurrentSession,
    card_id: Annotated[int, Path(description='卡片 ID')],
    obj: CheckMemoryCardParam,
) -> ResponseSchemaModel[CheckMemoryCardResult]:
    """判定答案、揭晓正确答案并预览四档复习时间，不推进记忆状态"""
    data = await study_service.check(db=db, user_id=request.user.id, card_id=card_id, obj=obj)
    return response_base.success(data=data)


@router.post('/reviews', summary='提交评分并调度', name='memory_submit_review')
async def submit_review(
    request: Request,
    db: CurrentSessionTransaction,
    obj: SubmitMemoryReviewParam,
) -> ResponseSchemaModel[SubmitMemoryReviewResult]:
    """提交四级评分，执行 FSRS 调度并记录复习日志（幂等）"""
    data = await study_service.review(db=db, user_id=request.user.id, obj=obj)
    return response_base.success(data=data)


# ============ 记忆曲线 ============
@router.get('/cards/{card_id}/forecast', summary='单卡复习预测', name='memory_get_card_forecast')
async def get_card_forecast(
    request: Request,
    db: CurrentSession,
    card_id: Annotated[int, Path(description='卡片 ID')],
) -> ResponseSchemaModel[ReviewForecast]:
    """预览各评分对应的下次复习时间"""
    data = await study_service.forecast(db=db, user_id=request.user.id, card_id=card_id)
    return response_base.success(data=data)


@router.get('/cards/{card_id}/curve', summary='单卡记忆曲线', name='memory_get_card_curve')
async def get_card_curve(
    request: Request,
    db: CurrentSession,
    card_id: Annotated[int, Path(description='卡片 ID')],
    days: Annotated[int, Query(ge=7, le=180, description='采样天数')] = 30,
) -> ResponseSchemaModel[GetMemoryCurve]:
    """获取单卡未来回忆概率曲线"""
    data = await study_service.curve(db=db, user_id=request.user.id, card_id=card_id, days=days)
    return response_base.success(data=data)


@router.get('/stats/forecast', summary='到期卡数预测', name='memory_get_stats_forecast')
async def get_stats_forecast(
    request: Request,
    db: CurrentSession,
    days: Annotated[int, Query(ge=7, le=90, description='预测天数')] = 30,
    category_id: Annotated[int | None, Query(gt=0, description='领域分类 ID，按当前领域过滤')] = None,
) -> ResponseSchemaModel[GetMemoryForecast]:
    """获取未来到期卡数预测"""
    data = await study_service.stats_forecast(db=db, user_id=request.user.id, days=days, category_id=category_id)
    return response_base.success(data=data)
