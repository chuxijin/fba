#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
收藏接口

设计原则：
- 支持收藏夹分组（类似 LeetCode）
- 支持自定义标签
- 支持置顶功能
"""
from typing import Annotated

from fastapi import APIRouter, Body, Path, Query

from backend.app.question_bank.schema.favorite import (
    ClearFolderParam,
    CreateQuestionFavoriteParam,
    FavoriteStatistics,
    GetQuestionFavoriteDetail,
    GetQuestionFavoriteListItem,
    UpdateQuestionFavoriteParam,
)
from backend.app.question_bank.security import DependsCurrentUser
from backend.app.question_bank.service.favorite_service import favorite_service
from backend.common.pagination import DependsPagination, PageData, paging_data
from backend.common.response.response_code import CustomResponse
from backend.common.response.response_schema import ResponseModel, ResponseSchemaModel, response_base
from backend.common.security.auth_strategy import AuthUser
from backend.database.db import CurrentSession, CurrentSessionTransaction
from backend.app.question_bank.crud.crud_question_favorite import question_favorite_dao

router = APIRouter()


# ============ 收藏管理接口 ============
# 重要：具体路径的路由必须放在通配路由（/{pk}）之前，否则会被通配路由拦截


@router.post('', summary='收藏题目', name='qbank_favorite_create')
async def create_favorite(
    db: CurrentSessionTransaction,
    obj: CreateQuestionFavoriteParam,
    current_user: AuthUser = DependsCurrentUser,
) -> ResponseSchemaModel[GetQuestionFavoriteDetail]:
    """收藏题目"""
    new_favorite = await favorite_service.create_favorite(db=db, user_id=current_user.user_id, obj=obj)
    return response_base.success(data=GetQuestionFavoriteDetail.model_validate(new_favorite))


@router.get('', summary='获取收藏列表', name='qbank_favorite_get_list', dependencies=[DependsPagination])
async def get_favorites(
    db: CurrentSession,
    current_user: AuthUser = DependsCurrentUser,
    folder_name: Annotated[str | None, Query(description='收藏夹名称')] = None,
    is_pinned: Annotated[bool | None, Query(description='是否置顶')] = None,
) -> ResponseSchemaModel[PageData[GetQuestionFavoriteListItem]]:
    """获取用户的收藏列表（分页）"""
    stmt = await question_favorite_dao.get_select(
        user_id=current_user.user_id, folder_name=folder_name, is_pinned=is_pinned
    )
    page_data = await paging_data(db, stmt, GetQuestionFavoriteListItem)
    return response_base.success(data=page_data)


# ============ 收藏夹管理接口（具体路径，必须在 /{pk} 之前）============


@router.delete('/questions/{question_id}', summary='通过题目ID取消收藏', name='qbank_favorite_delete_by_question')
async def delete_favorite_by_question(
    db: CurrentSessionTransaction,
    question_id: Annotated[int, Path(description='题目 ID')],
    current_user: AuthUser = DependsCurrentUser,
) -> ResponseModel:
    """通过题目ID直接取消收藏"""
    count = await favorite_service.delete_favorite_by_question(
        db=db, user_id=current_user.user_id, question_id=question_id
    )

    if count > 0:
        return response_base.success(res=CustomResponse(code=200, msg='取消收藏成功'))
    return response_base.success(res=CustomResponse(code=200, msg='该题目未收藏或已取消'))


@router.get('/folders', summary='获取收藏夹列表', name='qbank_favorite_get_folders')
async def get_folders(
    db: CurrentSession, current_user: AuthUser = DependsCurrentUser
) -> ResponseSchemaModel[list[str]]:
    """获取用户的所有收藏夹名称"""
    folders = await question_favorite_dao.get_user_folders(db=db, user_id=current_user.user_id)
    return response_base.success(data=folders)


@router.post('/folders/clear', summary='清空收藏夹', name='qbank_favorite_clear_folder')
async def clear_folder(
    db: CurrentSessionTransaction,
    obj: ClearFolderParam,
    current_user: AuthUser = DependsCurrentUser,
) -> ResponseModel:
    """清空指定收藏夹"""
    count = await question_favorite_dao.clear_folder(db=db, user_id=current_user.user_id, folder_name=obj.folder_name)

    if count > 0:
        return response_base.success(res=CustomResponse(code=200, msg=f'成功清空收藏夹，删除 {count} 个收藏'))
    return response_base.success(res=CustomResponse(code=200, msg='收藏夹为空'))


# ============ 工具接口（具体路径，必须在 /{pk} 之前）============


@router.post('/questions/check', summary='检查题目收藏状态', name='qbank_favorite_check')
async def check_favorited(
    db: CurrentSession,
    question_ids: Annotated[list[int], Body(description='题目 ID 列表（可以是单个或多个）')],
    current_user: AuthUser = DependsCurrentUser,
) -> ResponseSchemaModel[dict[int, bool]]:
    """批量检查题目的收藏状态"""
    status_map = await favorite_service.check_favorited(
        db=db, user_id=current_user.user_id, question_ids=question_ids
    )

    return response_base.success(data=status_map)


@router.get('/statistics', summary='获取收藏统计', name='qbank_favorite_statistics')
async def get_statistics(
    db: CurrentSession, current_user: AuthUser = DependsCurrentUser
) -> ResponseSchemaModel[FavoriteStatistics]:
    """获取用户的收藏统计数据"""
    stats = await favorite_service.get_statistics(db=db, user_id=current_user.user_id)

    return response_base.success(data=stats)


# ============ 通配路径接口（必须放在最后）============


@router.get('/{pk}', summary='获取收藏详情', name='qbank_favorite_get')
async def get_favorite(
    db: CurrentSession,
    pk: Annotated[int, Path(description='收藏 ID')],
    current_user: AuthUser = DependsCurrentUser,
) -> ResponseSchemaModel[GetQuestionFavoriteDetail]:
    """获取收藏详情"""
    favorite = await favorite_service.get_favorite(db=db, favorite_id=pk, user_id=current_user.user_id)

    return response_base.success(data=GetQuestionFavoriteDetail.model_validate(favorite))


@router.put('/{pk}', summary='更新收藏', name='qbank_favorite_update')
async def update_favorite(
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='收藏 ID')],
    obj: UpdateQuestionFavoriteParam,
    current_user: AuthUser = DependsCurrentUser,
) -> ResponseModel:
    """更新收藏信息"""
    count = await favorite_service.update_favorite(
        db=db,
        favorite_id=pk,
        user_id=current_user.user_id,
        folder_name=obj.folder_name,
        tags=obj.tags,
        remark=obj.remark,
    )

    if count > 0:
        return response_base.success()
    return response_base.fail(res=CustomResponse(code=400, msg='没有需要更新的数据'))


@router.put('/{pk}/pin', summary='设置收藏置顶', name='qbank_favorite_set_pin')
async def set_pin(
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='收藏 ID')],
    is_pinned: Annotated[bool, Body(embed=True, description='是否置顶')],
    current_user: AuthUser = DependsCurrentUser,
) -> ResponseModel:
    """设置收藏置顶或取消置顶"""
    count = await favorite_service.set_pin(
        db=db, favorite_id=pk, user_id=current_user.user_id, is_pinned=is_pinned
    )

    if count > 0:
        return response_base.success()
    return response_base.fail(res=CustomResponse(code=400, msg='设置失败'))


@router.delete('', summary='取消收藏', name='qbank_favorite_delete')
async def delete_favorites(
    db: CurrentSessionTransaction,
    favorite_ids: Annotated[list[int], Body(description='收藏 ID 列表（支持单个或批量）')],
    current_user: AuthUser = DependsCurrentUser,
) -> ResponseModel:
    """取消收藏题目（支持单个和批量）"""
    count = await favorite_service.delete_favorites(
        db=db, favorite_ids=favorite_ids, user_id=current_user.user_id
    )

    if count > 0:
        return response_base.success(res=CustomResponse(code=200, msg=f'成功取消 {count} 个收藏'))
    return response_base.fail(res=CustomResponse(code=400, msg='取消收藏失败'))

