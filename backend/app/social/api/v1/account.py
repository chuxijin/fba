#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, Request

from backend.app.social.schema.account import (
    CreateSocialAccountParam,
    UpdateSocialAccountParam,
    GetSocialAccountDetail,
)
from backend.app.social.service.account_service import SocialAccountService
from backend.common.pagination import DependsPagination, PageData, _CustomPageParams, paging_data
from backend.common.response.response_schema import ResponseModel, ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.database.db import CurrentSession

router = APIRouter(prefix='/social/account', tags=['social:account'])

service = SocialAccountService()


@router.get('/{pk}', summary='获取账号详情', dependencies=[DependsJwtAuth])
async def get_social_account(
    pk: Annotated[int, Path(description='账号 ID')],
) -> ResponseSchemaModel[GetSocialAccountDetail]:
    data = await service.get(pk=pk)
    return response_base.success(data=GetSocialAccountDetail.model_validate(data))


@router.get('', summary='分页获取账号列表', dependencies=[DependsJwtAuth, DependsPagination])
async def get_social_account_list(
    db: CurrentSession,
    page_params: Annotated[_CustomPageParams, DependsPagination],
    platform: Annotated[str | None, Query(description='平台')] = None,
    name: Annotated[str | None, Query(description='账号名称')] = None,
    domain: Annotated[str | None, Query(description='领域')] = None,
) -> ResponseModel:
    stmt = await service.get_list(platform=platform, name=name, domain=domain)
    data = await paging_data(db, stmt)
    return response_base.success(data=data)


@router.post('', summary='创建账号', dependencies=[DependsJwtAuth])
async def create_social_account(
    request: Request,
    db: CurrentSession,
    obj: CreateSocialAccountParam,
) -> ResponseSchemaModel[GetSocialAccountDetail]:
    current_user_id = getattr(request.state, 'user_id', None) or 0
    created = await service.create(obj=obj, current_user_id=current_user_id)
    return response_base.success(data=GetSocialAccountDetail.model_validate(created))


@router.put('/{pk}', summary='更新账号', dependencies=[DependsJwtAuth])
async def update_social_account(
    request: Request,
    pk: Annotated[int, Path(description='账号 ID')],
    obj: UpdateSocialAccountParam,
) -> ResponseModel:
    current_user_id = getattr(request.state, 'user_id', None) or 0
    await service.update(pk=pk, obj=obj, current_user_id=current_user_id)
    return response_base.success()


@router.delete('', summary='删除账号', dependencies=[DependsJwtAuth])
async def delete_social_account(
    pks: Annotated[list[int], Query(description='主键 ID 列表')],
) -> ResponseModel:
    await service.delete(pks=pks)
    return response_base.success()


