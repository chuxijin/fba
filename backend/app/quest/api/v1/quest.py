#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Annotated

from fastapi import APIRouter, Path, Query, Request

from backend.app.quest.schema.quest import GetClaimDetail, GetQuestWithUserDetail, SubmitClaimParam
from backend.app.quest.service.claim_service import claim_service
from backend.app.quest.service.quest_service import quest_service
from backend.common.pagination import DependsPagination
from backend.common.response.response_schema import ResponseModel, ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.database.db import CurrentSession, CurrentSessionTransaction

router = APIRouter(prefix='/quest', tags=['悬赏任务'])


@router.get('/quests', summary='获取任务列表', dependencies=[DependsPagination])
async def get_quest_list(
    db: CurrentSession,
    status: Annotated[int | None, Query(description='状态过滤')] = None,
    keyword: Annotated[str | None, Query(description='搜索关键词')] = None,
    only_active: Annotated[bool, Query(description='只看进行中')] = False,
) -> ResponseModel:
    """获取任务列表"""
    data = await quest_service.get_quest_list(
        db=db, status=status, keyword=keyword, only_active=only_active
    )
    return response_base.success(data=data)


@router.get('/quests/{pk}', summary='获取任务详情')
async def get_quest_detail(
    request: Request,
    db: CurrentSession,
    pk: Annotated[int, Path(description='任务 ID')],
) -> ResponseSchemaModel[GetQuestWithUserDetail]:
    """获取任务详情(含当前用户参与状态)"""
    user_id = getattr(request.user, 'id', None) if hasattr(request, 'user') else None
    data = await quest_service.get_quest_detail_with_user(db=db, pk=pk, user_id=user_id)
    return response_base.success(data=data)


@router.post('/quests/{pk}/claim', summary='领取任务', dependencies=[DependsJwtAuth])
async def claim_quest(
    request: Request,
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='任务 ID')],
) -> ResponseSchemaModel[GetClaimDetail]:
    """领取任务"""
    data = await claim_service.claim_quest(db=db, quest_id=pk, user_id=request.user.id)
    return response_base.success(data=data)


@router.post('/claims/{pk}/submit', summary='提交任务内容', dependencies=[DependsJwtAuth])
async def submit_claim(
    request: Request,
    db: CurrentSession,
    pk: Annotated[int, Path(description='领取记录 ID')],
    obj: SubmitClaimParam,
) -> ResponseSchemaModel[GetClaimDetail]:
    """提交任务内容"""
    data = await claim_service.submit_claim(db=db, claim_id=pk, user_id=request.user.id, obj=obj)
    return response_base.success(data=data)


@router.post('/claims/{pk}/abandon', summary='放弃领取', dependencies=[DependsJwtAuth])
async def abandon_claim(
    request: Request,
    db: CurrentSession,
    pk: Annotated[int, Path(description='领取记录 ID')],
) -> ResponseModel:
    """放弃领取"""
    count = await claim_service.abandon_claim(db=db, claim_id=pk, user_id=request.user.id)
    return response_base.success(data={'updated': count})


@router.get('/claims/mine', summary='获取我的领取列表', dependencies=[DependsJwtAuth, DependsPagination])
async def get_my_claims(
    request: Request,
    db: CurrentSession,
    claim_status: Annotated[int | None, Query(description='状态过滤')] = None,
) -> ResponseModel:
    """获取我的领取列表"""
    data = await claim_service.get_my_claims(
        db=db, user_id=request.user.id, claim_status=claim_status
    )
    return response_base.success(data=data)
