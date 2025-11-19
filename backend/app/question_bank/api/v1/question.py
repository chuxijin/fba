#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Body, Depends, Path, Query, Request

from backend.app.question_bank.schema.question import (
    CreateQuestionAnalysisParam,
    CreateQuestionParam,
    DeleteQuestionParam,
    GetQuestionAnalysisDetail,
    GetQuestionDetail,
    GetQuestionListItem,
    GetQuestionStatisticsDetail,
    UpdateQuestionAnalysisParam,
    UpdateQuestionParam,
)
from backend.app.question_bank.security import DependsCurrentUser
from backend.app.question_bank.service.membership_service import membership_service
from backend.app.question_bank.service.question_service import question_service
from backend.common.pagination import DependsPagination, PageData
from backend.common.response.response_schema import ResponseModel, ResponseSchemaModel, response_base
from backend.common.security.rbac import DependsRBAC
from backend.database.db import CurrentSession, CurrentSessionTransaction

router = APIRouter()


# ============ 题目相关接口 ============


@router.get('/{pk}', summary='获取题目详情（不含答案）', name='qbank_get_question', dependencies=[DependsCurrentUser])
async def get_question(
    request: Request,
    db: CurrentSession,
    pk: Annotated[int, Path(description='题目 ID')],
    user_info: tuple = DependsCurrentUser,
) -> ResponseSchemaModel[GetQuestionDetail]:
    """
    获取题目详情（不含答案和解析）

    - 👤 客户：需要会员权限验证
    - 🔐 管理员：直接查看，无需会员验证
    """
    user_type, customer = user_info

    # 客户需要验证会员权限
    if user_type == 'customer':
        await membership_service.verify_question_access(db=db, user_id=customer.user_id, question_id=pk)

    data = await question_service.get(db=db, pk=pk)
    return response_base.success(data=data)


@router.get(
    '',
    summary='获取题目列表（不含答案）',
    name='qbank_get_question_list',
    dependencies=[DependsCurrentUser, DependsPagination],
)
async def get_question_list(
    request: Request,
    db: CurrentSession,
    user_info: tuple = DependsCurrentUser,
    bank_id: Annotated[int | None, Query(description='题库 ID')] = None,
    chapter_id: Annotated[int | None, Query(description='章节 ID')] = None,
    type: Annotated[str | None, Query(description='题型')] = None,
    difficulty: Annotated[str | None, Query(description='难度')] = None,
    is_active: Annotated[bool | None, Query(description='是否启用')] = None,
    review_status: Annotated[int | None, Query(description='审核状态')] = None,
    keyword: Annotated[str | None, Query(description='关键字搜索')] = None,
    page: Annotated[int | None, Query(description='页码', ge=1)] = None,
    size: Annotated[int | None, Query(description='每页数量', ge=1, le=100)] = None,
) -> ResponseSchemaModel[PageData[GetQuestionListItem] | list[GetQuestionListItem]]:
    """
    获取题目列表（不含答案）

    - 👤 客户：需要会员权限验证，不支持分页
    - 🔐 管理员：无需会员验证，支持分页
    """
    user_type, customer = user_info

    # 客户需要验证会员权限
    if user_type == 'customer':
        if bank_id:
            await membership_service.verify_bank_list_access(db=db, user_id=customer.user_id, bank_id=bank_id)
        elif chapter_id:
            await membership_service.verify_chapter_access(db=db, user_id=customer.user_id, chapter_id=chapter_id)

    # 管理员支持分页，客户不支持
    data = await question_service.get_list(
        db=db,
        bank_id=bank_id,
        chapter_id=chapter_id,
        type=type,
        difficulty=difficulty,
        is_active=is_active,
        review_status=review_status,
        keyword=keyword,
        page=page if user_type == 'admin' else None,
        size=size if user_type == 'admin' else None,
    )
    return response_base.success(data=data)


@router.post(
    '',
    summary='创建题目',
    name='qbank_create_question',
    dependencies=[DependsRBAC],
)
async def create_question(request: Request, db: CurrentSessionTransaction, obj: CreateQuestionParam) -> ResponseModel:
    """🔐 管理员接口 - 创建题目"""
    await question_service.create(db=db, obj=obj, user_id=request.user.id)
    return response_base.success()


@router.put(
    '/{pk}',
    summary='更新题目',
    name='qbank_update_question',
    dependencies=[DependsRBAC],
)
async def update_question(
    request: Request,
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='题目 ID')],
    obj: UpdateQuestionParam,
) -> ResponseModel:
    """🔐 管理员接口 - 更新题目"""
    count = await question_service.update(db=db, pk=pk, obj=obj, user_id=request.user.id)
    if count > 0:
        return response_base.success()
    return response_base.fail()


@router.delete(
    '',
    summary='删除题目',
    name='qbank_delete_question',
    dependencies=[DependsRBAC],
)
async def delete_question(db: CurrentSessionTransaction, obj: DeleteQuestionParam) -> ResponseModel:
    """🔐 管理员接口 - 删除题目（级联删除解析和统计）"""
    count = await question_service.delete(db=db, obj=obj)
    if count > 0:
        return response_base.success()
    return response_base.fail()


# ============ 题目解析相关接口 ============


@router.get(
    '/{pk}/analysis',
    summary='获取题目解析（含答案）',
    name='qbank_get_question_analysis',
    dependencies=[DependsCurrentUser],
)
async def get_question_analysis(
    request: Request,
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='题目 ID')],
    user_info: tuple = DependsCurrentUser,
) -> ResponseSchemaModel[GetQuestionAnalysisDetail]:
    """
    获取题目解析（含答案）

    - 👤 客户：需要会员权限验证，自动增加查看次数
    - 🔐 管理员：直接查看，不增加查看次数
    """
    user_type, customer = user_info

    # 客户需要验证会员权限
    if user_type == 'customer':
        await membership_service.verify_question_access(db=db, user_id=customer.user_id, question_id=pk)
        increment_view = True
    else:
        increment_view = False

    data = await question_service.get_analysis(db=db, question_id=pk, increment_view=increment_view)
    return response_base.success(data=data)


@router.post(
    '/{pk}/analysis',
    summary='创建题目解析',
    name='qbank_create_question_analysis',
    dependencies=[DependsRBAC],
)
async def create_question_analysis(
    request: Request,
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='题目 ID')],
    obj: CreateQuestionAnalysisParam,
) -> ResponseModel:
    """🔐 管理员接口 - 创建题目解析"""
    # 确保路径参数和请求体中的 question_id 一致
    if obj.question_id != pk:
        return response_base.fail(msg='题目 ID 不匹配')

    await question_service.create_analysis(db=db, obj=obj, user_id=request.user.id)
    return response_base.success()


@router.put(
    '/{pk}/analysis',
    summary='更新题目解析',
    name='qbank_update_question_analysis',
    dependencies=[DependsRBAC],
)
async def update_question_analysis(
    request: Request,
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='题目 ID')],
    obj: UpdateQuestionAnalysisParam,
) -> ResponseModel:
    """🔐 管理员接口 - 更新题目解析"""
    count = await question_service.update_analysis(db=db, question_id=pk, obj=obj, user_id=request.user.id)
    if count > 0:
        return response_base.success()
    return response_base.fail()


@router.post(
    '/{pk}/analysis/helpful',
    summary='标记解析是否有帮助',
    name='qbank_mark_analysis_helpful',
    dependencies=[DependsCurrentUser],
)
async def mark_analysis_helpful(
    request: Request,
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='题目 ID')],
    is_helpful: Annotated[bool, Body(embed=True, description='是否有帮助')],
) -> ResponseModel:
    """
    标记解析是否有帮助

    - 👤 客户和管理员均可使用
    """
    await question_service.mark_analysis_helpful(db=db, question_id=pk, is_helpful=is_helpful)
    return response_base.success()


# ============ 题目统计相关接口 ============


@router.get(
    '/{pk}/statistics',
    summary='获取题目统计',
    name='qbank_get_question_statistics',
    dependencies=[DependsCurrentUser],
)
async def get_question_statistics(
    request: Request,
    db: CurrentSession,
    pk: Annotated[int, Path(description='题目 ID')],
) -> ResponseSchemaModel[GetQuestionStatisticsDetail]:
    """
    获取题目统计

    - 👤 客户和管理员均可查看
    """
    data = await question_service.get_statistics(db=db, question_id=pk)
    return response_base.success(data=data)
