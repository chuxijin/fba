#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Annotated

from fastapi import APIRouter, Path, Query, Request

from backend.app.quest.schema.quest import (
    CreateQuestParam,
    GetQuestDetail,
    ReviewClaimParam,
    ReviewClaimResult,
    RevokeClaimParam,
    RevokeClaimResult,
    UpdateQuestParam,
)
from backend.app.quest.service.claim_service import claim_service
from backend.app.quest.service.quest_service import quest_service
from backend.app.quest.service.review_service import review_service
from backend.app.quest.service.reward_service import reward_service
from backend.common.pagination import DependsPagination
from backend.common.response.response_schema import ResponseModel, ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.database.db import CurrentSession

router = APIRouter(prefix='/quest/admin', tags=['悬赏任务-管理端'])


@router.post('/quests', summary='创建任务', dependencies=[DependsJwtAuth])
async def create_quest(
    request: Request,
    db: CurrentSession,
    obj: CreateQuestParam,
) -> ResponseSchemaModel[GetQuestDetail]:
    """创建任务"""
    data = await quest_service.create_quest(db=db, user_id=request.user.id, obj=obj)
    return response_base.success(data=data)


@router.put('/quests/{pk}', summary='更新任务', dependencies=[DependsJwtAuth])
async def update_quest(
    db: CurrentSession,
    pk: Annotated[int, Path(description='任务 ID')],
    obj: UpdateQuestParam,
) -> ResponseModel:
    """更新任务"""
    count = await quest_service.update_quest(db=db, pk=pk, obj=obj)
    return response_base.success(data={'updated': count})


@router.delete('/quests/{pk}', summary='删除任务', dependencies=[DependsJwtAuth])
async def delete_quest(
    db: CurrentSession,
    pk: Annotated[int, Path(description='任务 ID')],
) -> ResponseModel:
    """删除任务"""
    count = await quest_service.delete_quest(db=db, pk=pk)
    return response_base.success(data={'deleted': count})


@router.get(
    '/quests',
    summary='管理端获取任务列表',
    dependencies=[DependsJwtAuth, DependsPagination],
)
async def get_quest_list_for_admin(
    db: CurrentSession,
    status: Annotated[int | None, Query(description='状态过滤')] = None,
    keyword: Annotated[str | None, Query(description='搜索关键词')] = None,
) -> ResponseModel:
    """管理端获取任务列表"""
    data = await quest_service.get_quest_list(db=db, status=status, keyword=keyword)
    return response_base.success(data=data)


@router.get(
    '/claims',
    summary='管理端获取领取列表',
    dependencies=[DependsJwtAuth, DependsPagination],
)
async def get_claim_list_for_admin(
    db: CurrentSession,
    quest_id: Annotated[int | None, Query(description='任务 ID')] = None,
    user_id: Annotated[int | None, Query(description='用户 ID')] = None,
    claim_status: Annotated[int | None, Query(description='领取状态')] = None,
) -> ResponseModel:
    """管理端获取领取列表"""
    data = await claim_service.get_claims_for_admin(
        db=db, quest_id=quest_id, user_id=user_id, claim_status=claim_status
    )
    return response_base.success(data=data)


@router.post('/claims/{pk}/review', summary='审核领取记录', dependencies=[DependsJwtAuth])
async def review_claim(
    request: Request,
    db: CurrentSession,
    pk: Annotated[int, Path(description='领取记录 ID')],
    obj: ReviewClaimParam,
) -> ResponseSchemaModel[ReviewClaimResult]:
    """审核领取记录"""
    data = await review_service.review(
        db=db, claim_id=pk, reviewer_id=request.user.id, obj=obj
    )
    return response_base.success(data=data)


@router.post('/claims/{pk}/retry-grant', summary='重试发放奖励', dependencies=[DependsJwtAuth])
async def retry_grant(
    db: CurrentSession,
    pk: Annotated[int, Path(description='领取记录 ID')],
) -> ResponseModel:
    """重试发放奖励"""
    success = await reward_service.retry_grant(db=db, claim_id=pk)
    return response_base.success(data={'success': success})


@router.post('/claims/{pk}/revoke', summary='撤销已审核记录(硬撤销)', dependencies=[DependsJwtAuth])
async def revoke_claim(
    request: Request,
    db: CurrentSession,
    pk: Annotated[int, Path(description='领取记录 ID')],
    obj: RevokeClaimParam,
) -> ResponseSchemaModel[RevokeClaimResult]:
    """撤销已审核记录, 同时回收已发放的奖励"""
    data = await review_service.revoke(
        db=db, claim_id=pk, reviewer_id=request.user.id, obj=obj
    )
    return response_base.success(data=data)
