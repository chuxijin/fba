#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Annotated

from fastapi import APIRouter, Path, Query

from backend.app.health.schema.nutrition_fact import (
    CreateNutritionFactParam,
    GetNutritionFactDetail,
    UpdateNutritionFactParam,
)
from backend.app.health.service.nutrition_fact_service import nutrition_fact_service
from backend.common.response.response_schema import ResponseModel, ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.database.db import CurrentSession, CurrentSessionTransaction

router = APIRouter()


@router.get('/{pk}', summary='获取营养成分详情', dependencies=[DependsJwtAuth])
async def get_nutrition_fact(
    db: CurrentSession, pk: Annotated[int, Path(description='营养成分 ID')]
) -> ResponseSchemaModel[GetNutritionFactDetail]:
    """获取营养成分详情"""
    data = await nutrition_fact_service.get(db=db, pk=pk)
    return response_base.success(data=data)


@router.get('/food/{food_id}', summary='通过食物 ID 获取营养成分', dependencies=[DependsJwtAuth])
async def get_nutrition_fact_by_food(
    db: CurrentSession, food_id: Annotated[int, Path(description='食物 ID')]
) -> ResponseSchemaModel[GetNutritionFactDetail]:
    """通过食物 ID 获取营养成分"""
    data = await nutrition_fact_service.get_by_food_id(db=db, food_id=food_id)
    return response_base.success(data=data)


@router.post('', summary='创建营养成分', dependencies=[DependsJwtAuth])
async def create_nutrition_fact(db: CurrentSessionTransaction, obj: CreateNutritionFactParam) -> ResponseModel:
    """创建营养成分"""
    await nutrition_fact_service.create(db=db, obj=obj)
    return response_base.success()


@router.put('/{pk}', summary='更新营养成分', dependencies=[DependsJwtAuth])
async def update_nutrition_fact(
    db: CurrentSessionTransaction, pk: Annotated[int, Path(description='营养成分 ID')], obj: UpdateNutritionFactParam
) -> ResponseModel:
    """更新营养成分"""
    count = await nutrition_fact_service.update(db=db, pk=pk, obj=obj)
    if count > 0:
        return response_base.success()
    return response_base.fail()


@router.delete('/{pk}', summary='删除营养成分', dependencies=[DependsJwtAuth])
async def delete_nutrition_fact(
    db: CurrentSessionTransaction, pk: Annotated[int, Path(description='营养成分 ID')]
) -> ResponseModel:
    """删除营养成分"""
    count = await nutrition_fact_service.delete(db=db, pk=pk)
    if count > 0:
        return response_base.success()
    return response_base.fail()
