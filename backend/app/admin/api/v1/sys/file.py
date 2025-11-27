#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
from datetime import datetime
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, File, Query, Request, UploadFile

from backend.common.dataclasses import UploadUrl
from backend.common.exception.errors import NotFoundError
from backend.common.response.response_code import CustomResponse
from backend.common.response.response_schema import ResponseSchemaModel, response_base
from backend.common.security.permission import RequestPermission
from backend.common.security.rbac import DependsRBAC
from backend.core.path_conf import UPLOAD_DIR
from backend.utils.file_ops import upload_file, upload_file_verify

router = APIRouter()


@router.post(
    '/upload',
    summary='本地文件上传',
    dependencies=[
        Depends(RequestPermission('sys:file:upload')),
        DependsRBAC,
    ],
)
async def upload_files(request: Request, file: Annotated[UploadFile, File()]) -> ResponseSchemaModel[UploadUrl]:
    """文件上传"""
    upload_file_verify(file)
    filename = await upload_file(file)
    # 返回完整的 URL（包含域名和端口）
    base_url = str(request.base_url).rstrip('/')
    full_url = f'{base_url}/static/upload/{filename}'
    return response_base.success(data={'url': full_url})


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
    upload_dir = UPLOAD_DIR

    # 确定当前目录
    if folder:
        # 安全检查：防止路径穿越
        folder = folder.strip('/').replace('\\', '/')
        if '..' in folder:
            raise NotFoundError(msg='非法的文件夹路径')
        current_dir = upload_dir / folder
    else:
        current_dir = upload_dir

    if not current_dir.exists():
        return response_base.success(data={'items': [], 'total': 0, 'page': page, 'size': size, 'current_folder': folder or ''})

    # 获取所有文件和文件夹
    all_items = []
    base_url = str(request.base_url).rstrip('/')

    for item_path in current_dir.iterdir():
        # 跳过隐藏文件
        if item_path.name.startswith('.'):
            continue

        if item_path.is_dir():
            # 文件夹
            folder_info = {
                'name': item_path.name,
                'type': 'folder',
                'is_folder': True,
                'created_time': datetime.fromtimestamp(item_path.stat().st_ctime).isoformat(),
            }
            all_items.append(folder_info)
        elif item_path.is_file():
            # 文件
            stat = item_path.stat()
            relative_path = item_path.relative_to(upload_dir).as_posix()
            file_info = {
                'name': item_path.name,
                'url': f'{base_url}/static/upload/{relative_path}',
                'size': stat.st_size,
                'created_time': datetime.fromtimestamp(stat.st_ctime).isoformat(),
                'type': _get_file_type(item_path.name),
                'is_folder': False,
            }

            # 关键词过滤
            if keyword and keyword.lower() not in item_path.name.lower():
                continue

            # 文件类型过滤
            if file_type and file_info['type'] != file_type:
                continue

            all_items.append(file_info)

    # 排序：文件夹在前，然后按创建时间倒序
    all_items.sort(key=lambda x: (not x['is_folder'], x['created_time']), reverse=True)

    # 分页
    total = len(all_items)
    start = (page - 1) * size
    end = start + size
    items = all_items[start:end]

    return response_base.success(
        data={
            'items': items,
            'total': total,
            'page': page,
            'size': size,
            'current_folder': folder or '',
        }
    )


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
    upload_dir = UPLOAD_DIR
    file_path = upload_dir / filename

    if not file_path.exists():
        raise NotFoundError(msg='文件不存在')

    # 安全检查：确保文件在上传目录内
    if not str(file_path.resolve()).startswith(str(upload_dir.resolve())):
        raise NotFoundError(msg='非法的文件路径')

    file_path.unlink()
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
    upload_dir = UPLOAD_DIR

    # 验证文件夹名称
    if not folder_name or folder_name.strip() == '':
        raise NotFoundError(msg='文件夹名称不能为空')

    # 移除危险字符
    folder_name = folder_name.strip().replace('/', '').replace('\\', '').replace('..', '')
    if not folder_name:
        raise NotFoundError(msg='文件夹名称不合法')

    # 确定父目录
    if parent_folder:
        parent_folder = parent_folder.strip('/').replace('\\', '/')
        if '..' in parent_folder:
            raise NotFoundError(msg='非法的文件夹路径')
        parent_dir = upload_dir / parent_folder
    else:
        parent_dir = upload_dir

    # 创建文件夹
    new_folder_path = parent_dir / folder_name

    if new_folder_path.exists():
        raise NotFoundError(msg='文件夹已存在')

    # 安全检查
    if not str(new_folder_path.resolve()).startswith(str(upload_dir.resolve())):
        raise NotFoundError(msg='非法的文件夹路径')

    new_folder_path.mkdir(parents=True, exist_ok=False)

    return response_base.success(
        res=CustomResponse(code=200, msg='文件夹创建成功'),
        data={
            'name': folder_name,
            'path': str(new_folder_path.relative_to(upload_dir).as_posix()) if parent_folder else folder_name,
        },
    )


def _get_file_type(filename: str) -> str:
    """
    根据文件扩展名判断文件类型

    :param filename: 文件名
    :return: 文件类型
    """
    ext = Path(filename).suffix.lower()

    image_exts = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.svg', '.ico', '.bmp'}
    video_exts = {'.mp4', '.avi', '.mov', '.wmv', '.flv', '.mkv', '.webm'}
    document_exts = {'.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx', '.txt', '.md'}

    if ext in image_exts:
        return 'image'
    elif ext in video_exts:
        return 'video'
    elif ext in document_exts:
        return 'document'
    else:
        return 'other'
