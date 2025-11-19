#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Annotated

from fastapi import APIRouter, Path, Query

from backend.app.bili.crud import bili_template_dao
from backend.app.bili.schema.template import CreateBiliTemplateParam, GetBiliTemplateDetail, UpdateBiliTemplateParam
from backend.app.bili.service import bili_template_service
from backend.common.response.response_schema import ResponseModel, ResponseSchemaModel, response_base
from backend.database.db import CurrentSession, CurrentSessionTransaction

router = APIRouter()


@router.get('', summary='获取 B 站模板列表')
async def get_bili_template_list(
    db: CurrentSession,
    name: Annotated[str | None, Query(description='模板名称')] = None,
    template_type: Annotated[str | None, Query(description='模板类型')] = None,
    status: Annotated[int | None, Query(description='状态')] = None,
    category_id: Annotated[int | None, Query(description='分类 ID')] = None,
) -> ResponseSchemaModel[list[GetBiliTemplateDetail]]:
    """获取 B 站模板列表"""
    data = await bili_template_dao.get_list(db, name=name, template_type=template_type, status=status, category_id=category_id)
    return response_base.success(data=data)


@router.get('/{pk}', summary='获取 B 站模板详情')
async def get_bili_template(
    db: CurrentSession, pk: Annotated[int, Path(description='模板 ID')]
) -> ResponseSchemaModel[GetBiliTemplateDetail]:
    """获取 B 站模板详情"""
    data = await bili_template_service.get(db, pk)
    return response_base.success(data=data)


@router.post('', summary='创建 B 站模板')
async def create_bili_template(db: CurrentSessionTransaction, obj: CreateBiliTemplateParam) -> ResponseModel:
    """创建 B 站模板"""
    await bili_template_service.create(db, obj)
    return response_base.success()


@router.put('/{pk}', summary='更新 B 站模板')
async def update_bili_template(
    db: CurrentSessionTransaction, pk: Annotated[int, Path(description='模板 ID')], obj: UpdateBiliTemplateParam
) -> ResponseModel:
    """更新 B 站模板"""
    count = await bili_template_service.update(db, pk, obj)
    if count > 0:
        return response_base.success()
    return response_base.fail()


@router.delete('/{pk}', summary='删除 B 站模板')
async def delete_bili_template(db: CurrentSessionTransaction, pk: Annotated[int, Path(description='模板 ID')]) -> ResponseModel:
    """删除 B 站模板"""
    count = await bili_template_service.delete(db, pk)
    if count > 0:
        return response_base.success()
    return response_base.fail()
