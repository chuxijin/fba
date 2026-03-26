#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Annotated

from fastapi import APIRouter, Body, Depends, Path, Request

from backend.app.question_bank.crud.crud_wrong_question import wrong_question_dao
from backend.app.question_bank.schema.wrong_question import (
    GetWrongQuestionDetail,
    GetWrongQuestionListItem,
    WrongQuestionGroupItem,
    WrongQuestionAnswerCorrectParam,
    WrongQuestionQueryParam,
    WrongQuestionStatistics,
)
from backend.common.security.jwt import DependsJwtAuth
from backend.app.question_bank.service.membership_service import membership_service
from backend.app.question_bank.service.wrong_question_service import wrong_question_service
from backend.common.pagination import DependsPagination, PageData, paging_data
from backend.common.response.response_code import CustomResponse
from backend.common.response.response_schema import ResponseModel, ResponseSchemaModel, response_base
from backend.database.db import CurrentSession, CurrentSessionTransaction

router = APIRouter()


# ===== 统计接口（必须在 /{pk} 之前注册，避免路径参数误匹配） =====


@router.get('/statistics', summary='获取错题本统计', name='qbank_wrong_question_statistics')
async def get_statistics(
    db: CurrentSession,
    request: Request,
    group_by: str | None = None,
    _token: str = DependsJwtAuth,
) -> ResponseSchemaModel:
    """获取用户的错题本统计数据，传 group_by 时返回树形分组"""
    if group_by:
        data = await wrong_question_service.get_statistics_with_groups(
            db=db, user_id=request.user.id, group_by=group_by,
        )
        return response_base.success(data=data)
    stats = await wrong_question_service.get_statistics(db=db, user_id=request.user.id)
    return response_base.success(data=stats)


@router.get('/grouped', summary='获取错题分组聚合', name='qbank_wrong_question_grouped')
async def get_grouped(
    db: CurrentSession,
    request: Request,
    group_by: str = 'bank',
    _token: str = DependsJwtAuth,
) -> ResponseSchemaModel[list[WrongQuestionGroupItem]]:
    """按题库或知识点分组聚合错题数量"""
    data = await wrong_question_service.get_grouped(db=db, user_id=request.user.id, group_by=group_by)
    return response_base.success(data=data)


@router.get('/ids', summary='获取分组内错题 ID 列表', name='qbank_wrong_question_ids')
async def get_question_ids(
    db: CurrentSession,
    request: Request,
    bank_id: int | None = None,
    chapter_id: int | None = None,
    knowledge_point: str | None = None,
    _token: str = DependsJwtAuth,
) -> ResponseSchemaModel[list[int]]:
    """按分组条件获取未掌握错题的题目 ID 列表"""
    if bank_id is not None and chapter_id is not None:
        await membership_service.verify_bank_chapter_relation(db=db, bank_id=bank_id, chapter_id=chapter_id)

    ids = await wrong_question_dao.get_question_ids(
        db=db, user_id=request.user.id, bank_id=bank_id, chapter_id=chapter_id, knowledge_point=knowledge_point,
    )
    return response_base.success(data=ids)


# ===== 详情 =====


@router.get('/{pk}', summary='获取错题详情', name='qbank_wrong_question_get')
async def get_wrong_question(
    db: CurrentSession,
    pk: Annotated[int, Path(description='错题 ID')],
    request: Request, _token: str = DependsJwtAuth,
) -> ResponseSchemaModel[GetWrongQuestionDetail]:
    """获取错题详情"""
    wrong = await wrong_question_service.get_wrong_question(db=db, wrong_id=pk, user_id=request.user.id)
    return response_base.success(data=GetWrongQuestionDetail.model_validate(wrong))


# ===== 列表 =====


@router.get('', summary='获取用户错题本列表', name='qbank_wrong_question_get_list', dependencies=[DependsPagination])
async def get_wrong_questions(
    db: CurrentSession,
    query: Annotated[WrongQuestionQueryParam, Depends()],
    request: Request, _token: str = DependsJwtAuth,
) -> ResponseSchemaModel[PageData[GetWrongQuestionListItem]]:
    """获取用户的错题本列表"""
    if query.bank_id is not None and query.chapter_id is not None:
        await membership_service.verify_bank_chapter_relation(
            db=db,
            bank_id=query.bank_id,
            chapter_id=query.chapter_id,
        )

    stmt = await wrong_question_dao.get_select(
        user_id=request.user.id,
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
    request: Request, _token: str = DependsJwtAuth,
) -> ResponseModel:
    """设置错题置顶或取消置顶"""
    count = await wrong_question_service.set_pin(db=db, wrong_id=pk, user_id=request.user.id, is_pinned=is_pinned)
    if count > 0:
        return response_base.success()
    return response_base.fail()


@router.delete('', summary='删除错题', name='qbank_wrong_question_delete')
async def delete_wrong_questions(
    db: CurrentSessionTransaction,
    wrong_ids: Annotated[list[int], Body(description='错题 ID 列表（支持单个或批量）')],
    request: Request, _token: str = DependsJwtAuth,
) -> ResponseModel:
    """从错题本移除题目"""
    count = await wrong_question_service.delete_wrong_questions(
        db=db, wrong_ids=wrong_ids, user_id=request.user.id
    )
    if count > 0:
        return response_base.success(res=CustomResponse(code=200, msg=f'成功删除 {count} 条错题记录'))
    return response_base.fail(res=CustomResponse(code=400, msg='删除失败'))


@router.post('/clear-mastered', summary='清空已掌握的错题', name='qbank_wrong_question_clear_mastered')
async def clear_mastered(
    db: CurrentSessionTransaction, request: Request, _token: str = DependsJwtAuth
) -> ResponseModel:
    """清空用户已掌握的错题"""
    count = await wrong_question_service.clear_mastered(db=db, user_id=request.user.id)
    if count > 0:
        return response_base.success(res=CustomResponse(code=200, msg=f'成功清空 {count} 条已掌握错题'))
    return response_base.success(res=CustomResponse(code=200, msg='没有已掌握的错题'))


@router.post('/{question_id}/answer-correct', summary='错题答对上报', name='qbank_wrong_question_answer_correct')
async def answer_correct(
    db: CurrentSessionTransaction,
    question_id: Annotated[int, Path(description='题目 ID')],
    request: Request,
    obj: WrongQuestionAnswerCorrectParam,
    _token: str = DependsJwtAuth,
) -> ResponseSchemaModel:
    """
    轻量刷题模式下，用户答对某题后调用

    根据 question_id + user_id 查找错题记录，增加连续答对次数，
    达到 mastery_threshold 自动标记为已掌握。
    """
    from datetime import datetime

    if obj.placement_id is not None:
        wrong = await wrong_question_dao.get_by_user_and_question(
            db=db,
            user_id=request.user.id,
            question_id=question_id,
            placement_id=obj.placement_id,
        )
        wrong_records = [wrong] if wrong else []
    else:
        wrong_records = await wrong_question_dao.list_by_user_and_question(
            db=db,
            user_id=request.user.id,
            question_id=question_id,
        )

    wrong_records = [item for item in wrong_records if item]
    if not wrong_records:
        return response_base.success(
            data={'is_mastered': False, 'correct_streak': 0, 'message': '未找到对应错题记录'},
        )

    practice_time = datetime.now()
    for wrong in wrong_records:
        await wrong_question_dao.increment_correct(
            db=db,
            wrong_id=wrong.id,
            practice_time=practice_time,
            mastery_threshold=obj.mastery_threshold,
        )
        await db.refresh(wrong)

    return response_base.success(
        data={
            'is_mastered': all(item.is_mastered for item in wrong_records),
            'correct_streak': max(item.correct_streak for item in wrong_records),
            'affected_count': len(wrong_records),
        },
    )

