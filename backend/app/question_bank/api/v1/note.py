#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Annotated

from fastapi import APIRouter, Path, Query, Request

from backend.app.question_bank.crud.crud_question_note import question_note_dao
from backend.app.question_bank.schema.note import (
    CreateQuestionNoteParam,
    GetQuestionNoteDetail,
    GetQuestionNoteListItem,
    GetUserNoteVoteDetail,
    NoteVoteStatistics,
    UpdateQuestionNoteParam,
    VoteQuestionNoteParam,
)
from backend.app.question_bank.schema.wrong_question import WrongQuestionGroupItem
from backend.common.security.jwt import DependsJwtAuth
from backend.app.question_bank.service.membership_service import membership_service
from backend.app.question_bank.service.note_service import note_service
from backend.common.pagination import DependsPagination, PageData, paging_data
from backend.common.response.response_code import CustomResponse
from backend.common.response.response_schema import ResponseModel, ResponseSchemaModel, response_base
from backend.database.db import CurrentSession, CurrentSessionTransaction

router = APIRouter()


# ============ 笔记管理接口 ============


@router.post('', summary='创建笔记')
async def create_note(
    db: CurrentSessionTransaction,
    obj: CreateQuestionNoteParam,
    request: Request, _token: str = DependsJwtAuth,
) -> ResponseSchemaModel[GetQuestionNoteDetail]:
    """创建题目笔记"""
    if obj.placement_id is not None:
        await membership_service.verify_placement_access(db=db, user_id=request.user.id, placement_id=obj.placement_id)
    else:
        await membership_service.verify_question_access(db=db, user_id=request.user.id, question_id=obj.question_id)

    new_note = await note_service.create_note(db=db, user_id=request.user.id, obj=obj)
    return response_base.success(data=GetQuestionNoteDetail.model_validate(new_note))


@router.get('', summary='获取笔记列表', dependencies=[DependsPagination])
async def get_notes(
    db: CurrentSession,
    request: Request, _token: str = DependsJwtAuth,
    question_id: Annotated[int | None, Query(description='题目 ID')] = None,
    is_public: Annotated[bool | None, Query(description='是否公开')] = None,
    is_featured: Annotated[bool | None, Query(description='是否精选')] = None,
    my_notes: Annotated[bool, Query(description='只看我的笔记')] = False,
) -> ResponseSchemaModel[PageData[GetQuestionNoteListItem]]:
    """获取笔记列表（分页）"""
    user_id = request.user.id if my_notes else None

    stmt = await question_note_dao.get_select(
        user_id=user_id, question_id=question_id, is_public=is_public, is_featured=is_featured
    )
    page_data = await paging_data(db, stmt, GetQuestionNoteListItem)
    return response_base.success(data=page_data)


@router.get('/statistics', summary='获取笔记统计', name='qbank_note_statistics')
async def get_statistics(
    db: CurrentSession,
    request: Request,
    group_by: str | None = None,
    _token: str = DependsJwtAuth,
) -> ResponseSchemaModel:
    """获取用户的笔记统计数据，传 group_by 时返回树形分组"""
    if group_by:
        data = await note_service.get_statistics_with_groups(
            db=db, user_id=request.user.id, group_by=group_by,
        )
        return response_base.success(data=data)
    from backend.app.question_bank.crud.crud_question_note import question_note_dao
    stats = await question_note_dao.get_statistics(db=db, user_id=request.user.id)
    return response_base.success(data=stats)


@router.get('/grouped', summary='获取笔记分组聚合', name='qbank_note_grouped')
async def get_grouped(
    db: CurrentSession,
    request: Request,
    group_by: str = 'bank',
    _token: str = DependsJwtAuth,
) -> ResponseSchemaModel[list[WrongQuestionGroupItem]]:
    """按题库或知识点分组聚合笔记数量"""
    data = await note_service.get_grouped(db=db, user_id=request.user.id, group_by=group_by)
    return response_base.success(data=data)


@router.get('/ids', summary='获取分组内笔记题目 ID 列表', name='qbank_note_ids')
async def get_question_ids(
    db: CurrentSession,
    request: Request,
    bank_id: int | None = None,
    chapter_id: int | None = None,
    knowledge_point: str | None = None,
    _token: str = DependsJwtAuth,
) -> ResponseSchemaModel[list[int]]:
    """按分组条件获取有笔记的题目 ID 列表"""
    if bank_id is not None and chapter_id is not None:
        await membership_service.verify_bank_chapter_relation(db=db, bank_id=bank_id, chapter_id=chapter_id)

    ids = await question_note_dao.get_question_ids(
        db=db, user_id=request.user.id, bank_id=bank_id, chapter_id=chapter_id, knowledge_point=knowledge_point,
    )
    return response_base.success(data=ids)


@router.get('/questions/{question_id}/public', summary='获取题目的公开笔记')
async def get_question_public_notes(
    db: CurrentSession,
    question_id: Annotated[int, Path(description='题目 ID')],
    request: Request, _token: str = DependsJwtAuth,
    is_featured: Annotated[bool | None, Query(description='只看精选')] = None,
) -> ResponseSchemaModel[list[GetQuestionNoteListItem]]:
    """获取题目的所有公开笔记（按质量分排序）"""
    note_list = await note_service.get_question_public_notes(
        db=db, question_id=question_id, is_featured=is_featured
    )
    return response_base.success(data=note_list)


@router.get('/{pk}', summary='获取笔记详情')
async def get_note(
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='笔记 ID')],
    request: Request, _token: str = DependsJwtAuth,
) -> ResponseSchemaModel[GetQuestionNoteDetail]:
    """获取笔记详情"""
    note = await note_service.get_note(db=db, note_id=pk, user_id=request.user.id)
    return response_base.success(data=GetQuestionNoteDetail.model_validate(note))


@router.put('/{pk}', summary='更新笔记')
async def update_note(
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='笔记 ID')],
    obj: UpdateQuestionNoteParam,
    request: Request, _token: str = DependsJwtAuth,
) -> ResponseModel:
    """更新笔记内容和公开状态（支持局部更新）"""
    count = await note_service.update_note(
        db=db, note_id=pk, user_id=request.user.id, obj=obj
    )

    if count > 0:
        return response_base.success()
    return response_base.fail(res=CustomResponse(code=400, msg='没有需要更新的数据'))


@router.delete('/{pk}', summary='删除笔记')
async def delete_note(
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='笔记 ID')],
    request: Request, _token: str = DependsJwtAuth,
) -> ResponseModel:
    """删除笔记"""
    count = await note_service.delete_note(db=db, note_id=pk, user_id=request.user.id)

    if count > 0:
        return response_base.success()
    return response_base.fail(res=CustomResponse(code=400, msg='删除失败'))


# ============ 笔记投票接口 ============


@router.post('/{pk}/vote', summary='投票笔记')
async def vote_note(
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='笔记 ID')],
    obj: VoteQuestionNoteParam,
    request: Request, _token: str = DependsJwtAuth,
) -> ResponseModel:
    """对笔记投票（点赞/点踩）"""
    await note_service.vote_note(db=db, note_id=pk, user_id=request.user.id, vote_value=obj.vote_value)
    return response_base.success()


@router.delete('/{pk}/vote', summary='取消投票')
async def cancel_vote(
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='笔记 ID')],
    request: Request, _token: str = DependsJwtAuth,
) -> ResponseModel:
    """取消对笔记的投票"""
    count = await note_service.cancel_vote(db=db, note_id=pk, user_id=request.user.id)

    if count > 0:
        return response_base.success()
    return response_base.fail(res=CustomResponse(code=400, msg='您还未对此笔记投票'))


@router.get('/{pk}/vote/my', summary='获取我的投票')
async def get_my_vote(
    db: CurrentSession,
    pk: Annotated[int, Path(description='笔记 ID')],
    request: Request, _token: str = DependsJwtAuth,
) -> ResponseSchemaModel[GetUserNoteVoteDetail]:
    """获取当前用户对笔记的投票状态"""
    vote = await note_service.get_my_vote(db=db, note_id=pk, user_id=request.user.id)
    return response_base.success(data=GetUserNoteVoteDetail.model_validate(vote))


@router.get('/{pk}/vote/statistics', summary='获取笔记投票统计')
async def get_vote_statistics(
    db: CurrentSession, pk: Annotated[int, Path(description='笔记 ID')]
) -> ResponseSchemaModel[NoteVoteStatistics]:
    """获取笔记的投票统计数据"""
    stats = await note_service.get_vote_statistics(db=db, note_id=pk)
    return response_base.success(data=stats)



