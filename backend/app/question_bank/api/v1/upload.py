#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
文件上传接口
"""
from typing import Annotated

from fastapi import APIRouter, File, Request, UploadFile

from backend.app.question_bank.crud.crud_user import user_account_dao
from backend.app.question_bank.security import DependsCurrentUser
from backend.common.dataclasses import UploadUrl
from backend.common.response.response_schema import ResponseSchemaModel, response_base
from backend.common.security.auth_strategy import AuthUser
from backend.database.db import CurrentSessionTransaction
from backend.utils.file_ops import upload_file, upload_file_verify

router = APIRouter()


@router.post('/avatar', summary='上传头像', name='qbank_upload_avatar')
async def upload_avatar(
    request: Request,
    db: CurrentSessionTransaction,
    file: Annotated[UploadFile, File()],
    current_user: AuthUser = DependsCurrentUser,
) -> ResponseSchemaModel[UploadUrl]:
    """
    上传用户头像并更新数据库

    :param request: Request 对象
    :param db: 数据库会话
    :param file: 上传的文件
    :param current_user: 当前用户
    :return: 文件 URL
    """
    upload_file_verify(file)
    filename = await upload_file(file)

    # 返回完整的 URL（包含域名和端口）
    base_url = str(request.base_url).rstrip('/')
    full_url = f'{base_url}/static/upload/{filename}'

    # ✅ 立即更新数据库
    await user_account_dao.update_avatar(db, current_user.user_id, full_url)

    print(f'[Upload API] 用户 {current_user.user_id} 上传头像成功: {full_url}')

    return response_base.success(data={'url': full_url})

