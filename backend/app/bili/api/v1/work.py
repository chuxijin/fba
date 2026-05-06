#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Annotated

from fastapi import APIRouter, Path, Query
from pydantic import BaseModel, Field

from backend.app.bili.crud import bili_work_dao
from backend.app.bili.schema.work import CreateBiliWorkParam, GetBiliWorkDetail, UpdateBiliWorkParam
from backend.app.bili.service import bili_work_service
from backend.common.response.response_schema import ResponseModel, ResponseSchemaModel, response_base
from backend.database.db import CurrentSession, CurrentSessionTransaction

router = APIRouter()


class GetOrCreateWorkByBVIDParam(BaseModel):
    """根据 BVID 获取或创建作品参数"""

    bvid: str = Field(description='BVID')


@router.post('/get_or_create', summary='根据 BVID 获取或创建作品')
async def get_or_create_work_by_bvid(
    db: CurrentSessionTransaction, param: GetOrCreateWorkByBVIDParam
) -> ResponseSchemaModel[GetBiliWorkDetail]:
    """
    根据 BVID 获取或创建作品

    - 如果作品已存在，直接返回
    - 如果不存在，从 B 站 API 获取信息并创建
    """
    data = await bili_work_service.get_or_create_by_bvid(db, param.bvid)
    return response_base.success(data=data)


@router.get('', summary='获取 B 站作品列表')
async def get_bili_work_list(
    db: CurrentSession,
    work_id: Annotated[str | None, Query(description='作品 ID')] = None,
    title: Annotated[str | None, Query(description='标题')] = None,
    work_type: Annotated[str | None, Query(description='作品类型')] = None,
    mid: Annotated[str | None, Query(description='所属 MID')] = None,
) -> ResponseSchemaModel[list[GetBiliWorkDetail]]:
    """获取 B 站作品列表"""
    data = await bili_work_dao.get_list(db, work_id=work_id, title=title, work_type=work_type, mid=mid)
    return response_base.success(data=data)


@router.get('/{pk}', summary='获取 B 站作品详情')
async def get_bili_work(
    db: CurrentSession, pk: Annotated[int, Path(description='作品 ID')]
) -> ResponseSchemaModel[GetBiliWorkDetail]:
    """获取 B 站作品详情"""
    data = await bili_work_service.get(db, pk)
    return response_base.success(data=data)


@router.post('', summary='创建 B 站作品')
async def create_bili_work(db: CurrentSessionTransaction, obj: CreateBiliWorkParam) -> ResponseModel:
    """创建 B 站作品"""
    await bili_work_service.create(db, obj)
    return response_base.success()


@router.put('/{pk}', summary='更新 B 站作品')
async def update_bili_work(
    db: CurrentSessionTransaction, pk: Annotated[int, Path(description='作品 ID')], obj: UpdateBiliWorkParam
) -> ResponseModel:
    """更新 B 站作品"""
    count = await bili_work_service.update(db, pk, obj)
    if count > 0:
        return response_base.success()
    return response_base.fail()


@router.delete('/{pk}', summary='删除 B 站作品')
async def delete_bili_work(db: CurrentSessionTransaction, pk: Annotated[int, Path(description='作品 ID')]) -> ResponseModel:
    """删除 B 站作品"""
    count = await bili_work_service.delete(db, pk)
    if count > 0:
        return response_base.success()
    return response_base.fail()
