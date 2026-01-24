#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, Request

from backend.app.gongkao.schema.zhenti import (
    CreateMaterialParam,
    CreateQuestionAnswerParam,
    CreateQuestionOptionParam,
    CreateQuestionParam,
    DeleteMaterialParam,
    DeleteQuestionAnswerParam,
    DeleteQuestionOptionParam,
    DeleteQuestionParam,
    GetMaterialDetail,
    GetQuestionAnswerDetail,
    GetQuestionDetail,
    GetQuestionOptionDetail,
    MaterialParam,
    QuestionParam,
    UpdateMaterialParam,
    UpdateQuestionAnswerParam,
    UpdateQuestionOptionParam,
    UpdateQuestionParam,
)
from backend.app.gongkao.service.zhenti_service import (
    material_service,
    question_answer_service,
    question_option_service,
    question_service,
)
from backend.common.pagination import DependsPagination, PageData
from backend.common.response.response_schema import ResponseModel, ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.common.security.permission import RequestPermission
from backend.common.security.rbac import DependsRBAC
from backend.database.db import CurrentSession, CurrentSessionTransaction

router = APIRouter()


# ==================== 题目接口 ====================
@router.get('/question/{pk}', summary='获取题目详情')
async def get_gongkao_question(
    db: CurrentSession,
    pk: Annotated[int, Path(description='题目 ID')],
) -> ResponseSchemaModel[GetQuestionDetail]:
    """获取题目详情"""
    data = await question_service.get(db=db, pk=pk)
    return response_base.success(data=data)


@router.get('/question/source/hot', summary='获取热门题目来源')
async def get_hot_sources(
    db: CurrentSession,
    limit: Annotated[int, Query(description='数量', le=50)] = 10,
) -> ResponseSchemaModel[list[str]]:
    """获取热门题目来源"""
    data = await question_service.get_hot_sources(db=db, limit=limit)
    return response_base.success(data=data)


@router.get(
    '/question',
    summary='获取题目列表',
    dependencies=[DependsPagination],
)
async def get_gongkao_question_list(
    db: CurrentSession,
    title: Annotated[str | None, Query(description='题目题干')] = None,
    question_type: Annotated[str | None, Query(description='题型', alias='type')] = None,
    category_id: Annotated[int | None, Query(description='关联分类 ID')] = None,
    material_id: Annotated[int | None, Query(description='关联材料 ID')] = None,
    year: Annotated[int | None, Query(description='年份')] = None,
    source: Annotated[str | None, Query(description='来源')] = None,
    status: Annotated[bool | None, Query(description='状态')] = None,
) -> ResponseSchemaModel[PageData[GetQuestionDetail]]:
    """获取题目列表"""
    params = QuestionParam(
        title=title,
        type=question_type,
        category_id=category_id,
        material_id=material_id,
        year=year,
        source=source,
        status=status,
    )
    data = await question_service.get_list(db=db, params=params)
    return response_base.success(data=data)


@router.post(
    '/question',
    summary='创建题目',
    dependencies=[
        Depends(RequestPermission('gongkao:question:create')),
        DependsRBAC,
    ],
)
async def create_gongkao_question(
    request: Request,
    db: CurrentSessionTransaction,
    obj: CreateQuestionParam,
) -> ResponseModel:
    """创建题目"""
    await question_service.create(db=db, obj=obj, created_by=request.user.id)
    return response_base.success()


@router.put(
    '/question/{pk}',
    summary='更新题目',
    dependencies=[
        Depends(RequestPermission('gongkao:question:update')),
        DependsRBAC,
    ],
)
async def update_gongkao_question(
    request: Request,
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='题目 ID')],
    obj: UpdateQuestionParam,
) -> ResponseModel:
    """更新题目"""
    count = await question_service.update(db=db, pk=pk, obj=obj, updated_by=request.user.id)
    if count > 0:
        return response_base.success()
    return response_base.fail()


@router.delete(
    '/question',
    summary='删除题目',
    dependencies=[
        Depends(RequestPermission('gongkao:question:delete')),
        DependsRBAC,
    ],
)
async def delete_gongkao_question(db: CurrentSessionTransaction, obj: DeleteQuestionParam) -> ResponseModel:
    """删除题目"""
    count = await question_service.delete(db=db, obj=obj)
    if count > 0:
        return response_base.success()
    return response_base.fail()


# ==================== 题目选项接口 ====================
@router.get('/option/{pk}', summary='获取选项详情')
async def get_gongkao_question_option(
    db: CurrentSession,
    pk: Annotated[int, Path(description='选项 ID')],
) -> ResponseSchemaModel[GetQuestionOptionDetail]:
    """获取选项详情"""
    data = await question_option_service.get(db=db, pk=pk)
    return response_base.success(data=data)


@router.get('/option/question/{question_id}', summary='获取题目的所有选项')
async def get_gongkao_question_options_by_question(
    db: CurrentSession,
    question_id: Annotated[int, Path(description='题目 ID')],
) -> ResponseSchemaModel[list[GetQuestionOptionDetail]]:
    """获取题目的所有选项"""
    data = await question_option_service.get_by_question(db=db, question_id=question_id)
    return response_base.success(data=[GetQuestionOptionDetail.model_validate(item) for item in data])


@router.post(
    '/option',
    summary='创建选项',
    dependencies=[
        Depends(RequestPermission('gongkao:question:create')),
        DependsRBAC,
    ],
)
async def create_gongkao_question_option(
    db: CurrentSessionTransaction,
    obj: CreateQuestionOptionParam,
) -> ResponseModel:
    """创建选项"""
    await question_option_service.create(db=db, obj=obj)
    return response_base.success()


@router.put(
    '/option/{pk}',
    summary='更新选项',
    dependencies=[
        Depends(RequestPermission('gongkao:question:update')),
        DependsRBAC,
    ],
)
async def update_gongkao_question_option(
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='选项 ID')],
    obj: UpdateQuestionOptionParam,
) -> ResponseModel:
    """更新选项"""
    count = await question_option_service.update(db=db, pk=pk, obj=obj)
    if count > 0:
        return response_base.success()
    return response_base.fail()


@router.delete(
    '/option',
    summary='删除选项',
    dependencies=[
        Depends(RequestPermission('gongkao:question:delete')),
        DependsRBAC,
    ],
)
async def delete_gongkao_question_option(db: CurrentSessionTransaction, obj: DeleteQuestionOptionParam) -> ResponseModel:
    """删除选项"""
    count = await question_option_service.delete(db=db, obj=obj)
    if count > 0:
        return response_base.success()
    return response_base.fail()


# ==================== 题目答案接口 ====================
@router.get('/answer/{pk}', summary='获取答案详情')
async def get_gongkao_question_answer(
    db: CurrentSession,
    pk: Annotated[int, Path(description='答案 ID')],
) -> ResponseSchemaModel[GetQuestionAnswerDetail]:
    """获取答案详情"""
    data = await question_answer_service.get(db=db, pk=pk)
    return response_base.success(data=data)


@router.get('/answer/question/{question_id}', summary='获取题目的所有答案')
async def get_gongkao_question_answers_by_question(
    db: CurrentSession,
    question_id: Annotated[int, Path(description='题目 ID')],
) -> ResponseSchemaModel[list[GetQuestionAnswerDetail]]:
    """获取题目的所有答案"""
    data = await question_answer_service.get_by_question(db=db, question_id=question_id)
    return response_base.success(data=[GetQuestionAnswerDetail.model_validate(item) for item in data])


@router.get('/answer/question/{question_id}/official', summary='获取题目的官方答案')
async def get_gongkao_question_official_answer(
    db: CurrentSession,
    question_id: Annotated[int, Path(description='题目 ID')],
) -> ResponseSchemaModel[GetQuestionAnswerDetail | None]:
    """获取题目的官方答案"""
    data = await question_answer_service.get_official_answer(db=db, question_id=question_id)
    return response_base.success(data=GetQuestionAnswerDetail.model_validate(data) if data else None)


@router.post(
    '/answer',
    summary='创建答案',
    dependencies=[
        Depends(RequestPermission('gongkao:question:create')),
        DependsRBAC,
    ],
)
async def create_gongkao_question_answer(
    db: CurrentSessionTransaction,
    obj: CreateQuestionAnswerParam,
) -> ResponseModel:
    """创建答案"""
    await question_answer_service.create(db=db, obj=obj)
    return response_base.success()


@router.put(
    '/answer/{pk}',
    summary='更新答案',
    dependencies=[
        Depends(RequestPermission('gongkao:question:update')),
        DependsRBAC,
    ],
)
async def update_gongkao_question_answer(
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='答案 ID')],
    obj: UpdateQuestionAnswerParam,
) -> ResponseModel:
    """更新答案"""
    count = await question_answer_service.update(db=db, pk=pk, obj=obj)
    if count > 0:
        return response_base.success()
    return response_base.fail()


@router.delete(
    '/answer',
    summary='删除答案',
    dependencies=[
        Depends(RequestPermission('gongkao:question:delete')),
        DependsRBAC,
    ],
)
async def delete_gongkao_question_answer(db: CurrentSessionTransaction, obj: DeleteQuestionAnswerParam) -> ResponseModel:
    """删除答案"""
    count = await question_answer_service.delete(db=db, obj=obj)
    if count > 0:
        return response_base.success()
    return response_base.fail()


# ==================== 材料接口 ====================
@router.get('/material/{pk}', summary='获取材料详情')
async def get_gongkao_material(
    db: CurrentSession,
    pk: Annotated[int, Path(description='材料 ID')],
) -> ResponseSchemaModel[GetMaterialDetail]:
    """获取材料详情"""
    data = await material_service.get(db=db, pk=pk)
    return response_base.success(data=data)


@router.get(
    '/material',
    summary='获取材料列表',
    dependencies=[DependsPagination],
)
async def get_gongkao_material_list(
    db: CurrentSession,
    title: Annotated[str | None, Query(description='材料标题')] = None,
    category_id: Annotated[int | None, Query(description='关联分类 ID')] = None,
    year: Annotated[int | None, Query(description='年份')] = None,
    source: Annotated[str | None, Query(description='来源')] = None,
    status: Annotated[bool | None, Query(description='状态')] = None,
) -> ResponseSchemaModel[PageData[GetMaterialDetail]]:
    """获取材料列表"""
    params = MaterialParam(
        title=title,
        category_id=category_id,
        year=year,
        source=source,
        status=status,
    )
    data = await material_service.get_list(db=db, params=params)
    return response_base.success(data=data)


@router.post(
    '/material',
    summary='创建材料',
    dependencies=[
        Depends(RequestPermission('gongkao:material:create')),
        DependsRBAC,
    ],
)
async def create_gongkao_material(
    request: Request,
    db: CurrentSessionTransaction,
    obj: CreateMaterialParam,
) -> ResponseModel:
    """创建材料"""
    await material_service.create(db=db, obj=obj, created_by=request.user.id)
    return response_base.success()


@router.put(
    '/material/{pk}',
    summary='更新材料',
    dependencies=[
        Depends(RequestPermission('gongkao:material:update')),
        DependsRBAC,
    ],
)
async def update_gongkao_material(
    request: Request,
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='材料 ID')],
    obj: UpdateMaterialParam,
) -> ResponseModel:
    """更新材料"""
    count = await material_service.update(db=db, pk=pk, obj=obj, updated_by=request.user.id)
    if count > 0:
        return response_base.success()
    return response_base.fail()


@router.delete(
    '/material',
    summary='删除材料',
    dependencies=[
        Depends(RequestPermission('gongkao:material:delete')),
        DependsRBAC,
    ],
)
async def delete_gongkao_material(db: CurrentSessionTransaction, obj: DeleteMaterialParam) -> ResponseModel:
    """删除材料"""
    count = await material_service.delete(db=db, obj=obj)
    if count > 0:
        return response_base.success()
    return response_base.fail()
