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
        from sqlalchemy import select

        from backend.app.gongkao.model.category import GkCategory

        category_ids = []
        if category_id:
            # 递归查找所有子分类 ID
            to_process = [category_id]
            while to_process:
                curr = to_process.pop(0)
                category_ids.append(curr)
                # 查找直接子分类
                stmt = select(GkCategory.id).where(GkCategory.parent_id == curr)
                result = await db.execute(stmt)
                children = result.scalars().all()
                to_process.extend(children)
        
        return await resource_dao.get_list(
            db,
            title=title,
            category_id=category_ids if category_ids else None,
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
    async def upload_file(db: AsyncSession, file, category_id: int) -> dict:
        """
        上传资料预览文件到云存储
        
        :param db: 数据库会话
        :param file: FastAPI UploadFile 对象
        :param category_id: 分类ID
        :return: 上传结果
        """
        from sqlalchemy import select

        from backend.app.gongkao.model.category import GkCategory
        from backend.common.log import log
        
        # 解析分类路径
        safe_parts = []
        
        try:
            stmt = select(GkCategory).where(GkCategory.id == category_id)
            result = await db.execute(stmt)
            cat = result.scalars().first()
            
            if cat:
                # 找到了分类，开始向上递归查找父级
                path_nodes = [cat.name]
                current = cat
                # 防止死循环，限制深度
                depth = 0
                while current.parent_id and depth < 5:
                    stmt = select(GkCategory).where(GkCategory.id == current.parent_id)
                    result = await db.execute(stmt)
                    parent = result.scalars().first()
                    if parent:
                        path_nodes.insert(0, parent.name)
                        current = parent
                    else:
                        break
                    depth += 1
                safe_parts = [re.sub(r'[^\w\u4e00-\u9fff-]', '_', p) for p in path_nodes]
        except Exception as e:
            log.error(f'查询分类失败：{e!s}')

        if not safe_parts:
            safe_parts = ['other']
        
        # 构建文件名
        filename = file.filename or 'unnamed'
        file_ext = filename.split('.')[-1].lower() if '.' in filename else ''
        timestamp = int(timezone.now().timestamp())
        if file_ext:
            new_filename = f'{filename.replace(f".{file_ext}", f"_{timestamp}")}.{file_ext}'
        else:
            new_filename = f'{filename}_{timestamp}'

        category_path = '/'.join(safe_parts)
        uploaded_url, object_key = await storage_service.upload_with_filename(
            db=db,
            file=file,
            filename=new_filename,
            path=f'gk_resource/{category_path}',
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
