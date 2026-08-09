from typing import Annotated, Literal

from fastapi import APIRouter, Path, Query, Request

from backend.app.question_bank_v2.schema.user_content import (
    CreateFavoriteFolderParam,
    CreateQuestionFavoriteParam,
    CreateQuestionNoteParam,
    FavoriteStatistics,
    GetFavoriteFolderDetail,
    GetQuestionFavoriteDetail,
    GetQuestionNoteDetail,
    NoteStatistics,
    QuestionNoteVoteParam,
    UpdateFavoriteFolderParam,
    UpdateQuestionFavoriteParam,
    UpdateQuestionNoteParam,
)
from backend.app.question_bank_v2.service.user_content_service import user_content_service
from backend.common.pagination import CursorPageData, DependsCursorPagination, cursor_paging_data
from backend.common.response.response_schema import ResponseModel, ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.database.db import CurrentSession, CurrentSessionTransaction

router = APIRouter(dependencies=[DependsJwtAuth])


@router.get('/favorites/folders', summary='获取收藏夹列表', name='qbank_v2_get_favorite_folders')
async def get_favorite_folders(
    request: Request,
    db: CurrentSession,
) -> ResponseSchemaModel[list[GetFavoriteFolderDetail]]:
    """获取当前用户收藏夹及其收藏数量"""
    data = await user_content_service.get_folders(db=db, user_id=request.user.id)
    return response_base.success(data=data)


@router.post('/favorites/folders', summary='创建收藏夹', name='qbank_v2_create_favorite_folder')
async def create_favorite_folder(
    request: Request,
    db: CurrentSessionTransaction,
    obj: CreateFavoriteFolderParam,
) -> ResponseSchemaModel[GetFavoriteFolderDetail]:
    """创建名称在当前用户内唯一的收藏夹"""
    data = await user_content_service.create_folder(db=db, user_id=request.user.id, obj=obj)
    return response_base.success(data=data)


@router.put('/favorites/folders/{folder_id}', summary='更新收藏夹', name='qbank_v2_update_favorite_folder')
async def update_favorite_folder(
    request: Request,
    db: CurrentSessionTransaction,
    folder_id: Annotated[int, Path(gt=0, description='收藏夹 ID')],
    obj: UpdateFavoriteFolderParam,
) -> ResponseSchemaModel[GetFavoriteFolderDetail]:
    """更新收藏夹名称、说明、排序或状态"""
    data = await user_content_service.update_folder(
        db=db,
        user_id=request.user.id,
        folder_id=folder_id,
        obj=obj,
    )
    return response_base.success(data=data)


@router.delete('/favorites/folders/{folder_id}', summary='删除收藏夹', name='qbank_v2_delete_favorite_folder')
async def delete_favorite_folder(
    request: Request,
    db: CurrentSessionTransaction,
    folder_id: Annotated[int, Path(gt=0, description='收藏夹 ID')],
) -> ResponseModel:
    """幂等删除收藏夹并将其中收藏移到未分组"""
    await user_content_service.delete_folder(db=db, user_id=request.user.id, folder_id=folder_id)
    return response_base.success()


@router.get('/favorites/statistics', summary='获取收藏统计', name='qbank_v2_get_favorite_statistics')
async def get_favorite_statistics(
    request: Request,
    db: CurrentSession,
    group_by: Annotated[Literal['bank', 'knowledge_point'], Query(description='分组方式')] = 'bank',
    knowledge_system_id: Annotated[
        int | None, Query(gt=0, description='知识体系 ID；不传按科目偏好回落 default')
    ] = None,
    domain_category_id: Annotated[int | None, Query(gt=0, description='领域分类 ID；不传取用户当前领域')] = None,
) -> ResponseSchemaModel[FavoriteStatistics]:
    """获取收藏总数、收藏夹数及分组数据"""
    data = await user_content_service.get_favorite_statistics(
        db=db,
        user_id=request.user.id,
        group_by=group_by,
        knowledge_system_id=knowledge_system_id,
        domain_category_id=domain_category_id,
    )
    return response_base.success(data=data)


@router.get(
    '/favorites',
    summary='获取收藏列表',
    name='qbank_v2_get_favorites',
    dependencies=[DependsCursorPagination],
)
async def get_favorites(
    request: Request,
    db: CurrentSession,
    folder_id: Annotated[int | None, Query(gt=0, description='收藏夹 ID')] = None,
) -> ResponseSchemaModel[CursorPageData[GetQuestionFavoriteDetail]]:
    """按置顶和收藏时间获取当前用户收藏"""
    stmt = await user_content_service.get_favorites_select(
        db=db,
        user_id=request.user.id,
        folder_id=folder_id,
    )
    return response_base.success(data=await cursor_paging_data(db, stmt, GetQuestionFavoriteDetail))


@router.post('/favorites', summary='收藏题目', name='qbank_v2_create_favorite')
async def create_favorite(
    request: Request,
    db: CurrentSessionTransaction,
    obj: CreateQuestionFavoriteParam,
) -> ResponseSchemaModel[GetQuestionFavoriteDetail]:
    """幂等收藏稳定题目并保存版本和题库上下文"""
    data = await user_content_service.create_favorite(db=db, user_id=request.user.id, obj=obj)
    return response_base.success(data=data)


@router.put('/favorites/{favorite_id}', summary='更新收藏', name='qbank_v2_update_favorite')
async def update_favorite(
    request: Request,
    db: CurrentSessionTransaction,
    favorite_id: Annotated[int, Path(gt=0, description='收藏 ID')],
    obj: UpdateQuestionFavoriteParam,
) -> ResponseSchemaModel[GetQuestionFavoriteDetail]:
    """更新收藏夹归属、标签、备注或置顶状态"""
    data = await user_content_service.update_favorite(
        db=db,
        user_id=request.user.id,
        favorite_id=favorite_id,
        obj=obj,
    )
    return response_base.success(data=data)


@router.delete(
    '/favorites/by-question/{question_id}',
    summary='按题目取消收藏',
    name='qbank_v2_delete_favorite_by_question',
)
async def delete_favorite_by_question(
    request: Request,
    db: CurrentSessionTransaction,
    question_id: Annotated[int, Path(gt=0, description='稳定题目 ID')],
) -> ResponseModel:
    """幂等取消当前用户对稳定题目的收藏"""
    await user_content_service.delete_favorite_by_question(
        db=db,
        user_id=request.user.id,
        question_id=question_id,
    )
    return response_base.success()


@router.get(
    '/sessions/{session_key}/favorites',
    summary='获取会话收藏状态',
    name='qbank_v2_get_session_favorites',
)
async def get_session_favorites(
    request: Request,
    db: CurrentSession,
    session_key: Annotated[str, Path(min_length=8, max_length=64, description='会话标识')],
) -> ResponseSchemaModel[dict[int, bool]]:
    """一次查询返回会话内已收藏题目，未收藏题目不占响应体"""
    data = await user_content_service.get_session_favorites(
        db=db,
        user_id=request.user.id,
        session_key=session_key,
    )
    return response_base.success(data=data)


@router.get('/notes/statistics', summary='获取笔记统计', name='qbank_v2_get_note_statistics')
async def get_note_statistics(
    request: Request,
    db: CurrentSession,
    group_by: Annotated[Literal['bank', 'knowledge_point'], Query(description='分组方式')] = 'bank',
    knowledge_system_id: Annotated[
        int | None, Query(gt=0, description='知识体系 ID；不传按科目偏好回落 default')
    ] = None,
    domain_category_id: Annotated[int | None, Query(gt=0, description='领域分类 ID；不传取用户当前领域')] = None,
) -> ResponseSchemaModel[NoteStatistics]:
    """获取笔记总数、公开数、精选数及分组数据"""
    data = await user_content_service.get_note_statistics(
        db=db,
        user_id=request.user.id,
        group_by=group_by,
        knowledge_system_id=knowledge_system_id,
        domain_category_id=domain_category_id,
    )
    return response_base.success(data=data)


@router.get(
    '/notes/questions/{question_id}/public',
    summary='获取题目公开笔记',
    name='qbank_v2_get_public_question_notes',
    dependencies=[DependsCursorPagination],
)
async def get_public_question_notes(
    request: Request,
    db: CurrentSession,
    question_id: Annotated[int, Path(gt=0, description='稳定题目 ID')],
) -> ResponseSchemaModel[CursorPageData[GetQuestionNoteDetail]]:
    """按精选和点赞数获取题目公开笔记"""
    stmt = user_content_service.get_public_notes_select(
        user_id=request.user.id,
        question_id=question_id,
    )
    return response_base.success(
        data=await cursor_paging_data(
            db,
            stmt,
            item_transform=user_content_service.build_note_page,
        )
    )


@router.get(
    '/notes',
    summary='获取我的笔记列表',
    name='qbank_v2_get_notes',
    dependencies=[DependsCursorPagination],
)
async def get_notes(
    request: Request,
    db: CurrentSession,
) -> ResponseSchemaModel[CursorPageData[GetQuestionNoteDetail]]:
    """按更新时间获取当前用户题目笔记"""
    stmt = user_content_service.get_notes_select(user_id=request.user.id)
    return response_base.success(
        data=await cursor_paging_data(
            db,
            stmt,
            item_transform=user_content_service.build_note_page,
        )
    )


@router.post('/notes', summary='创建题目笔记', name='qbank_v2_create_note')
async def create_note(
    request: Request,
    db: CurrentSessionTransaction,
    obj: CreateQuestionNoteParam,
) -> ResponseSchemaModel[GetQuestionNoteDetail]:
    """为稳定题目创建当前用户唯一笔记"""
    data = await user_content_service.create_note(db=db, user_id=request.user.id, obj=obj)
    return response_base.success(data=data)


@router.put('/notes/{note_id}', summary='更新题目笔记', name='qbank_v2_update_note')
async def update_note(
    request: Request,
    db: CurrentSessionTransaction,
    note_id: Annotated[int, Path(gt=0, description='笔记 ID')],
    obj: UpdateQuestionNoteParam,
) -> ResponseSchemaModel[GetQuestionNoteDetail]:
    """更新当前用户笔记正文、格式或公开状态"""
    data = await user_content_service.update_note(
        db=db,
        user_id=request.user.id,
        note_id=note_id,
        obj=obj,
    )
    return response_base.success(data=data)


@router.delete('/notes/{note_id}', summary='删除题目笔记', name='qbank_v2_delete_note')
async def delete_note(
    request: Request,
    db: CurrentSessionTransaction,
    note_id: Annotated[int, Path(gt=0, description='笔记 ID')],
) -> ResponseModel:
    """幂等删除当前用户题目笔记"""
    await user_content_service.delete_note(db=db, user_id=request.user.id, note_id=note_id)
    return response_base.success()


@router.put('/notes/{note_id}/vote', summary='投票公开笔记', name='qbank_v2_vote_note')
async def vote_note(
    request: Request,
    db: CurrentSessionTransaction,
    note_id: Annotated[int, Path(gt=0, description='笔记 ID')],
    obj: QuestionNoteVoteParam,
) -> ResponseSchemaModel[GetQuestionNoteDetail]:
    """点赞、点踩或取消对他人公开笔记的投票"""
    data = await user_content_service.vote_note(
        db=db,
        user_id=request.user.id,
        note_id=note_id,
        obj=obj,
    )
    return response_base.success(data=data)


@router.get('/sessions/{session_key}/notes', summary='获取会话个人笔记', name='qbank_v2_get_session_notes')
async def get_session_notes(
    request: Request,
    db: CurrentSession,
    session_key: Annotated[str, Path(min_length=8, max_length=64, description='会话标识')],
) -> ResponseSchemaModel[dict[int, GetQuestionNoteDetail]]:
    """一次查询返回会话内当前用户已有笔记"""
    data = await user_content_service.get_session_notes(
        db=db,
        user_id=request.user.id,
        session_key=session_key,
    )
    return response_base.success(data=data)
