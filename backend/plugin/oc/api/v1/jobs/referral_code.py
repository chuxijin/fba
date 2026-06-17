"""内推码 API"""

from typing import Annotated

from fastapi import APIRouter, Query, Request

from backend.common.pagination import DependsPagination, PageData
from backend.common.response.response_schema import ResponseModel, ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.database.db import CurrentSession
from backend.plugin.oc.service.referral_code_service import referral_code_service
from backend.plugin.oc.schema.referral_code import (
    CreateReferralCodeParam,
    UpdateReferralCodeParam,
    GetReferralCodeDetail,
)


router = APIRouter()


@router.get('', summary='获取内推码列表', dependencies=[DependsPagination])
async def get_referral_code_list(
    db: CurrentSession,
    company_name: Annotated[str | None, Query(description='企业名称')] = None,
) -> ResponseSchemaModel[PageData[GetReferralCodeDetail]]:
    """获取内推码分页列表（公开接口）"""
    data = await referral_code_service.get_list(db, company_name)
    return response_base.success(data=data)


@router.get('/{pk}', summary='获取内推码详情')
async def get_referral_code(
    db: CurrentSession,
    pk: int,
) -> ResponseModel:
    """获取内推码详情（公开接口）"""
    data = await referral_code_service.get(db, pk)
    return response_base.success(data=data)


@router.post('', summary='创建内推码', dependencies=[DependsJwtAuth])
async def create_referral_code(
    request: Request,
    db: CurrentSession,
    obj: CreateReferralCodeParam,
) -> ResponseModel:
    """创建内推码（需要登录）"""
    await referral_code_service.create(db, obj, request.user.id)
    return response_base.success()


@router.put('/{pk}', summary='更新内推码', dependencies=[DependsJwtAuth])
async def update_referral_code(
    request: Request,
    db: CurrentSession,
    pk: int,
    obj: UpdateReferralCodeParam,
) -> ResponseModel:
    """更新内推码（需要登录）"""
    await referral_code_service.update(db, pk, obj, request.user.id)
    return response_base.success()


@router.delete('/{pk}', summary='删除内推码', dependencies=[DependsJwtAuth])
async def delete_referral_code(
    db: CurrentSession,
    pk: int,
) -> ResponseModel:
    """删除内推码（需要登录）"""
    await referral_code_service.delete(db, pk)
    return response_base.success()
