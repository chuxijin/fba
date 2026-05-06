#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Annotated

from fastapi import APIRouter, Depends, File, Query, Request, UploadFile

from backend.app.admin.service.file_service import file_service
from backend.common.response.response_code import CustomResponse
from backend.common.response.response_schema import ResponseSchemaModel, response_base
from backend.common.security.permission import RequestPermission
from backend.common.security.rbac import DependsRBAC

router = APIRouter()


@router.post(
    '/upload',
    summary='本地文件上传',
    dependencies=[
        Depends(RequestPermission('sys:file:upload')),
        DependsRBAC,
    ],
)
async def upload_files(
    request: Request,
    file: Annotated[UploadFile, File()],
    folder: Annotated[str | None, Query()] = None,
) -> ResponseSchemaModel[dict]:
    """文件上传"""
    relative_path = await file_service.upload(file, folder=folder)
    
    # 相对路径 URL
    url = f'/static/upload/{relative_path}'
    
    # 获取文件详情
    from pathlib import Path

    from backend.core.path_conf import UPLOAD_DIR
    
    full_path_obj = UPLOAD_DIR / relative_path
    local_path = str(full_path_obj.resolve())
    size = full_path_obj.stat().st_size
    file_type = Path(relative_path).suffix.lstrip('.').lower()
    
    return response_base.success(data={
        'url': url,
        'local_path': local_path,
        'file_type': file_type,
        'size': size,
        'filename': Path(relative_path).name
    })


@router.get(
    '/list',
    summary='文件列表',
    dependencies=[
        Depends(RequestPermission('sys:file:list')),
        DependsRBAC,
    ],
)
async def list_uploaded_files(
    request: Request,
    page: Annotated[int, Query(ge=1)] = 1,
    size: Annotated[int, Query(ge=1, le=100)] = 20,
    keyword: Annotated[str | None, Query()] = None,
    file_type: Annotated[str | None, Query()] = None,
    folder: Annotated[str | None, Query()] = None,
) -> ResponseSchemaModel[dict]:
    """
    获取已上传的文件列表

    :param request: Request 对象
    :param page: 页码
    :param size: 每页数量
    :param keyword: 搜索关键词
    :param file_type: 文件类型筛选 (image, video, document, other)
    :param folder: 文件夹路径（相对于 upload 目录）
    :return: 文件列表
    """
    base_url = str(request.base_url).rstrip('/')
    data = file_service.list(page, size, base_url, keyword, file_type, folder)
    return response_base.success(data=data)


@router.delete(
    '/delete',
    summary='删除文件',
    dependencies=[
        Depends(RequestPermission('sys:file:delete')),
        DependsRBAC,
    ],
)
async def delete_uploaded_file(filename: Annotated[str, Query()]) -> ResponseSchemaModel[None]:
    """
    删除指定文件

    :param filename: 文件名
    :return: 删除结果
    """
    file_service.delete(filename)
    return response_base.success(res=CustomResponse(code=200, msg='文件删除成功'))


@router.post(
    '/create-folder',
    summary='创建文件夹',
    dependencies=[
        Depends(RequestPermission('sys:file:upload')),
        DependsRBAC,
    ],
)
async def create_upload_folder(
    folder_name: Annotated[str, Query()],
    parent_folder: Annotated[str | None, Query()] = None,
) -> ResponseSchemaModel[dict]:
    """
    创建文件夹

    :param folder_name: 文件夹名称
    :param parent_folder: 父文件夹路径（相对于 upload 目录）
    :return: 创建结果
    """
    result = file_service.create_folder(folder_name, parent_folder)
    return response_base.success(
        res=CustomResponse(code=200, msg='文件夹创建成功'),
        data=result,
    )
