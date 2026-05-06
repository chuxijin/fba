#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Annotated

from fastapi import APIRouter, Path, Query, Request

from backend.app.social.schema.work import (
    CreateSocialWorkParam,
    GetSocialWorkDetail,
    UpdateSocialWorkParam,
)
from backend.app.social.service.work_service import SocialWorkService
from backend.common.pagination import DependsPagination, _CustomPageParams, paging_data
from backend.common.response.response_schema import ResponseModel, ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.database.db import CurrentSession

router = APIRouter(prefix='/social/work', tags=['social:work'])

service = SocialWorkService()


@router.get('/{pk}', summary='获取作品详情', dependencies=[DependsJwtAuth])
async def get_social_work(
    pk: Annotated[int, Path(description='作品 ID')],
) -> ResponseSchemaModel[GetSocialWorkDetail]:
    data = await service.get(pk=pk)
    return response_base.success(data=GetSocialWorkDetail.model_validate(data))


@router.get('', summary='分页获取作品列表', dependencies=[DependsJwtAuth, DependsPagination])
async def get_social_work_list(
    db: CurrentSession,
    page_params: Annotated[_CustomPageParams, DependsPagination],
    account_id: Annotated[int | None, Query(description='账号ID')] = None,
    external_id: Annotated[str | None, Query(description='平台作品ID')] = None,
) -> ResponseModel:
    stmt = await service.get_list(account_id=account_id, external_id=external_id)
    data = await paging_data(db, stmt)
    return response_base.success(data=data)


@router.post('', summary='创建作品', dependencies=[DependsJwtAuth])
async def create_social_work(
    request: Request,
    db: CurrentSession,
    obj: CreateSocialWorkParam,
) -> ResponseSchemaModel[GetSocialWorkDetail]:
    # 从请求上下文或权限中提取当前用户 ID；示例中简单处理
    current_user_id = getattr(request.state, 'user_id', None) or 0
    created = await service.create(obj=obj, current_user_id=current_user_id)
    return response_base.success(data=GetSocialWorkDetail.model_validate(created))


@router.put('/{pk}', summary='更新作品', dependencies=[DependsJwtAuth])
async def update_social_work(
    pk: Annotated[int, Path(description='作品 ID')],
    obj: UpdateSocialWorkParam,
) -> ResponseModel:
    await service.update(pk=pk, obj=obj, current_user_id=0)
    return response_base.success()


@router.delete('', summary='删除作品', dependencies=[DependsJwtAuth])
async def delete_social_work(
    pks: Annotated[list[int], Query(description='主键 ID 列表')],
) -> ResponseModel:
    await service.delete(pks=pks)
    return response_base.success()

