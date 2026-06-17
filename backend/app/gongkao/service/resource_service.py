#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""资料服务"""

from sqlalchemy import Select
from sqlalchemy.ext.asyncio import AsyncSession

import re

from backend.app.gongkao.crud.crud_resource import resource_dao
from backend.app.gongkao.model.resource import GkResource
from backend.app.gongkao.schema.resource import CreateResourceParam, UpdateResourceParam
from backend.plugin.oss.service.storage_service import storage_service
from backend.utils.timezone import timezone


class ResourceService:
    """资料服务"""

    @staticmethod
    async def get(db: AsyncSession, pk: int) -> GkResource | None:
        """获取资料详情"""
        return await resource_dao.get(db, pk)

    @staticmethod
    async def get_list(
        db: AsyncSession,
        *,
        title: str | None = None,
        category_id: int | None = None,
        file_type: str | None = None,
        status: bool | None = None,
    ) -> Select:
        """获取资料列表"""
        return await resource_dao.get_list(
            db,
            title=title,
            category_id=category_id,
            file_type=file_type,
            status=status,
        )

    @staticmethod
    async def create(db: AsyncSession, obj_in: CreateResourceParam) -> GkResource:
        """创建资料"""
        return await resource_dao.create(db, obj_in)

    @staticmethod
    async def update(db: AsyncSession, pk: int, obj_in: UpdateResourceParam) -> int:
        """更新资料"""
        return await resource_dao.update(db, pk, obj_in)

    @staticmethod
    async def delete(db: AsyncSession, pk: int) -> int:
        """删除资料"""
        return await resource_dao.delete(db, pk)

    @staticmethod
    async def increment_view(db: AsyncSession, pk: int) -> int:
        """增加查看次数"""
        return await resource_dao.increment_view(db, pk)

    @staticmethod
    async def upload_file(db: AsyncSession, file, category_id: int | None = None) -> dict:
        """
        上传资料预览文件到云存储

        :param db: 数据库会话
        :param file: FastAPI UploadFile 对象
        :param category_id: 分类ID（已废弃，保留参数兼容）
        :return: 上传结果
        """
        from backend.common.log import log

        # 构建文件名
        filename = file.filename or 'unnamed'
        file_ext = filename.split('.')[-1].lower() if '.' in filename else ''
        timestamp = int(timezone.now().timestamp())
        if file_ext:
            new_filename = f'{filename.replace(f".{file_ext}", f"_{timestamp}")}.{file_ext}'
        else:
            new_filename = f'{filename}_{timestamp}'

        uploaded_url, object_key = await storage_service.upload_with_filename(
            db=db,
            file=file,
            filename=new_filename,
            path='gk_resource',
            use_signed_url=False,
        )
        log.info('公考资料上传成功: %s', uploaded_url)
        return {
            'url': uploaded_url,
            'filename': new_filename,
            'file_type': file_ext,
            'object_key': object_key,
        }


resource_service: ResourceService = ResourceService()
