#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
文件上传接口（无需权限，供小程序用户使用）
"""
from typing import Annotated

from fastapi import APIRouter, File, Request, UploadFile

from backend.common.dataclasses import UploadUrl
from backend.common.response.response_schema import ResponseSchemaModel, response_base
from backend.utils.file_ops import upload_file, upload_file_verify

router = APIRouter()


@router.post('/avatar', summary='上传头像', name='qbank_upload_avatar')
async def upload_avatar(request: Request, file: Annotated[UploadFile, File()]) -> ResponseSchemaModel[UploadUrl]:
    """
    上传用户头像（无需权限）

    :param request: Request 对象
    :param file: 上传的文件
    :return: 文件 URL
    """
    upload_file_verify(file)
    filename = await upload_file(file)
    # 返回完整的 URL（包含域名和端口）
    base_url = str(request.base_url).rstrip('/')
    full_url = f'{base_url}/static/upload/{filename}'
    return response_base.success(data={'url': full_url})
