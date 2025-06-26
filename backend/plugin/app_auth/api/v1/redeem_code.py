#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query

from backend.common.pagination import DependsPagination, PageData, paging_data
from backend.common.response.response_schema import ResponseModel, ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.common.security.rbac import DependsRBAC
from backend.database.db import CurrentSession
from backend.plugin.app_auth.schema.redeem_code import (
    BatchCreateRedeemCodeParam,
    GetRedeemCodeDetail,
    UseRedeemCodeParam,
)
from backend.plugin.app_auth.service.redeem_code_service import redeem_code_service

router = APIRouter()


@router.post('/batch', summary='批量生成兑换码', dependencies=[DependsRBAC])
async def batch_create_redeem_codes(obj: BatchCreateRedeemCodeParam) -> ResponseSchemaModel[list[GetRedeemCodeDetail]]:
    """
    批量生成兑换码
    
    :param obj: 批量生成参数
    :return:
    """
    data = await redeem_code_service.batch_create(obj=obj)
    return response_base.success(data=data)


@router.post('/use', summary='使用兑换码', dependencies=[DependsJwtAuth])
async def use_redeem_code(obj: UseRedeemCodeParam) -> ResponseModel:
    """
    使用兑换码
    
    :param obj: 使用兑换码参数
    :return:
    """
    await redeem_code_service.use_code(obj=obj)
    return response_base.success()


@router.get('', summary='分页获取兑换码列表', dependencies=[DependsJwtAuth, DependsPagination])
async def get_pagination_redeem_codes(
    db: CurrentSession,
    application_id: Annotated[int | None, Query(description='应用ID')] = None,
    batch_no: Annotated[str | None, Query(description='批次号')] = None,
    is_used: Annotated[bool | None, Query(description='是否已使用')] = None,
) -> ResponseModel:
    """
    分页获取兑换码列表
    
    :param db: 数据库会话
    :param application_id: 应用ID
    :param batch_no: 批次号
    :param is_used: 是否已使用
    :return:
    """
    select = redeem_code_service.get_select(application_id=application_id, batch_no=batch_no, is_used=is_used)
    page_data = await paging_data(db, select)
    return response_base.success(data=page_data)


@router.get('/{pk}', summary='获取兑换码详情', dependencies=[DependsJwtAuth])
async def get_redeem_code(pk: Annotated[int, Path(description='兑换码ID')]) -> ResponseSchemaModel[GetRedeemCodeDetail]:
    """
    获取兑换码详情
    
    :param pk: 兑换码ID
    :return:
    """
    data = await redeem_code_service.get(pk=pk)
    return response_base.success(data=data)


@router.delete('/{pk}', summary='删除兑换码', dependencies=[DependsRBAC])
async def delete_redeem_code(pk: Annotated[int, Path(description='兑换码ID')]) -> ResponseModel:
    """
    删除兑换码
    
    :param pk: 兑换码ID
    :return:
    """
    count = await redeem_code_service.delete(pk=pk)
    if count > 0:
        return response_base.success()
    return response_base.fail()