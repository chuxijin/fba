#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Annotated

from fastapi import APIRouter, Body, Depends, Path, Request

from backend.app.question_bank.crud.crud_wrong_question import wrong_question_dao
from backend.app.question_bank.schema.wrong_question import (
    GetWrongQuestionDetail,
    GetWrongQuestionListItem,
    WrongQuestionChapterCountItem,
    WrongQuestionAnswerCorrectParam,
    WrongQuestionGroupItem,
    WrongQuestionQueryParam,
)
from backend.app.question_bank.service.membership_service import membership_service
from backend.app.question_bank.service.wrong_question_service import wrong_question_service
from backend.common.pagination import DependsPagination, PageData, paging_data
from backend.common.response.response_code import CustomResponse
from backend.common.response.response_schema import ResponseModel, ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.database.db import CurrentSession, CurrentSessionTransaction

router = APIRouter()


# ===== 统计接口（必须在 /{pk} 之前注册，避免路径参数误匹配） =====


@router.get('/statistics', summary='获取错题本统计', name='qbank_wrong_question_statistics', dependencies=[DependsJwtAuth])
async def get_statistics(
    request: Request,
    db: CurrentSession,
    group_by: str | None = None,
    cat_id: int | None = None,
    kp_cat_id: int | None = None,
) -> ResponseSchemaModel:
    """获取用户的错题本统计数据，传 group_by 时返回树形分组"""
    if group_by:
        data = await wrong_question_service.get_statistics_with_groups(
            db=db, user_id=request.user.id, group_by=group_by, cat_id=cat_id, kp_cat_id=kp_cat_id,
        )
        return response_base.success(data=data)
    stats = await wrong_question_service.get_statistics(
        db=db,
        user_id=request.user.id,
        cat_id=cat_id,
        kp_cat_id=kp_cat_id,
    )
    return response_base.success(data=stats)


@router.get('/grouped', summary='获取错题分组聚合', name='qbank_wrong_question_grouped', dependencies=[DependsJwtAuth])
async def get_grouped(
    request: Request,
    db: CurrentSession,
    group_by: str = 'bank',
    cat_id: int | None = None,
    kp_cat_id: int | None = None,
) -> ResponseSchemaModel[list[WrongQuestionGroupItem]]:
    """按题库或知识点分组聚合错题数量"""
    data = await wrong_question_service.get_grouped(
        db=db,
        user_id=request.user.id,
        group_by=group_by,
        cat_id=cat_id,
        kp_cat_id=kp_cat_id,
    )
    return response_base.success(data=data)


@router.get('/ids', summary='获取分组内错题 ID 列表', name='qbank_wrong_question_ids', dependencies=[DependsJwtAuth])
async def get_question_ids(
    request: Request,
    db: CurrentSession,
    bank_id: int | None = None,
    chapter_id: int | None = None,
    knowledge_point: str | None = None,
) -> ResponseSchemaModel[list[int]]:
    """按分组条件获取未掌握错题的题目 ID 列表"""
    if chapter_id is not None:
        bank_id = await membership_service.resolve_bank_context_for_chapter(
            db=db,
            chapter_id=chapter_id,
            bank_id=bank_id,
            user_id=request.user.id,
        )

    ids = await wrong_question_dao.get_question_ids(
        db=db, user_id=request.user.id, bank_id=bank_id, chapter_id=chapter_id, knowledge_point=knowledge_point,
    )
    return response_base.success(data=ids)


@router.get(
    '/bank-chapter-counts',
    summary='获取当前题库章节错题计数',
    name='qbank_wrong_question_bank_chapter_counts',
    dependencies=[DependsJwtAuth],
)
async def get_bank_chapter_counts(
    request: Request,
    db: CurrentSession,
    bank_id: int,
) -> ResponseSchemaModel[list[WrongQuestionChapterCountItem]]:
    """获取当前题库下各章节未掌握错题数量"""
    await membership_service.verify_bank_list_access(db=db, user_id=request.user.id, bank_id=bank_id)
    data = await wrong_question_service.get_bank_chapter_counts(
        db=db,
        user_id=request.user.id,
        bank_id=bank_id,
    )
    return response_base.success(data=data)


# ===== 详情 =====


@router.get('/{pk}', summary='获取错题详情', name='qbank_wrong_question_get', dependencies=[DependsJwtAuth])
async def get_wrong_question(
    request: Request,
    db: CurrentSession,
    pk: Annotated[int, Path(description='错题 ID')],
) -> ResponseSchemaModel[GetWrongQuestionDetail]:
    """获取错题详情"""
    wrong = await wrong_question_service.get_wrong_question(db=db, wrong_id=pk, user_id=request.user.id)
    return response_base.success(data=GetWrongQuestionDetail.model_validate(wrong))


# ===== 列表 =====


@router.get(
    '',
    summary='获取用户错题本列表',
    name='qbank_wrong_question_get_list',
    dependencies=[DependsJwtAuth, DependsPagination],
)
async def get_wrong_questions(
    request: Request,
    db: CurrentSession,
    query: Annotated[WrongQuestionQueryParam, Depends()],
) -> ResponseSchemaModel[PageData[GetWrongQuestionListItem]]:
    """获取用户的错题本列表"""
    if query.chapter_id is not None:
        query.bank_id = await membership_service.resolve_bank_context_for_chapter(
            db=db,
            chapter_id=query.chapter_id,
            bank_id=query.bank_id,
            user_id=request.user.id,
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


@router.put('/{pk}/pin', summary='设置错题置顶', name='qbank_wrong_question_set_pin', dependencies=[DependsJwtAuth])
async def set_pin(
    request: Request,
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='错题 ID')],
    is_pinned: Annotated[bool, Body(embed=True, description='是否置顶')],
) -> ResponseModel:
    """设置错题置顶或取消置顶"""
    count = await wrong_question_service.set_pin(db=db, wrong_id=pk, user_id=request.user.id, is_pinned=is_pinned)
    if count > 0:
        return response_base.success()
    return response_base.fail()


@router.delete('', summary='删除错题', name='qbank_wrong_question_delete', dependencies=[DependsJwtAuth])
async def delete_wrong_questions(
    request: Request,
    db: CurrentSessionTransaction,
    wrong_ids: Annotated[list[int], Body(description='错题 ID 列表（支持单个或批量）')],
) -> ResponseModel:
    """从错题本移除题目"""
    count = await wrong_question_service.delete_wrong_questions(
        db=db, wrong_ids=wrong_ids, user_id=request.user.id
    )
    if count > 0:
        return response_base.success(res=CustomResponse(code=200, msg=f'成功删除 {count} 条错题记录'))
    return response_base.fail(res=CustomResponse(code=400, msg='删除失败'))


@router.post('/clear-mastered', summary='清空已掌握的错题', name='qbank_wrong_question_clear_mastered', dependencies=[DependsJwtAuth])
async def clear_mastered(
    request: Request,
    db: CurrentSessionTransaction,
) -> ResponseModel:
    """清空用户已掌握的错题"""
    count = await wrong_question_service.clear_mastered(db=db, user_id=request.user.id)
    if count > 0:
        return response_base.success(res=CustomResponse(code=200, msg=f'成功清空 {count} 条已掌握错题'))
    return response_base.success(res=CustomResponse(code=200, msg='没有已掌握的错题'))


@router.post(
    '/{question_id}/answer-correct',
    summary='错题答对上报',
    name='qbank_wrong_question_answer_correct',
    dependencies=[DependsJwtAuth],
)
async def answer_correct(
    request: Request,
    db: CurrentSessionTransaction,
    question_id: Annotated[int, Path(description='题目 ID')],
    obj: WrongQuestionAnswerCorrectParam,
) -> ResponseSchemaModel:
    """
    轻量刷题模式下，用户答对某题后调用

    根据 question_id + user_id 查找错题记录，增加连续答对次数，
    达到 mastery_threshold 自动标记为已掌握。
    """
    mastery_threshold = obj.mastery_threshold
    if mastery_threshold is None:
        from backend.app.question_bank.service.user_settings_service import user_settings_service

        mastery_threshold = await user_settings_service.get_mastery_threshold(db=db, user_id=request.user.id)

    data = await wrong_question_service.answer_correct(
        db=db,
        user_id=request.user.id,
        question_id=question_id,
        placement_id=obj.placement_id,
        mastery_threshold=mastery_threshold,
    )
    return response_base.success(data=data)
