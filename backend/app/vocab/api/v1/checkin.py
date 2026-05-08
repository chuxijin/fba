#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Annotated

from fastapi import APIRouter, Query, Request

from backend.app.vocab.schema.checkin import GetCheckinToday, GetStreakInfo
from backend.app.vocab.service.checkin_service import checkin_service
from backend.app.vocab.crud.crud_checkin import checkin_dao
from backend.common.pagination import DependsPagination, paging_data
from backend.common.response.response_schema import ResponseModel, ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.database.db import CurrentSession

router = APIRouter(prefix='/vocab/checkin', tags=['单词打卡'], dependencies=[DependsJwtAuth])


@router.get('/today', summary='今日打卡状态')
async def get_today_status(request: Request, db: CurrentSession) -> ResponseSchemaModel[GetCheckinToday]:
    """获取今日打卡状态"""
    data = await checkin_service.get_today_status(db=db, user_id=request.user.id)
    return response_base.success(data=data)


@router.get('/streak', summary='连续打卡信息')
async def get_streak_info(request: Request, db: CurrentSession) -> ResponseSchemaModel[GetStreakInfo]:
    """获取连续打卡天数"""
    data = await checkin_service.get_streak_info(db=db, user_id=request.user.id)
    return response_base.success(data=data)


@router.get('/history', summary='打卡历史', dependencies=[DependsPagination])
async def get_checkin_history(
    request: Request,
    db: CurrentSession,
    year: Annotated[int | None, Query(description='年份')] = None,
    month: Annotated[int | None, Query(description='月份')] = None,
) -> ResponseModel:
    """获取打卡历史"""
    stmt = await checkin_dao.get_select_by_user(request.user.id, year=year, month=month)
    data = await paging_data(db, stmt)
    return response_base.success(data=data)
