#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Annotated

from fastapi import APIRouter, Path, Query, Request

from backend.app.mydrive.schema.file import (
    CreateMyDriveDirectoryParam,
    CreateMyDriveShareParam,
    CancelMyDriveSharesParam,
    GetMyDriveFileDetail,
    GetMyDriveFileList,
    GetMyDriveShareDetail,
    GetMyDriveShareList,
    OperateMyDriveFilesParam,
    RenameMyDriveFileParam,
    SaveMyDriveShareFilesParam,
    TransferMyDriveFilesParam,
)
from backend.app.mydrive.schema.space import (
    CreateMyDriveSpaceParam,
    GetMyDriveSpaceDetail,
    PreviewMyDriveSpaceParam,
    UpdateMyDriveSpaceParam,
)
from backend.app.mydrive.service.space_service import mydrive_space_service
from backend.common.pagination import DependsPagination, PageData, paging_data
from backend.common.response.response_schema import ResponseModel, ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.database.db import CurrentSession, CurrentSessionTransaction

router = APIRouter()


@router.post('/preview', summary='预览待挂载文件空间', dependencies=[DependsJwtAuth])
async def preview_mydrive_space(
    request: Request,
    db: CurrentSession,
    obj: PreviewMyDriveSpaceParam,
) -> ResponseSchemaModel[GetMyDriveFileList]:
    """预览尚未创建的文件空间目录。"""
    file_list = await mydrive_space_service.preview_files(db, owner_id=request.user.id, obj=obj)
    return response_base.success(data=file_list)


@router.get('', summary='分页获取文件空间', dependencies=[DependsJwtAuth, DependsPagination])
async def get_mydrive_spaces(
    request: Request,
    db: CurrentSession,
    space_type: Annotated[str | None, Query(description='文件空间类型')] = None,
) -> ResponseSchemaModel[PageData[GetMyDriveSpaceDetail]]:
    """分页获取当前用户的文件空间。"""
    stmt = await mydrive_space_service.get_select(owner_id=request.user.id, space_type=space_type)
    return response_base.success(data=await paging_data(db, stmt))


@router.get('/{pk}', summary='获取文件空间详情', dependencies=[DependsJwtAuth])
async def get_mydrive_space(
    request: Request,
    db: CurrentSession,
    pk: Annotated[int, Path(description='文件空间 ID')],
) -> ResponseSchemaModel[GetMyDriveSpaceDetail]:
    """获取当前用户的文件空间详情。"""
    space = await mydrive_space_service.get(db, pk=pk, owner_id=request.user.id)
    return response_base.success(data=space)


@router.get('/{pk}/list', summary='浏览文件空间', dependencies=[DependsJwtAuth])
async def get_mydrive_space_files(
    request: Request,
    db: CurrentSession,
    pk: Annotated[int, Path(description='文件空间 ID')],
    path: Annotated[str, Query(description='挂载内目录路径')] = '/',
    file_id: Annotated[str | None, Query(description='目录 ID')] = None,
    page: Annotated[int, Query(ge=1, description='页码')] = 1,
    per_page: Annotated[int, Query(ge=1, le=200, description='每页文件数')] = 200,
    refresh: Annotated[bool, Query(description='是否绕过目录缓存')] = False,
) -> ResponseSchemaModel[GetMyDriveFileList]:
    """按 OpenList 风格浏览当前用户的文件空间。"""
    file_list = await mydrive_space_service.list_files(
        db,
        pk=pk,
        owner_id=request.user.id,
        path=path,
        file_id=file_id,
        page=page,
        per_page=per_page,
        refresh=refresh,
    )
    return response_base.success(data=file_list)


@router.get('/{pk}/search', summary='搜索文件空间', dependencies=[DependsJwtAuth])
async def search_mydrive_space_files(
    request: Request,
    db: CurrentSession,
    pk: Annotated[int, Path(description='文件空间 ID')],
    keyword: Annotated[str, Query(min_length=1, description='搜索关键词')],
    path: Annotated[str, Query(description='挂载内搜索目录路径')] = '/',
    recursive: Annotated[bool, Query(description='是否递归搜索')] = False,
    page: Annotated[int, Query(ge=1, description='页码')] = 1,
    per_page: Annotated[int, Query(ge=1, le=200, description='每页文件数')] = 200,
) -> ResponseSchemaModel[GetMyDriveFileList]:
    """搜索当前用户的文件空间。"""
    file_list = await mydrive_space_service.search_files(
        db,
        pk=pk,
        owner_id=request.user.id,
        keyword=keyword,
        path=path,
        recursive=recursive,
        page=page,
        per_page=per_page,
    )
    return response_base.success(data=file_list)


@router.post('/{pk}/mkdir', summary='创建目录', dependencies=[DependsJwtAuth])
async def create_mydrive_directory(
    request: Request,
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='文件空间 ID')],
    obj: CreateMyDriveDirectoryParam,
) -> ResponseSchemaModel[GetMyDriveFileDetail]:
    """在个人文件空间创建目录。"""
    directory = await mydrive_space_service.make_directory(
        db,
        pk=pk,
        owner_id=request.user.id,
        name=obj.name,
        parent=obj.parent,
    )
    return response_base.success(data=directory)


@router.post('/{pk}/copy', summary='复制文件', dependencies=[DependsJwtAuth])
async def copy_mydrive_files(
    request: Request,
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='文件空间 ID')],
    obj: OperateMyDriveFilesParam,
) -> ResponseModel:
    """在个人文件空间复制文件。"""
    await mydrive_space_service.copy_files(db, pk=pk, owner_id=request.user.id, files=obj.files, target=obj.target)
    return response_base.success()


@router.post('/{pk}/move', summary='移动文件', dependencies=[DependsJwtAuth])
async def move_mydrive_files(
    request: Request,
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='文件空间 ID')],
    obj: OperateMyDriveFilesParam,
) -> ResponseModel:
    """在个人文件空间移动文件。"""
    await mydrive_space_service.move_files(db, pk=pk, owner_id=request.user.id, files=obj.files, target=obj.target)
    return response_base.success()


@router.post('/{pk}/rename', summary='重命名文件', dependencies=[DependsJwtAuth])
async def rename_mydrive_file(
    request: Request,
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='文件空间 ID')],
    obj: RenameMyDriveFileParam,
) -> ResponseSchemaModel[GetMyDriveFileDetail]:
    """重命名个人文件空间文件。"""
    file = await mydrive_space_service.rename_file(
        db,
        pk=pk,
        owner_id=request.user.id,
        file=obj.file,
        name=obj.name,
    )
    return response_base.success(data=file)


@router.post('/{pk}/remove', summary='删除文件', dependencies=[DependsJwtAuth])
async def remove_mydrive_files(
    request: Request,
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='文件空间 ID')],
    obj: OperateMyDriveFilesParam,
) -> ResponseModel:
    """删除个人文件空间文件。"""
    await mydrive_space_service.remove_files(db, pk=pk, owner_id=request.user.id, files=obj.files)
    return response_base.success()


@router.post('/{pk}/transfer', summary='转存外部文件', dependencies=[DependsJwtAuth])
async def transfer_mydrive_files(
    request: Request,
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='源文件空间 ID')],
    obj: TransferMyDriveFilesParam,
) -> ResponseSchemaModel[list[GetMyDriveFileDetail]]:
    """将分享或群组空间文件转存到个人文件空间。"""
    files = await mydrive_space_service.transfer_files(
        db,
        pk=pk,
        owner_id=request.user.id,
        files=obj.files,
        target_space_id=obj.target_space_id,
    )
    return response_base.success(data=files)


@router.post('/{pk}/save-share', summary='保存分享文件', dependencies=[DependsJwtAuth])
async def save_mydrive_share_files(
    request: Request,
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='目标个人文件空间 ID')],
    obj: SaveMyDriveShareFilesParam,
) -> ResponseSchemaModel[list[GetMyDriveFileDetail]]:
    """将分享文件保存到当前个人文件空间。"""
    files = await mydrive_space_service.save_share_files(
        db,
        owner_id=request.user.id,
        target_space_id=pk,
        account_id=obj.account_id,
        provider=obj.provider,
        source_key=obj.source_key,
        source_ref=obj.source_ref,
        root_id=obj.root_id,
        root_path=obj.root_path,
        files=obj.files,
        target=obj.target,
    )
    return response_base.success(data=files)


@router.post('/{pk}/share', summary='创建分享链接', dependencies=[DependsJwtAuth])
async def create_mydrive_share(
    request: Request,
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='文件空间 ID')],
    obj: CreateMyDriveShareParam,
) -> ResponseSchemaModel[GetMyDriveShareDetail]:
    """为个人文件空间中的文件创建分享链接。"""
    share_link = await mydrive_space_service.create_share(
        db,
        pk=pk,
        owner_id=request.user.id,
        files=obj.files,
        title=obj.title,
        expires_in_days=obj.expires_in_days,
        password=obj.password,
    )
    return response_base.success(data=share_link)


@router.get('/{pk}/shares', summary='获取我的分享', dependencies=[DependsJwtAuth])
async def get_mydrive_shares(
    request: Request,
    db: CurrentSession,
    pk: Annotated[int, Path(description='文件空间 ID')],
    page: Annotated[int, Query(ge=1, description='页码')] = 1,
    per_page: Annotated[int, Query(ge=1, le=100, description='每页分享数')] = 20,
) -> ResponseSchemaModel[GetMyDriveShareList]:
    """获取当前个人文件空间创建的分享链接。"""
    shares = await mydrive_space_service.list_shares(
        db, pk=pk, owner_id=request.user.id, page=page, per_page=per_page
    )
    return response_base.success(data=shares)


@router.get('/{pk}/shares/{share_id}', summary='获取分享详情', dependencies=[DependsJwtAuth])
async def get_mydrive_share(
    request: Request,
    db: CurrentSession,
    pk: Annotated[int, Path(description='文件空间 ID')],
    share_id: Annotated[str, Path(description='分享 ID')],
) -> ResponseSchemaModel[GetMyDriveShareDetail]:
    """获取当前个人文件空间中的分享详情。"""
    share = await mydrive_space_service.get_share(db, pk=pk, owner_id=request.user.id, share_id=share_id)
    return response_base.success(data=share)


@router.post('/{pk}/shares/cancel', summary='取消分享链接', dependencies=[DependsJwtAuth])
async def cancel_mydrive_shares(
    request: Request,
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='文件空间 ID')],
    obj: CancelMyDriveSharesParam,
) -> ResponseModel:
    """批量取消当前个人文件空间中的分享链接。"""
    await mydrive_space_service.cancel_shares(db, pk=pk, owner_id=request.user.id, share_ids=obj.share_ids)
    return response_base.success()


@router.post('', summary='创建文件空间', dependencies=[DependsJwtAuth])
async def create_mydrive_space(
    request: Request,
    db: CurrentSessionTransaction,
    obj: CreateMyDriveSpaceParam,
) -> ResponseSchemaModel[GetMyDriveSpaceDetail]:
    """创建当前用户的文件空间。"""
    space = await mydrive_space_service.create(db, owner_id=request.user.id, obj=obj)
    return response_base.success(data=space)


@router.put('/{pk}', summary='更新文件空间', dependencies=[DependsJwtAuth])
async def update_mydrive_space(
    request: Request,
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='文件空间 ID')],
    obj: UpdateMyDriveSpaceParam,
) -> ResponseModel:
    """更新当前用户的文件空间。"""
    await mydrive_space_service.update(db, pk=pk, owner_id=request.user.id, obj=obj)
    return response_base.success()


@router.delete('/{pk}', summary='删除文件空间', dependencies=[DependsJwtAuth])
async def delete_mydrive_space(
    request: Request,
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='文件空间 ID')],
) -> ResponseModel:
    """删除当前用户的文件空间。"""
    await mydrive_space_service.delete(db, pk=pk, owner_id=request.user.id)
    return response_base.success()
