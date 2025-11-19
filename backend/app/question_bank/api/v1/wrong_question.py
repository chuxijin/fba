#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
错题本接口

设计原则：
- 答错自动加入错题本
- 连续答对 3 次自动标记为已掌握
- 支持置顶、移除、清空已掌握等操作
"""
from typing import Annotated

from fastapi import APIRouter, Body, Path, Query

from backend.app.question_bank.crud.crud_wrong_question import wrong_question_dao
from backend.app.question_bank.schema.wrong_question import (
    BatchDeleteWrongQuestionsParam,
    GetWrongQuestionDetail,
    GetWrongQuestionListItem,
    SetWrongQuestionPinParam,
    WrongQuestionStatistics,
)
from backend.app.question_bank.security import DependsCustomerAuth
from backend.common.pagination import DependsPagination, PageData, paging_data
from backend.common.response.response_schema import ResponseModel, ResponseSchemaModel, response_base
from backend.common.security.auth_strategy import AuthUser
from backend.database.db import CurrentSession, CurrentSessionTransaction

router = APIRouter()


@router.get('/{pk}', summary='获取错题详情', name='qbank_wrong_question_get')
async def get_wrong_question(
    db: CurrentSession,
    pk: Annotated[int, Path(description='错题 ID')],
    current_user: AuthUser = DependsCustomerAuth,
) -> ResponseSchemaModel[GetWrongQuestionDetail]:
    """获取错题详情"""
    wrong = await wrong_question_dao.get(db=db, wrong_id=pk)
    if not wrong:
        return response_base.fail(msg='错题不存在')
    if wrong.user_id != current_user.user_id:
        return response_base.fail(msg='无权访问此错题')

    return response_base.success(data=GetWrongQuestionDetail.model_validate(wrong))


@router.get('', summary='获取用户错题本列表', name='qbank_wrong_question_get_list', dependencies=[DependsPagination])
async def get_wrong_questions(
    db: CurrentSession,
    current_user: AuthUser = DependsCustomerAuth,
    is_mastered: Annotated[bool | None, Query(description='是否已掌握')] = None,
    is_pinned: Annotated[bool | None, Query(description='是否置顶')] = None,
) -> ResponseSchemaModel[PageData[GetWrongQuestionListItem]]:
    """
    获取用户的错题本列表（分页）

    支持按掌握状态、置顶状态筛选
    """
    stmt = await wrong_question_dao.get_select(
        user_id=current_user.user_id, is_mastered=is_mastered, is_pinned=is_pinned
    )
    page_data = await paging_data(db, stmt, GetWrongQuestionListItem)
    return response_base.success(data=page_data)


@router.put('/{pk}/pin', summary='设置错题置顶', name='qbank_wrong_question_set_pin')
async def set_pin(
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='错题 ID')],
    is_pinned: Annotated[bool, Body(embed=True, description='是否置顶')],
    current_user: AuthUser = DependsCustomerAuth,
) -> ResponseModel:
    """设置错题置顶或取消置顶"""
    wrong = await wrong_question_dao.get(db=db, wrong_id=pk)
    if not wrong:
        return response_base.fail(msg='错题不存在')
    if wrong.user_id != current_user.user_id:
        return response_base.fail(msg='无权操作此错题')

    count = await wrong_question_dao.set_pin(db=db, wrong_id=pk, is_pinned=is_pinned)
    if count > 0:
        return response_base.success()
    return response_base.fail()


@router.delete('/{pk}', summary='从错题本移除', name='qbank_wrong_question_delete')
async def delete_wrong_question(
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='错题 ID')],
    current_user: AuthUser = DependsCustomerAuth,
) -> ResponseModel:
    """
    从错题本移除题目

    手动从错题本中删除
    """
    wrong = await wrong_question_dao.get(db=db, wrong_id=pk)
    if not wrong:
        return response_base.fail(msg='错题不存在')
    if wrong.user_id != current_user.user_id:
        return response_base.fail(msg='无权操作此错题')

    count = await wrong_question_dao.delete(db=db, wrong_id=pk)
    if count > 0:
        return response_base.success()
    return response_base.fail()


@router.post('/batch-delete', summary='批量删除错题', name='qbank_wrong_question_batch_delete')
async def batch_delete_wrong_questions(
    db: CurrentSessionTransaction,
    obj: BatchDeleteWrongQuestionsParam,
    current_user: AuthUser = DependsCustomerAuth,
) -> ResponseModel:
    """批量从错题本移除题目"""
    # 验证所有错题是否属于当前用户
    for wrong_id in obj.wrong_ids:
        wrong = await wrong_question_dao.get(db=db, wrong_id=wrong_id)
        if wrong and wrong.user_id != current_user.user_id:
            return response_base.fail(msg=f'无权操作错题 {wrong_id}')

    # 批量删除
    count = 0
    for wrong_id in obj.wrong_ids:
        count += await wrong_question_dao.delete(db=db, wrong_id=wrong_id)

    if count > 0:
        return response_base.success(msg=f'成功删除 {count} 条错题记录')
    return response_base.fail()


@router.post('/clear-mastered', summary='清空已掌握的错题', name='qbank_wrong_question_clear_mastered')
async def clear_mastered(
    db: CurrentSessionTransaction, current_user: AuthUser = DependsCustomerAuth
) -> ResponseModel:
    """
    清空用户已掌握的错题

    删除所有 is_mastered = true 的记录
    """
    count = await wrong_question_dao.clear_mastered(db=db, user_id=current_user.user_id)
    if count > 0:
        return response_base.success(msg=f'成功清空 {count} 条已掌握错题')
    return response_base.success(msg='没有已掌握的错题')


@router.get('/statistics', summary='获取错题本统计', name='qbank_wrong_question_statistics')
async def get_statistics(
    db: CurrentSession, current_user: AuthUser = DependsCustomerAuth
) -> ResponseSchemaModel[WrongQuestionStatistics]:
    """
    获取用户的错题本统计数据

    包括总数、已掌握数、未掌握数、平均错误次数
    """
    all_wrongs = await wrong_question_dao.get_by_user(db=db, user_id=current_user.user_id)

    total_count = len(all_wrongs)
    mastered_count = sum(1 for w in all_wrongs if w.is_mastered)
    unmastered_count = total_count - mastered_count
    avg_wrong_count = sum(w.wrong_count for w in all_wrongs) / total_count if total_count > 0 else 0

    stats = WrongQuestionStatistics(
        total_count=total_count,
        mastered_count=mastered_count,
        unmastered_count=unmastered_count,
        avg_wrong_count=round(avg_wrong_count, 2),
    )

    return response_base.success(data=stats)
