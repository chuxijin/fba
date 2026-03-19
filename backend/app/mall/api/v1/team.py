#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Annotated

from fastapi import APIRouter, Path, Query, Request

from backend.app.mall.schema.group_buy_team import (
    CreateGroupBuyTeamParam,
    GetGroupBuyMemberItem,
    GetGroupBuyTeamDetail,
    GetGroupBuyTeamListItem,
    GroupBuyTeamProgress,
    JoinGroupBuyTeamParam,
)
from backend.app.mall.service.team_service import team_service
from backend.common.response.response_schema import ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.database.db import CurrentSession, CurrentSessionTransaction

router = APIRouter(prefix='/team', tags=['拼团团队'])


# ===== 拼团团队 =====
@router.post('', summary='发起拼团', dependencies=[DependsJwtAuth])
async def create_team(
    request: Request,
    db: CurrentSessionTransaction,
    obj: CreateGroupBuyTeamParam,
) -> ResponseSchemaModel[GetGroupBuyTeamDetail]:
    """发起拼团"""
    team = await team_service.create_team(db=db, obj=obj, user_id=request.user.id)
    team_with_members = await team_service.get_team(db=db, team_id=team.id, with_members=True)
    return response_base.success(data=GetGroupBuyTeamDetail.model_validate(team_with_members))


@router.post('/join', summary='参与拼团', dependencies=[DependsJwtAuth])
async def join_team(
    request: Request,
    db: CurrentSessionTransaction,
    obj: JoinGroupBuyTeamParam,
) -> ResponseSchemaModel[GetGroupBuyMemberItem]:
    """参与拼团"""
    member = await team_service.join_team(db=db, obj=obj, user_id=request.user.id)
    return response_base.success(data=GetGroupBuyMemberItem.model_validate(member))


@router.get('/list', summary='获取拼团团队列表')
async def get_team_list(
    db: CurrentSession,
    activity_id: Annotated[int, Query(description='活动 ID')],
    status: Annotated[str | None, Query(description='团队状态')] = None,
) -> ResponseSchemaModel[list[GetGroupBuyTeamListItem]]:
    """获取拼团团队列表"""
    teams = await team_service.get_team_list(db=db, activity_id=activity_id, status=status)
    data = [GetGroupBuyTeamListItem.model_validate(team) for team in teams]
    return response_base.success(data=data)


@router.get('/pending', summary='获取进行中的团队列表')
async def get_pending_teams(
    db: CurrentSession,
    activity_id: Annotated[int, Query(description='活动 ID')],
) -> ResponseSchemaModel[list[GetGroupBuyTeamListItem]]:
    """获取进行中的团队列表（可参与）"""
    teams = await team_service.get_pending_teams(db=db, activity_id=activity_id)
    data = [GetGroupBuyTeamListItem.model_validate(team) for team in teams]
    return response_base.success(data=data)


@router.get('/my', summary='获取我的拼团列表', dependencies=[DependsJwtAuth])
async def get_my_teams(
    request: Request,
    db: CurrentSession,
) -> ResponseSchemaModel[list[GetGroupBuyTeamListItem]]:
    """获取我的拼团列表"""
    teams = await team_service.get_user_teams(db=db, user_id=request.user.id)
    data = [GetGroupBuyTeamListItem.model_validate(team) for team in teams]
    return response_base.success(data=data)


@router.get('/{team_id}', summary='获取拼团团队详情')
async def get_team_detail(
    db: CurrentSession,
    team_id: Annotated[int, Path(description='团队 ID')],
) -> ResponseSchemaModel[GetGroupBuyTeamDetail]:
    """获取拼团团队详情"""
    team = await team_service.get_team(db=db, team_id=team_id, with_members=True)
    return response_base.success(data=GetGroupBuyTeamDetail.model_validate(team))


@router.get('/{team_id}/progress', summary='获取拼团进度')
async def get_team_progress(
    db: CurrentSession,
    team_id: Annotated[int, Path(description='团队 ID')],
) -> ResponseSchemaModel[GroupBuyTeamProgress]:
    """获取拼团进度"""
    progress = await team_service.get_team_progress(db=db, team_id=team_id)
    return response_base.success(data=progress)


@router.delete('/{team_id}', summary='取消拼团', dependencies=[DependsJwtAuth])
async def cancel_team(
    request: Request,
    db: CurrentSession,
    team_id: Annotated[int, Path(description='团队 ID')],
) -> ResponseSchemaModel[int]:
    """取消拼团（仅团长可操作）"""
    count = await team_service.cancel_team(db=db, team_id=team_id, user_id=request.user.id)
    return response_base.success(data=count)
