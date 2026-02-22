#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Annotated

from fastapi import APIRouter, Path, Query, Request

from backend.app.jia.schema.doc import (
    CreateAssetParam,
    CreateDocParam,
    CreateFolderParam,
    DocAccessPasswordParam,
    GetAssetDetail,
    GetDocDetail,
    GetDocList,
    GetFolderDetail,
    GetFolderTree,
    MoveDocParam,
    UpdateAssetParam,
    UpdateDocParam,
    UpdateFolderParam,
)
from backend.app.jia.service.doc_service import asset_service, doc_service, folder_service
from backend.common.pagination import DependsPagination, PageData
from backend.common.response.response_schema import ResponseModel, ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.database.db import CurrentSession, CurrentSessionTransaction

router = APIRouter()


# ===================== Folder =====================


@router.get(
    '/folders/tree',
    summary='获取文件夹树',
    dependencies=[DependsJwtAuth],
)
async def jia_doc_get_folder_tree(
    request: Request,
    db: CurrentSession,
) -> ResponseSchemaModel[list[GetFolderTree]]:
    tree = await folder_service.get_tree(db=db, user_id=request.user.id)
    return response_base.success(data=tree)


@router.get(
    '/folders/{pk}',
    summary='获取文件夹详情',
    dependencies=[DependsJwtAuth],
)
async def jia_doc_get_folder(
    request: Request,
    db: CurrentSession,
    pk: Annotated[int, Path(description='文件夹 ID')],
) -> ResponseSchemaModel[GetFolderDetail]:
    folder = await folder_service.get(db=db, pk=pk, user_id=request.user.id)
    return response_base.success(data=folder)


@router.post(
    '/folders',
    summary='创建文件夹',
    dependencies=[DependsJwtAuth],
)
async def jia_doc_create_folder(
    request: Request,
    db: CurrentSessionTransaction,
    obj: CreateFolderParam,
) -> ResponseSchemaModel[GetFolderDetail]:
    folder = await folder_service.create(db=db, obj=obj, user_id=request.user.id)
    return response_base.success(data=folder)


@router.put(
    '/folders/{pk}',
    summary='更新文件夹',
    dependencies=[DependsJwtAuth],
)
async def jia_doc_update_folder(
    request: Request,
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='文件夹 ID')],
    obj: UpdateFolderParam,
) -> ResponseModel:
    count = await folder_service.update(db=db, pk=pk, obj=obj, user_id=request.user.id)
    if count > 0:
        return response_base.success()
    return response_base.fail()


@router.delete(
    '/folders/{pk}',
    summary='删除文件夹',
    dependencies=[DependsJwtAuth],
)
async def jia_doc_delete_folder(
    request: Request,
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='文件夹 ID')],
) -> ResponseModel:
    count = await folder_service.delete(db=db, pk=pk, user_id=request.user.id)
    if count > 0:
        return response_base.success()
    return response_base.fail()


# ===================== Doc =====================


@router.get(
    '',
    summary='获取文档列表',
    dependencies=[DependsJwtAuth, DependsPagination],
)
async def jia_doc_get_docs_paginated(
    request: Request,
    db: CurrentSession,
    folder_id: Annotated[int | None, Query(description='文件夹 ID')] = None,
    is_trashed: Annotated[bool, Query(description='是否回收站')] = False,
    is_pinned: Annotated[bool | None, Query(description='是否置顶')] = None,
    title: Annotated[str | None, Query(description='标题搜索')] = None,
) -> ResponseSchemaModel[PageData[GetDocList]]:
    page_data = await doc_service.get_list(
        db=db,
        user_id=request.user.id,
        folder_id=folder_id,
        is_trashed=is_trashed,
        is_pinned=is_pinned,
        title=title,
    )
    return response_base.success(data=page_data)


@router.put(
    '/move',
    summary='移动文档',
    dependencies=[DependsJwtAuth],
)
async def jia_doc_move(
    request: Request,
    db: CurrentSessionTransaction,
    obj: MoveDocParam,
) -> ResponseModel:
    count = await doc_service.move(
        db=db,
        doc_ids=obj.doc_ids,
        target_folder_id=obj.target_folder_id,
        user_id=request.user.id,
    )
    return response_base.success(data={'moved': count})


@router.get(
    '/{pk}',
    summary='获取文档详情',
    dependencies=[DependsJwtAuth],
)
async def jia_doc_get_doc(
    request: Request,
    db: CurrentSession,
    pk: Annotated[int, Path(description='文档 ID')],
) -> ResponseSchemaModel[GetDocDetail]:
    doc = await doc_service.get(db=db, pk=pk, user_id=request.user.id)
    return response_base.success(data=doc)


@router.post(
    '/{pk}/verify-access',
    summary='验证文档访问密码',
    dependencies=[DependsJwtAuth],
)
async def jia_doc_verify_access(
    request: Request,
    db: CurrentSession,
    pk: Annotated[int, Path(description='文档 ID')],
    obj: DocAccessPasswordParam,
) -> ResponseSchemaModel[GetDocDetail]:
    doc = await doc_service.verify_access(db=db, pk=pk, user_id=request.user.id, password=obj.password)
    return response_base.success(data=doc)


@router.post(
    '',
    summary='创建文档',
    dependencies=[DependsJwtAuth],
)
async def jia_doc_create_doc(
    request: Request,
    db: CurrentSessionTransaction,
    obj: CreateDocParam,
) -> ResponseSchemaModel[GetDocDetail]:
    doc = await doc_service.create(db=db, obj=obj, user_id=request.user.id)
    return response_base.success(data=doc)


@router.put(
    '/{pk}',
    summary='更新文档',
    dependencies=[DependsJwtAuth],
)
async def jia_doc_update_doc(
    request: Request,
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='文档 ID')],
    obj: UpdateDocParam,
) -> ResponseModel:
    count = await doc_service.update(db=db, pk=pk, obj=obj, user_id=request.user.id)
    if count > 0:
        return response_base.success()
    return response_base.fail()


@router.put(
    '/{pk}/trash',
    summary='移入回收站',
    dependencies=[DependsJwtAuth],
)
async def jia_doc_trash_doc(
    request: Request,
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='文档 ID')],
) -> ResponseModel:
    count = await doc_service.move_to_trash(db=db, pk=pk, user_id=request.user.id)
    if count > 0:
        return response_base.success()
    return response_base.fail()


@router.put(
    '/{pk}/restore',
    summary='从回收站恢复',
    dependencies=[DependsJwtAuth],
)
async def jia_doc_restore_doc(
    request: Request,
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='文档 ID')],
) -> ResponseModel:
    count = await doc_service.restore(db=db, pk=pk, user_id=request.user.id)
    if count > 0:
        return response_base.success()
    return response_base.fail()


@router.delete(
    '/{pk}',
    summary='永久删除文档',
    dependencies=[DependsJwtAuth],
)
async def jia_doc_delete_doc(
    request: Request,
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='文档 ID')],
) -> ResponseModel:
    count = await doc_service.delete(db=db, pk=pk, user_id=request.user.id)
    if count > 0:
        return response_base.success()
    return response_base.fail()


# ===================== Asset =====================


@router.get(
    '/assets',
    summary='获取资源列表',
    dependencies=[DependsJwtAuth, DependsPagination],
)
async def jia_doc_get_assets_paginated(
    request: Request,
    db: CurrentSession,
    doc_id: Annotated[int | None, Query(description='文档 ID')] = None,
) -> ResponseSchemaModel[PageData[GetAssetDetail]]:
    page_data = await asset_service.get_list(db=db, user_id=request.user.id, doc_id=doc_id)
    return response_base.success(data=page_data)


@router.post(
    '/assets',
    summary='创建资源记录',
    dependencies=[DependsJwtAuth],
)
async def jia_doc_create_asset(
    request: Request,
    db: CurrentSessionTransaction,
    obj: CreateAssetParam,
) -> ResponseSchemaModel[GetAssetDetail]:
    asset = await asset_service.create(db=db, obj=obj, user_id=request.user.id)
    return response_base.success(data=asset)


@router.put(
    '/assets/{pk}',
    summary='更新资源',
    dependencies=[DependsJwtAuth],
)
async def jia_doc_update_asset(
    request: Request,
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='资源 ID')],
    obj: UpdateAssetParam,
) -> ResponseModel:
    count = await asset_service.update(db=db, pk=pk, obj=obj, user_id=request.user.id)
    if count > 0:
        return response_base.success()
    return response_base.fail()


@router.delete(
    '/assets/{pk}',
    summary='删除资源',
    dependencies=[DependsJwtAuth],
)
async def jia_doc_delete_asset(
    request: Request,
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='资源 ID')],
) -> ResponseModel:
    count = await asset_service.delete(db=db, pk=pk, user_id=request.user.id)
    if count > 0:
        return response_base.success()
    return response_base.fail()
