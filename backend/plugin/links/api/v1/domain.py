#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Annotated

from fastapi import APIRouter, Query, Request

from backend.common.pagination import DependsPagination, PageData, paging_data
from backend.common.response.response_schema import ResponseModel, ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.database.db import CurrentSession, CurrentSessionTransaction
from backend.plugin.links.schema import CreateDomainParam, GetDomainDetail, UpdateDomainParam
from backend.plugin.links.service import domain_service

router = APIRouter()


@router.get('', summary='获取域名列表', dependencies=[DependsJwtAuth, DependsPagination])
async def get_domain_list(
    db: CurrentSession,
    domain: Annotated[str | None, Query(description='域名模糊搜索')] = None,
    domain_type: Annotated[int | None, Query(ge=1, le=3, description='域名类型(1入口 2中转 3落地)')] = None,
) -> ResponseSchemaModel[PageData[GetDomainDetail]]:
    select = domain_service.get_select(domain=domain, domain_type=domain_type)
    page_data = await paging_data(db, select)
    return response_base.success(data=page_data)


@router.get('/type/{domain_type}', summary='获取指定类型域名', dependencies=[DependsJwtAuth])
async def get_domains_by_type(
    db: CurrentSession,
    domain_type: int,
) -> ResponseSchemaModel[list[GetDomainDetail]]:
    domains = await domain_service.get_by_type(db=db, domain_type=domain_type)
    return response_base.success(data=[GetDomainDetail.model_validate(d) for d in domains])


@router.get('/{pk}', summary='获取域名详情', dependencies=[DependsJwtAuth])
async def get_domain_detail(db: CurrentSession, pk: int) -> ResponseSchemaModel[GetDomainDetail]:
    domain = await domain_service.get(db=db, pk=pk)
    return response_base.success(data=GetDomainDetail.model_validate(domain))


@router.post('', summary='创建域名', dependencies=[DependsJwtAuth])
async def create_domain(
    db: CurrentSessionTransaction,
    request: Request,
    obj: CreateDomainParam,
) -> ResponseSchemaModel[GetDomainDetail]:
    domain = await domain_service.create(db=db, obj=obj, created_by=request.user.id)
    return response_base.success(data=GetDomainDetail.model_validate(domain))


@router.put('/{pk}', summary='更新域名', dependencies=[DependsJwtAuth])
async def update_domain(db: CurrentSessionTransaction, pk: int, obj: UpdateDomainParam) -> ResponseModel:
    await domain_service.update(db=db, pk=pk, obj=obj)
    return response_base.success()


@router.delete('/{pk}', summary='删除域名', dependencies=[DependsJwtAuth])
async def delete_domain(db: CurrentSessionTransaction, pk: int) -> ResponseModel:
    await domain_service.delete(db=db, pk=pk)
    return response_base.success()
