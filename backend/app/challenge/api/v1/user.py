#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Annotated

from fastapi import APIRouter, Path, Request

from backend.app.challenge.schema.challenge import (
    GetChallengeAttemptResponse,
    GetChallengeMapResponse,
    SubmitChallengeAttemptParam,
    SubmitChallengeAttemptResult,
)
from backend.app.challenge.service.challenge_service import challenge_service
from backend.common.response.response_schema import ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.database.db import CurrentSession, CurrentSessionTransaction

router = APIRouter(dependencies=[DependsJwtAuth])


@router.get('/{challenge_key}/map', summary='获取我的闯关地图')
async def get_my_challenge_map(
    request: Request,
    db: CurrentSession,
    challenge_key: Annotated[str, Path(description='闯关标识')],
) -> ResponseSchemaModel[GetChallengeMapResponse]:
    """
    获取我的闯关地图

    :param request: 请求对象
    :param db: 数据库会话
    :param challenge_key: 闯关标识
    :return:
    """
    data = await challenge_service.get_map(db=db, user_id=request.user.id, challenge_key=challenge_key)
    return response_base.success(data=data)


@router.post('/{challenge_key}/levels/{level_id}/attempts', summary='开始关卡挑战')
async def start_challenge_attempt(
    request: Request,
    db: CurrentSessionTransaction,
    challenge_key: Annotated[str, Path(description='闯关标识')],
    level_id: Annotated[int, Path(description='关卡 ID')],
) -> ResponseSchemaModel[GetChallengeAttemptResponse]:
    """
    开始关卡挑战

    :param request: 请求对象
    :param db: 数据库会话
    :param challenge_key: 闯关标识
    :param level_id: 关卡 ID
    :return:
    """
    data = await challenge_service.start_attempt(
        db=db,
        user_id=request.user.id,
        challenge_key=challenge_key,
        level_id=level_id,
    )
    return response_base.success(data=data)


@router.get('/attempts/{attempt_key}', summary='获取挑战会话')
async def get_challenge_attempt(
    request: Request,
    db: CurrentSession,
    attempt_key: Annotated[str, Path(description='挑战标识')],
) -> ResponseSchemaModel[GetChallengeAttemptResponse]:
    """
    获取挑战会话

    :param request: 请求对象
    :param db: 数据库会话
    :param attempt_key: 挑战标识
    :return:
    """
    data = await challenge_service.get_attempt(db=db, user_id=request.user.id, attempt_key=attempt_key)
    return response_base.success(data=data)


@router.post('/attempts/{attempt_key}/submit', summary='提交关卡挑战')
async def submit_challenge_attempt(
    request: Request,
    db: CurrentSessionTransaction,
    attempt_key: Annotated[str, Path(description='挑战标识')],
    obj: SubmitChallengeAttemptParam,
) -> ResponseSchemaModel[SubmitChallengeAttemptResult]:
    """
    提交关卡挑战

    :param request: 请求对象
    :param db: 数据库会话
    :param attempt_key: 挑战标识
    :param obj: 提交参数
    :return:
    """
    data = await challenge_service.submit_attempt(
        db=db,
        user_id=request.user.id,
        attempt_key=attempt_key,
        obj=obj,
    )
    return response_base.success(data=data)

