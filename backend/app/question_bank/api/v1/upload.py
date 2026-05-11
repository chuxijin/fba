#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import logging

from typing import Annotated

from fastapi import APIRouter, File, UploadFile

from backend.app.question_bank.crud.crud_user import user_account_dao
from backend.common.dataclasses import UploadUrl
from backend.common.response.response_schema import ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.database.db import CurrentSessionTransaction
from backend.plugin.oss.service.storage_service import storage_service
from backend.utils.file_ops import upload_file_verify

log = logging.getLogger(__name__)

router = APIRouter()


@router.post('/avatar', summary='上传头像', name='qbank_upload_avatar', dependencies=[DependsJwtAuth])
async def upload_avatar(
    db: CurrentSessionTransaction,
    file: Annotated[UploadFile, File()],
) -> ResponseSchemaModel[UploadUrl]:
    """上传用户头像并更新数据库"""
    upload_file_verify(file)
    full_url, _object_key = await storage_service.upload(
        db=db,
        file=file,
        path='avatar/qbank',
        use_signed_url=False,
    )

    await user_account_dao.update_avatar_by_sys_user_id(db, request.user.id, full_url)

    log.info('用户 %d 上传头像成功: %s', request.user.id, full_url)

    return response_base.success(data={'url': full_url})
