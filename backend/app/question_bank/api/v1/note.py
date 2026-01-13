#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
笔记接口

设计原则：
- 用户可为题目写笔记，支持公开/私密
- 公开笔记可被其他用户点赞/点踩
- 管理员可精选优质笔记
"""
from typing import Annotated

from fastapi import APIRouter, Body, Path, Query

from backend.app.question_bank.crud.crud_question_note import question_note_dao
from backend.app.question_bank.schema.note import (
    CreateQuestionNoteParam,
    GetQuestionNoteDetail,
    GetQuestionNoteListItem,
    GetUserNoteVoteDetail,
    NoteVoteStatistics,
    UpdateQuestionNoteParam,
)
from backend.app.question_bank.security import DependsCustomerAuth
from backend.app.question_bank.service.note_service import note_service
from backend.common.pagination import DependsPagination, PageData, paging_data
from backend.common.response.response_code import CustomResponse
from backend.common.response.response_schema import ResponseModel, ResponseSchemaModel, response_base
from backend.common.security.auth_strategy import AuthUser
from backend.database.db import CurrentSession, CurrentSessionTransaction

router = APIRouter()


# ============ 笔记管理接口 ============


@router.post('', summary='创建笔记')
async def create_note(
    db: CurrentSessionTransaction,
    obj: CreateQuestionNoteParam,
    current_user: AuthUser = DependsCustomerAuth,
) -> ResponseSchemaModel[GetQuestionNoteDetail]:
    """创建题目笔记"""
    new_note = await note_service.create_note(db=db, user_id=current_user.user_id, obj=obj)
    return response_base.success(data=GetQuestionNoteDetail.model_validate(new_note))


@router.get('/{pk}', summary='获取笔记详情')
async def get_note(
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='笔记 ID')],
    current_user: AuthUser = DependsCustomerAuth,
) -> ResponseSchemaModel[GetQuestionNoteDetail]:
    """获取笔记详情"""
    note = await note_service.get_note(db=db, note_id=pk, user_id=current_user.user_id)
    return response_base.success(data=GetQuestionNoteDetail.model_validate(note))


@router.get('', summary='获取笔记列表', dependencies=[DependsPagination])
async def get_notes(
    db: CurrentSession,
    current_user: AuthUser = DependsCustomerAuth,
    question_id: Annotated[int | None, Query(description='题目 ID')] = None,
    is_public: Annotated[bool | None, Query(description='是否公开')] = None,
    is_featured: Annotated[bool | None, Query(description='是否精选')] = None,
    my_notes: Annotated[bool, Query(description='只看我的笔记')] = False,
) -> ResponseSchemaModel[PageData[GetQuestionNoteListItem]]:
    """获取笔记列表（分页）"""
    user_id = current_user.user_id if my_notes else None

    stmt = await question_note_dao.get_select(
        user_id=user_id, question_id=question_id, is_public=is_public, is_featured=is_featured
    )
    page_data = await paging_data(db, stmt, GetQuestionNoteListItem)
    return response_base.success(data=page_data)


@router.get('/questions/{question_id}/public', summary='获取题目的公开笔记')
async def get_question_public_notes(
    db: CurrentSession,
    question_id: Annotated[int, Path(description='题目 ID')],
    current_user: AuthUser = DependsCustomerAuth,
    is_featured: Annotated[bool | None, Query(description='只看精选')] = None,
) -> ResponseSchemaModel[list[GetQuestionNoteListItem]]:
    """获取题目的所有公开笔记（按质量分排序）"""
    note_list = await note_service.get_question_public_notes(
        db=db, question_id=question_id, is_featured=is_featured
    )
    return response_base.success(data=note_list)


@router.put('/{pk}', summary='更新笔记')
async def update_note(
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='笔记 ID')],
    obj: UpdateQuestionNoteParam,
    current_user: AuthUser = DependsCustomerAuth,
) -> ResponseModel:
    """更新笔记内容和公开状态"""
    count = await note_service.update_note(
        db=db, note_id=pk, user_id=current_user.user_id, content=obj.content, is_public=obj.is_public
    )

    if count > 0:
        return response_base.success()
    return response_base.fail(res=CustomResponse(code=400, msg='更新失败'))


@router.delete('/{pk}', summary='删除笔记')
async def delete_note(
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='笔记 ID')],
    current_user: AuthUser = DependsCustomerAuth,
) -> ResponseModel:
    """删除笔记"""
    count = await note_service.delete_note(db=db, note_id=pk, user_id=current_user.user_id)

    if count > 0:
        return response_base.success()
    return response_base.fail(res=CustomResponse(code=400, msg='删除失败'))


# ============ 笔记投票接口 ============


@router.post('/{pk}/vote', summary='投票笔记')
async def vote_note(
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='笔记 ID')],
    vote_value: Annotated[int, Body(embed=True, description='投票值：1=点赞，-1=点踩')],
    current_user: AuthUser = DependsCustomerAuth,
) -> ResponseModel:
    """对笔记投票（点赞/点踩）"""
    await note_service.vote_note(db=db, note_id=pk, user_id=current_user.user_id, vote_value=vote_value)
    return response_base.success()


@router.delete('/{pk}/vote', summary='取消投票')
async def cancel_vote(
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='笔记 ID')],
    current_user: AuthUser = DependsCustomerAuth,
) -> ResponseModel:
    """取消对笔记的投票"""
    count = await note_service.cancel_vote(db=db, note_id=pk, user_id=current_user.user_id)

    if count > 0:
        return response_base.success()
    return response_base.fail(res=CustomResponse(code=400, msg='您还未对此笔记投票'))


@router.get('/{pk}/vote/my', summary='获取我的投票')
async def get_my_vote(
    db: CurrentSession,
    pk: Annotated[int, Path(description='笔记 ID')],
    current_user: AuthUser = DependsCustomerAuth,
) -> ResponseSchemaModel[GetUserNoteVoteDetail]:
    """获取当前用户对笔记的投票状态"""
    vote = await note_service.get_my_vote(db=db, note_id=pk, user_id=current_user.user_id)
    return response_base.success(data=GetUserNoteVoteDetail.model_validate(vote))


@router.get('/{pk}/vote/statistics', summary='获取笔记投票统计')
async def get_vote_statistics(
    db: CurrentSession, pk: Annotated[int, Path(description='笔记 ID')]
) -> ResponseSchemaModel[NoteVoteStatistics]:
    """获取笔记的投票统计数据"""
    stats = await note_service.get_vote_statistics(db=db, note_id=pk)
    return response_base.success(data=stats)
