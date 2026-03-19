#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Annotated

from fastapi import APIRouter, Body, Depends, Path

from backend.app.question_bank.crud.crud_wrong_question import wrong_question_dao
from backend.app.question_bank.schema.wrong_question import (
    GetWrongQuestionDetail,
    GetWrongQuestionListItem,
    WrongQuestionQueryParam,
    WrongQuestionStatistics,
)
from backend.app.question_bank.security import DependsCurrentUser
from backend.app.question_bank.service.wrong_question_service import wrong_question_service
from backend.common.pagination import DependsPagination, PageData, paging_data
from backend.common.response.response_code import CustomResponse
from backend.common.response.response_schema import ResponseModel, ResponseSchemaModel, response_base
from backend.common.security.auth_strategy import AuthUser
from backend.database.db import CurrentSession, CurrentSessionTransaction

router = APIRouter()


# ===== 统计接口（必须在 /{pk} 之前注册，避免路径参数误匹配） =====


@router.get('/statistics', summary='获取错题本统计', name='qbank_wrong_question_statistics')
async def get_statistics(
    db: CurrentSession, current_user: AuthUser = DependsCurrentUser
) -> ResponseSchemaModel[WrongQuestionStatistics]:
    """获取用户的错题本统计数据"""
    stats = await wrong_question_service.get_statistics(db=db, user_id=current_user.user_id)
    return response_base.success(data=stats)


# ===== 详情 =====


@router.get('/{pk}', summary='获取错题详情', name='qbank_wrong_question_get')
async def get_wrong_question(
    db: CurrentSession,
    pk: Annotated[int, Path(description='错题 ID')],
    current_user: AuthUser = DependsCurrentUser,
) -> ResponseSchemaModel[GetWrongQuestionDetail]:
    """获取错题详情"""
    wrong = await wrong_question_service.get_wrong_question(db=db, wrong_id=pk, user_id=current_user.user_id)
    return response_base.success(data=GetWrongQuestionDetail.model_validate(wrong))


# ===== 列表 =====


@router.get('', summary='获取用户错题本列表', name='qbank_wrong_question_get_list', dependencies=[DependsPagination])
async def get_wrong_questions(
    db: CurrentSession,
    query: Annotated[WrongQuestionQueryParam, Depends()],
    current_user: AuthUser = DependsCurrentUser,
) -> ResponseSchemaModel[PageData[GetWrongQuestionListItem]]:
    """获取用户的错题本列表"""
    stmt = await wrong_question_dao.get_select(
        user_id=current_user.user_id,
        is_mastered=query.is_mastered,
        is_pinned=query.is_pinned,
        bank_id=query.bank_id,
        chapter_id=query.chapter_id,
        keyword=query.keyword,
    )
    page_data = await paging_data(db, stmt, GetWrongQuestionListItem)
    return response_base.success(data=page_data)


# ===== 操作 =====


@router.put('/{pk}/pin', summary='设置错题置顶', name='qbank_wrong_question_set_pin')
async def set_pin(
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='错题 ID')],
    is_pinned: Annotated[bool, Body(embed=True, description='是否置顶')],
    current_user: AuthUser = DependsCurrentUser,
) -> ResponseModel:
    """设置错题置顶或取消置顶"""
    count = await wrong_question_service.set_pin(db=db, wrong_id=pk, user_id=current_user.user_id, is_pinned=is_pinned)
    if count > 0:
        return response_base.success()
    return response_base.fail()


@router.delete('', summary='删除错题', name='qbank_wrong_question_delete')
async def delete_wrong_questions(
    db: CurrentSessionTransaction,
    wrong_ids: Annotated[list[int], Body(description='错题 ID 列表（支持单个或批量）')],
    current_user: AuthUser = DependsCurrentUser,
) -> ResponseModel:
    """从错题本移除题目"""
    count = await wrong_question_service.delete_wrong_questions(
        db=db, wrong_ids=wrong_ids, user_id=current_user.user_id
    )
    if count > 0:
        return response_base.success(res=CustomResponse(code=200, msg=f'成功删除 {count} 条错题记录'))
    return response_base.fail(res=CustomResponse(code=400, msg='删除失败'))


@router.post('/clear-mastered', summary='清空已掌握的错题', name='qbank_wrong_question_clear_mastered')
async def clear_mastered(
    db: CurrentSessionTransaction, current_user: AuthUser = DependsCurrentUser
) -> ResponseModel:
    """清空用户已掌握的错题"""
    count = await wrong_question_service.clear_mastered(db=db, user_id=current_user.user_id)
    if count > 0:
        return response_base.success(res=CustomResponse(code=200, msg=f'成功清空 {count} 条已掌握错题'))
    return response_base.success(res=CustomResponse(code=200, msg='没有已掌握的错题'))

