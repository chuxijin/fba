#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""资料服务"""
from sqlalchemy import Select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.gongkao.crud.crud_resource import resource_dao
from backend.app.gongkao.model.resource import GkResource
from backend.app.gongkao.schema.resource import CreateResourceParam, UpdateResourceParam


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
        上传资料预览文件
        
        :param db: 数据库会话
        :param file: FastAPI UploadFile 对象
        :param category_id: 分类ID
        :return: { 'url': 相对路径, 'filename': 文件名 }
        """
        import re

        from anyio import open_file
        from sqlalchemy import select

        from backend.app.gongkao.model.category import GkCategory
        from backend.common.exception import errors
        from backend.common.log import log
        from backend.core.conf import settings
        from backend.core.path_conf import STATIC_DIR
        from backend.utils.timezone import timezone
        
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

        if not safe_parts:
            safe_parts = ['other']
        
        # 构建保存目录（支持多级）
        resource_dir = STATIC_DIR / 'gk_resource'
        for part in safe_parts:
            resource_dir = resource_dir / part
        resource_dir.mkdir(parents=True, exist_ok=True)
        
        # 构建文件名
        filename = file.filename or 'unnamed'
        file_ext = filename.split('.')[-1].lower() if '.' in filename else ''
        timestamp = int(timezone.now().timestamp())
        if file_ext:
            new_filename = f'{filename.replace(f".{file_ext}", f"_{timestamp}")}.{file_ext}'
        else:
            new_filename = f'{filename}_{timestamp}'
        
        # 保存文件
        file_path = resource_dir / new_filename
        try:
            async with await open_file(file_path, mode='wb') as fb:
                while True:
                    content = await file.read(settings.UPLOAD_READ_SIZE)
                    if not content:
                        break
                    await fb.write(content)
        except Exception as e:
            log.error(f'上传资料文件 {new_filename} 失败：{e!s}')
            raise errors.RequestError(msg='上传文件失败')
        finally:
            await file.close()
        
        # 返回相对路径（不含域名）
        category_path = '/'.join(safe_parts)
        relative_url = f'/static/gk_resource/{category_path}/{new_filename}'
        
        return {'url': relative_url, 'filename': new_filename}


resource_service: ResourceService = ResourceService()
