#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, Request

from backend.app.question_bank.schema.bank import (
    BankProgressSummary,
    CreateBankParam,
    DeleteBankParam,
    GetBankChapterProgress,
    GetBankDetail,
    GetBankDetailWithChapters,
    UpdateBankParam,
)
from backend.app.question_bank.schema.question import GetQuestionWithAnswer
from backend.app.question_bank.service.bank_service import bank_service
from backend.app.question_bank.service.membership_service import membership_service
from backend.app.question_bank.service.question_service import question_service
from backend.common.response.response_schema import ResponseModel, ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth, get_token, jwt_authentication
from backend.common.security.permission import RequestPermission
from backend.common.security.rbac import DependsRBAC
from backend.database.db import CurrentSession, CurrentSessionTransaction

router = APIRouter()


async def get_authenticated_user_id(request: Request) -> int:
    """
    获取认证用户 ID

    :param request: FastAPI 请求对象
    :return:
    """
    user_id = getattr(request.user, 'id', None)
    if user_id is not None:
        return int(user_id)

    token = get_token(request)
    user = await jwt_authentication(token)
    return int(user.id)


@router.get('/recommend', summary='获取推荐题库', name='qbank_get_recommend_banks')
async def get_recommend_banks(
    db: CurrentSession,
) -> ResponseSchemaModel[list[GetBankDetail]]:
    """🌍 公开接口 - 获取全局热门推荐题库（最近7天做题最多的前5个）"""
    data = await bank_service.get_recommend_banks(db=db)
    return response_base.success(data=data)


@router.get(
    '/progress/summary',
    summary='批量获取题库进度摘要',
    name='qbank_get_bank_progress_summary',
    dependencies=[DependsJwtAuth],
)
async def get_bank_progress_summary(
    request: Request,
    db: CurrentSession,
    bank_ids: Annotated[list[int] | None, Query(description='题库 ID 列表')] = None,
    cat_id: Annotated[int | None, Query(description='分类 ID（自动展开子孙分类下的所有题库）')] = None,
) -> ResponseSchemaModel[list[BankProgressSummary]]:
    """🔒 登录接口 - 批量获取题库累计进度摘要"""
    data = await bank_service.get_progress_summaries(
        db=db, bank_ids=bank_ids, cat_id=cat_id, user_id=request.user.id,
    )
    return response_base.success(data=data)


@router.get('/{pk}', summary='获取题库详情', name='qbank_get_bank')
async def get_bank(
    db: CurrentSession, pk: Annotated[int, Path(description='题库 ID')]
) -> ResponseSchemaModel[GetBankDetailWithChapters]:
    """🌍 公开接口 - 任何人都可以查看题库详情（含章节树）"""
    data = await bank_service.get(db=db, pk=pk)
    return response_base.success(data=data)


@router.get(
    '/{pk}/chapter-progress',
    summary='获取题库章节进度',
    name='qbank_get_bank_chapter_progress',
    dependencies=[DependsJwtAuth],
)
async def get_bank_chapter_progress(
    request: Request,
    db: CurrentSession,
    pk: Annotated[int, Path(description='题库 ID')],
) -> ResponseSchemaModel[GetBankChapterProgress]:
    """🔒 登录接口 - 获取用户在指定题库下的章节做题进度"""
    data = await bank_service.get_chapter_progress(db=db, bank_id=pk, user_id=request.user.id)
    return response_base.success(data=data)


@router.get(
    '/{pk}/questions/all',
    summary='获取题库下所有题目（含答案）',
    name='qbank_get_bank_questions_all',
    dependencies=[DependsJwtAuth],
)
async def get_bank_questions_all(
    request: Request,
    db: CurrentSession,
    pk: Annotated[int, Path(description='题库 ID')],
    offset: Annotated[int, Query(ge=0, description='偏移量')] = 0,
    limit: Annotated[int, Query(ge=1, le=500, description='每批数量上限')] = 200,
) -> ResponseSchemaModel:
    """
    🌍 公开接口 - 分批获取指定题库下的题目（包含答案和解析）

    - 支持 offset / limit 分批拉取，避免大题库一次性 OOM
    - 用于导出或离线使用
    """
    await membership_service.verify_bank_access(db=db, user_id=request.user.id, bank_id=pk)
    bank = await bank_service.get(db=db, pk=pk)

    data = await question_service.get_list(
        db=db,
        bank_id=pk,
        page=offset // limit + 1,
        size=limit,
        include_analysis=True,
    )

    items = data.get('items', []) if isinstance(data, dict) else data
    result_with_answer = [GetQuestionWithAnswer(**item) for item in items]

    return response_base.success(data={
        'total': getattr(bank, 'q_count_cache', len(result_with_answer)),
        'offset': offset,
        'limit': limit,
        'items': result_with_answer,
    })


@router.get('', summary='获取题库树形列表', name='qbank_get_bank_list')
async def get_bank_list(
    db: CurrentSession,
    cat_id: Annotated[int | None, Query(description='分类 ID')] = None,
    status: Annotated[int | None, Query(description='题库状态')] = None,
    keyword: Annotated[str | None, Query(description='关键字搜索')] = None,
    bank_type: Annotated[int | None, Query(description='内容类型: 1=题库, 2=试卷, 3=合集')] = None,
    parent_id: Annotated[int | None, Query(description='父级题库 ID')] = None,
    study_domain: Annotated[str | None, Query(description='学习领域编码')] = None,
    exclude_empty: Annotated[bool, Query(description='是否过滤掉无题目的空题库(含递归判断)')] = True,
) -> ResponseModel:
    """🌍 公开接口 - 任何人都可以查看题库树形列表"""
    data = await bank_service.get_list(
        db=db,
        cat_id=cat_id,
        status=status,
        keyword=keyword,
        bank_type=bank_type,
        parent_id=parent_id,
        study_domain=study_domain,
        exclude_empty=exclude_empty,
    )
    return response_base.success(data=data)


@router.post(
    '',
    summary='创建题库',
    name='qbank_create_bank',
    dependencies=[
        DependsJwtAuth,
        Depends(RequestPermission('question_bank:bank:create')),
        DependsRBAC,
    ],
)
async def create_bank(request: Request, db: CurrentSessionTransaction, obj: CreateBankParam) -> ResponseModel:
    """🔐 管理员接口 - 只有管理员可以创建题库"""
    user_id = await get_authenticated_user_id(request)
    await bank_service.create(db=db, obj=obj, created_by=user_id)
    return response_base.success()


@router.put(
    '/{pk}',
    summary='更新题库',
    name='qbank_update_bank',
    dependencies=[
        DependsJwtAuth,
        Depends(RequestPermission('question_bank:bank:update')),
        DependsRBAC,
    ],
)
async def update_bank(
    request: Request, db: CurrentSessionTransaction, pk: Annotated[int, Path(description='题库 ID')], obj: UpdateBankParam
) -> ResponseModel:
    """🔐 管理员接口 - 只有管理员可以更新题库"""
    user_id = await get_authenticated_user_id(request)
    count = await bank_service.update(db=db, pk=pk, obj=obj, updated_by=user_id)
    if count > 0:
        return response_base.success()
    return response_base.fail()


@router.delete(
    '',
    summary='删除题库',
    name='qbank_delete_bank',
    dependencies=[
        DependsJwtAuth,
        Depends(RequestPermission('question_bank:bank:delete')),
        DependsRBAC,
    ],
)
async def delete_bank(db: CurrentSessionTransaction, obj: DeleteBankParam) -> ResponseModel:
    """🔐 管理员接口 - 只有管理员可以删除题库"""
    count = await bank_service.delete(db=db, obj=obj)
    if count > 0:
        return response_base.success()
    return response_base.fail()
