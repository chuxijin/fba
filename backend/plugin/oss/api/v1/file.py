from typing import Annotated

from fastapi import APIRouter, File, Form, UploadFile

from backend.common.dataclasses import OssUploadResult
from backend.common.response.response_schema import ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.database.db import CurrentSession
from backend.plugin.oss.service.storage_service import storage_service
from backend.utils.file_ops import upload_file_verify

router = APIRouter()


@router.post('/upload', summary='云存储文件上传', dependencies=[DependsJwtAuth])
async def oss_upload_files(
    db: CurrentSession,
    file: Annotated[UploadFile, File()],
    path: Annotated[str | None, Form()] = None,
    use_signed_url: Annotated[bool | None, Form()] = None,
    url_expire_seconds: Annotated[int | None, Form()] = None,
    object_expire_days: Annotated[int | None, Form()] = None,
) -> ResponseSchemaModel[OssUploadResult]:
    """
    上传文件到当前启用的云存储 provider。

    :param db: 数据库会话
    :param file: 上传文件
    :return:
    """
    upload_file_verify(file)
    url, object_key = await storage_service.upload(
        db=db,
        file=file,
        path=path,
        use_signed_url=use_signed_url,
        url_expire_seconds=url_expire_seconds,
        object_expire_days=object_expire_days,
    )
    return response_base.success(data={'url': url, 'object_key': object_key})
