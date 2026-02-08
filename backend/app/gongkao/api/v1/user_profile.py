#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from fastapi import APIRouter, Request

from backend.app.gongkao.schema.user_profile import (
    CreateUserProfileParam,
    GetUserProfileDetail,
    UpdateUserProfileParam,
)
from backend.app.gongkao.service.user_profile_service import user_profile_service
from backend.common.response.response_schema import ResponseModel, ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.database.db import CurrentSession, CurrentSessionTransaction

router = APIRouter()


@router.get(
    '/me',
    summary='获取当前用户画像',
    dependencies=[DependsJwtAuth],
)
async def get_my_profile(
    request: Request,
    db: CurrentSession,
) -> ResponseSchemaModel[GetUserProfileDetail | None]:
    """获取当前登录用户的画像"""
    data = await user_profile_service.get_by_user_id(db=db, user_id=request.user.id)
    return response_base.success(data=data)


@router.post(
    '/me',
    summary='创建当前用户画像',
    dependencies=[DependsJwtAuth],
)
async def create_my_profile(
    request: Request,
    db: CurrentSessionTransaction,
    obj: CreateUserProfileParam,
) -> ResponseSchemaModel[GetUserProfileDetail]:
    """创建当前登录用户的画像"""
    data = await user_profile_service.create(db=db, user_id=request.user.id, obj=obj)
    return response_base.success(data=data)


@router.put(
    '/me',
    summary='更新当前用户画像',
    dependencies=[DependsJwtAuth],
)
async def update_my_profile(
    request: Request,
    db: CurrentSessionTransaction,
    obj: UpdateUserProfileParam,
) -> ResponseModel:
    """更新当前登录用户的画像"""
    count = await user_profile_service.update(db=db, user_id=request.user.id, obj=obj)
    if count >= 0:
        return response_base.success()
    return response_base.fail()


@router.post(
    '/me/save',
    summary='保存当前用户画像',
    dependencies=[DependsJwtAuth],
)
async def save_my_profile(
    request: Request,
    db: CurrentSessionTransaction,
    obj: CreateUserProfileParam,
) -> ResponseSchemaModel[GetUserProfileDetail]:
    """保存当前登录用户的画像（存在则更新，不存在则创建）"""
    data = await user_profile_service.save(db=db, user_id=request.user.id, obj=obj)
    return response_base.success(data=data)


@router.delete(
    '/me',
    summary='删除当前用户画像',
    dependencies=[DependsJwtAuth],
)
async def delete_my_profile(
    request: Request,
    db: CurrentSessionTransaction,
) -> ResponseModel:
    """删除当前登录用户的画像"""
    count = await user_profile_service.delete(db=db, user_id=request.user.id)
    if count > 0:
        return response_base.success()
    return response_base.fail()
