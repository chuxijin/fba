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

from backend.app.question_bank.crud.crud_question_note import question_note_dao, user_note_vote_dao
from backend.app.question_bank.schema.note import (
    CreateQuestionNoteParam,
    GetQuestionNoteDetail,
    GetQuestionNoteListItem,
    GetUserNoteVoteDetail,
    NoteVoteStatistics,
    SetNoteFeaturedParam,
    UpdateQuestionNoteParam,
    VoteQuestionNoteParam,
)
from backend.app.question_bank.security import DependsCustomerAuth
from backend.common.pagination import DependsPagination, PageData, paging_data
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
    """
    创建题目笔记

    用户可选择公开或私密
    """
    note_dict = obj.model_dump()
    note_dict['user_id'] = current_user.user_id

    new_note = await question_note_dao.create(db=db, obj_dict=note_dict)
    return response_base.success(data=GetQuestionNoteDetail.model_validate(new_note))


@router.get('/{pk}', summary='获取笔记详情')
async def get_note(
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='笔记 ID')],
    current_user: AuthUser = DependsCustomerAuth,
) -> ResponseSchemaModel[GetQuestionNoteDetail]:
    """
    获取笔记详情

    如果是公开笔记，会自动增加浏览次数
    """
    note = await question_note_dao.get(db=db, note_id=pk)
    if not note:
        return response_base.fail(msg='笔记不存在')

    # 私密笔记只能作者查看
    if not note.is_public and note.user_id != current_user.user_id:
        return response_base.fail(msg='无权访问此笔记')

    # 公开笔记增加浏览次数
    if note.is_public and note.user_id != current_user.user_id:
        await question_note_dao.increment_view(db=db, note_id=pk)

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
    """
    获取笔记列表（分页）

    支持按题目、公开状态、精选状态筛选
    my_notes=true 时只返回当前用户的笔记
    """
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
    """
    获取题目的所有公开笔记（按质量分排序）

    用于在做题时查看其他用户的笔记
    """
    notes = await question_note_dao.get_public_notes(db=db, question_id=question_id, is_featured=is_featured)
    return response_base.success(data=[GetQuestionNoteListItem.model_validate(n) for n in notes])


@router.put('/{pk}', summary='更新笔记')
async def update_note(
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='笔记 ID')],
    obj: UpdateQuestionNoteParam,
    current_user: AuthUser = DependsCustomerAuth,
) -> ResponseModel:
    """更新笔记内容和公开状态"""
    note = await question_note_dao.get(db=db, note_id=pk)
    if not note:
        return response_base.fail(msg='笔记不存在')
    if note.user_id != current_user.user_id:
        return response_base.fail(msg='无权操作此笔记')

    count = await question_note_dao.update(db=db, note_id=pk, content=obj.content, is_public=obj.is_public)
    if count > 0:
        return response_base.success()
    return response_base.fail()


@router.delete('/{pk}', summary='删除笔记')
async def delete_note(
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='笔记 ID')],
    current_user: AuthUser = DependsCustomerAuth,
) -> ResponseModel:
    """删除笔记"""
    note = await question_note_dao.get(db=db, note_id=pk)
    if not note:
        return response_base.fail(msg='笔记不存在')
    if note.user_id != current_user.user_id:
        return response_base.fail(msg='无权操作此笔记')

    count = await question_note_dao.delete(db=db, note_id=pk)
    if count > 0:
        return response_base.success()
    return response_base.fail()


# ============ 笔记投票接口 ============


@router.post('/{pk}/vote', summary='投票笔记')
async def vote_note(
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='笔记 ID')],
    vote_value: Annotated[int, Body(embed=True, description='投票值：1=点赞，-1=点踩')],
    current_user: AuthUser = DependsCustomerAuth,
) -> ResponseModel:
    """
    对笔记投票（点赞/点踩）

    可以切换投票（点赞→点踩，点踩→点赞）
    """
    note = await question_note_dao.get(db=db, note_id=pk)
    if not note:
        return response_base.fail(msg='笔记不存在')
    if not note.is_public:
        return response_base.fail(msg='不能对私密笔记投票')
    if note.user_id == current_user.user_id:
        return response_base.fail(msg='不能给自己的笔记投票')

    if vote_value not in [1, -1]:
        return response_base.fail(msg='投票值必须是 1（点赞）或 -1（点踩）')

    # 投票
    await user_note_vote_dao.vote(db=db, user_id=current_user.user_id, note_id=pk, vote_value=vote_value)

    # 更新笔记的投票统计
    like_count, dislike_count = await user_note_vote_dao.get_note_vote_stats(db=db, note_id=pk)
    await question_note_dao.update_vote_stats(db=db, note_id=pk, like_count=like_count, dislike_count=dislike_count)

    return response_base.success()


@router.delete('/{pk}/vote', summary='取消投票')
async def cancel_vote(
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='笔记 ID')],
    current_user: AuthUser = DependsCustomerAuth,
) -> ResponseModel:
    """取消对笔记的投票"""
    # 取消投票
    count = await user_note_vote_dao.cancel_vote(db=db, user_id=current_user.user_id, note_id=pk)

    if count > 0:
        # 更新笔记的投票统计
        like_count, dislike_count = await user_note_vote_dao.get_note_vote_stats(db=db, note_id=pk)
        await question_note_dao.update_vote_stats(db=db, note_id=pk, like_count=like_count, dislike_count=dislike_count)
        return response_base.success()

    return response_base.fail(msg='您还未对此笔记投票')


@router.get('/{pk}/vote/my', summary='获取我的投票')
async def get_my_vote(
    db: CurrentSession,
    pk: Annotated[int, Path(description='笔记 ID')],
    current_user: AuthUser = DependsCustomerAuth,
) -> ResponseSchemaModel[GetUserNoteVoteDetail]:
    """获取当前用户对笔记的投票状态"""
    vote = await user_note_vote_dao.get_vote(db=db, user_id=current_user.user_id, note_id=pk)
    if not vote:
        return response_base.fail(msg='未对此笔记投票')

    return response_base.success(data=GetUserNoteVoteDetail.model_validate(vote))


@router.get('/{pk}/vote/statistics', summary='获取笔记投票统计')
async def get_vote_statistics(
    db: CurrentSession, pk: Annotated[int, Path(description='笔记 ID')]
) -> ResponseSchemaModel[NoteVoteStatistics]:
    """获取笔记的投票统计数据"""
    like_count, dislike_count = await user_note_vote_dao.get_note_vote_stats(db=db, note_id=pk)
    stats = NoteVoteStatistics(
        like_count=like_count, dislike_count=dislike_count, quality_score=like_count - dislike_count
    )
    return response_base.success(data=stats)


# ============ 管理员接口 ============


# @router.put('/{pk}/featured', summary='设置笔记精选（管理员）')
# async def set_featured(
#     db: CurrentSessionTransaction,
#     pk: Annotated[int, Path(description='笔记 ID')],
#     is_featured: Annotated[bool, Body(embed=True, description='是否精选')],
#     # current_user: AuthUser = DependsAdminAuth,  # TODO: 需要管理员权限
# ) -> ResponseModel:
#     """
#     设置笔记为精选（管理员功能）
#
#     管理员可标记优质笔记
#     """
#     count = await question_note_dao.set_featured(db=db, note_id=pk, is_featured=is_featured)
#     if count > 0:
#         return response_base.success()
#     return response_base.fail()
