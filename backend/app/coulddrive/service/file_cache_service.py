#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json
from typing import Any
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.coulddrive.crud.crud_file_cache import file_cache_crud
from backend.app.coulddrive.model.file_cache import FileCache
from backend.app.coulddrive.schema.file_cache import (
    CreateFileCacheParam,
    UpdateFileCacheParam,
    FileCacheQueryParam,
    BatchCreateFileCacheParam,
    GetFileCacheDetail,
    GetFileCacheStats,
    FileCacheStatsParam
)
from backend.app.coulddrive.schema.file import BaseFileInfo
from backend.app.coulddrive.schema.enum import RecursionSpeed
from backend.common.exception import errors
from backend.common.log import log


class FileCacheService:
    """文件缓存服务"""

    @staticmethod
    async def get_file_cache(db: AsyncSession, *, cache_id: int) -> GetFileCacheDetail:
        """
        获取文件缓存详情
        
        :param db: 数据库会话
        :param cache_id: 缓存ID
        :return: 文件缓存详情
        """
        cache = await file_cache_crud.get(db, pk=cache_id)
        if not cache:
            raise errors.NotFoundError(msg="文件缓存不存在")
        
        return GetFileCacheDetail.model_validate(cache)

    @staticmethod
    async def get_file_cache_by_file_id(
        db: AsyncSession, 
        *, 
        file_id: str, 
        drive_account_id: int
    ) -> GetFileCacheDetail | None:
        """
        通过文件ID获取缓存
        
        :param db: 数据库会话
        :param file_id: 文件ID
        :param drive_account_id: 网盘账户ID
        :return: 文件缓存详情
        """
        cache = await file_cache_crud.get_by_file_id_and_account(
            db, file_id=file_id, drive_account_id=drive_account_id
        )
        if not cache:
            return None
        
        return GetFileCacheDetail.model_validate(cache)

    @staticmethod
    async def get_file_cache_by_path(
        db: AsyncSession, 
        *, 
        file_path: str, 
        drive_account_id: int
    ) -> GetFileCacheDetail | None:
        """
        通过文件路径获取缓存
        
        :param db: 数据库会话
        :param file_path: 文件路径
        :param drive_account_id: 网盘账户ID
        :return: 文件缓存详情
        """
        cache = await file_cache_crud.get_by_path_and_account(
            db, file_path=file_path, drive_account_id=drive_account_id
        )
        if not cache:
            return None
        
        return GetFileCacheDetail.model_validate(cache)

    @staticmethod
    async def get_children_files(
        db: AsyncSession, 
        *, 
        parent_id: str, 
        drive_account_id: int,
        is_valid: bool = True
    ) -> list[GetFileCacheDetail]:
        """
        获取子文件列表
        
        :param db: 数据库会话
        :param parent_id: 父目录ID
        :param drive_account_id: 网盘账户ID
        :param is_valid: 是否只获取有效缓存
        :return: 子文件列表
        """
        caches = await file_cache_crud.get_children_by_parent(
            db, parent_id=parent_id, drive_account_id=drive_account_id, is_valid=is_valid
        )
        
        return [GetFileCacheDetail.model_validate(cache) for cache in caches]

    @staticmethod
    async def get_cached_children_as_file_info(
        db: AsyncSession,
        *,
        parent_id: str,
        drive_account_id: int,
        is_valid: bool = True
    ) -> list[BaseFileInfo]:
        """
        获取缓存的子文件列表并转换为BaseFileInfo格式（用于快速模式）
        
        :param db: 数据库会话
        :param parent_id: 父目录ID
        :param drive_account_id: 网盘账户ID
        :param is_valid: 是否只获取有效缓存
        :return: BaseFileInfo格式的文件列表
        """
        caches = await file_cache_crud.get_children_by_parent(
            db, parent_id=parent_id, drive_account_id=drive_account_id, is_valid=is_valid
        )
        
        file_list = []
        for cache in caches:
            file_info = BaseFileInfo(
                file_id=cache.file_id,
                file_name=cache.file_name,
                file_path=cache.file_path,
                is_folder=cache.is_folder,
                parent_id=cache.parent_id,
                file_size=cache.file_size or 0,
                created_at=cache.file_created_at or "",
                updated_at=cache.file_updated_at or "",
                file_ext=json.loads(cache.file_ext) if cache.file_ext else {}
            )
            file_list.append(file_info)
        
        return file_list

    @staticmethod
    async def get_file_cache_list(
        db: AsyncSession, 
        *, 
        query_param: FileCacheQueryParam,
        skip: int = 0,
        limit: int = 100
    ) -> list[GetFileCacheDetail]:
        """
        获取文件缓存列表
        
        :param db: 数据库会话
        :param query_param: 查询参数
        :param skip: 跳过数量
        :param limit: 限制数量
        :return: 文件缓存列表
        """
        caches = await file_cache_crud.get_list_by_query(
            db, query_param=query_param, skip=skip, limit=limit
        )
        
        return [GetFileCacheDetail.model_validate(cache) for cache in caches]

    @staticmethod
    async def get_file_cache_select(db: AsyncSession, *, query_param: FileCacheQueryParam):
        """
        获取文件缓存查询语句
        
        :param db: 数据库会话
        :param query_param: 查询参数
        :return: SQLAlchemy Select 对象
        """
        return await file_cache_crud.get_select_by_query(query_param=query_param)

    @staticmethod
    async def create_file_cache(
        db: AsyncSession, 
        *, 
        cache_in: CreateFileCacheParam
    ) -> GetFileCacheDetail:
        """
        创建文件缓存
        
        :param db: 数据库会话
        :param cache_in: 创建参数
        :return: 创建的文件缓存详情
        """
        # 检查是否已存在
        existing = await file_cache_crud.get_by_file_id_and_account(
            db, file_id=cache_in.file_id, drive_account_id=cache_in.drive_account_id
        )
        if existing:
            raise errors.ForbiddenError(msg="文件缓存已存在")
        
        cache = await file_cache_crud.create_with_ext(db, obj_in=cache_in)
        return GetFileCacheDetail.model_validate(cache)

    @staticmethod
    async def update_file_cache(
        db: AsyncSession, 
        *, 
        cache_id: int, 
        cache_in: UpdateFileCacheParam
    ) -> GetFileCacheDetail:
        """
        更新文件缓存
        
        :param db: 数据库会话
        :param cache_id: 缓存ID
        :param cache_in: 更新参数
        :return: 更新后的文件缓存详情
        """
        cache = await file_cache_crud.get(db, pk=cache_id)
        if not cache:
            raise errors.NotFoundError(msg="文件缓存不存在")
        
        # 处理扩展信息
        update_data = cache_in.model_dump(exclude_unset=True, exclude={'file_ext'})
        if cache_in.file_ext is not None:
            update_data['file_ext'] = json.dumps(cache_in.file_ext, ensure_ascii=False)
        
        updated_cache = await file_cache_crud.update(db, db_obj=cache, obj_in=update_data)
        return GetFileCacheDetail.model_validate(updated_cache)

    @staticmethod
    async def delete_file_cache(db: AsyncSession, *, cache_id: int) -> bool:
        """
        删除文件缓存
        
        :param db: 数据库会话
        :param cache_id: 缓存ID
        :return: 是否删除成功
        """
        cache = await file_cache_crud.get(db, pk=cache_id)
        if not cache:
            raise errors.NotFoundError(msg="文件缓存不存在")
        
        await file_cache_crud.delete(db, pk=cache_id)
        return True

    @staticmethod
    async def batch_create_file_cache(
        db: AsyncSession, 
        *, 
        batch_param: BatchCreateFileCacheParam
    ) -> list[GetFileCacheDetail]:
        """
        批量创建文件缓存
        
        :param db: 数据库会话
        :param batch_param: 批量创建参数
        :return: 创建的文件缓存列表
        """
        try:
            caches = await file_cache_crud.batch_create(db, batch_param=batch_param)
            return [GetFileCacheDetail.model_validate(cache) for cache in caches]
        except Exception as e:
            log.error(f"批量创建文件缓存失败: {e}")
            raise errors.ServerError(msg="批量创建文件缓存失败")

    @staticmethod
    async def sync_files_to_cache(
        db: AsyncSession,
        *,
        drive_account_id: int,
        files: list[BaseFileInfo],
        cache_version: str | None = None
    ) -> list[GetFileCacheDetail]:
        """
        同步文件信息到缓存
        
        :param db: 数据库会话
        :param drive_account_id: 网盘账户ID
        :param files: 文件信息列表
        :param cache_version: 缓存版本
        :return: 同步后的缓存列表
        """
        if not cache_version:
            cache_version = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # 转换文件信息为缓存参数
        file_data = []
        for file_info in files:
            file_dict = {
                'file_id': file_info.file_id,
                'file_name': file_info.file_name,
                'file_path': file_info.file_path,
                'is_folder': file_info.is_folder,
                'parent_id': file_info.parent_id,
                'file_size': file_info.file_size,
                'file_created_at': file_info.created_at,
                'file_updated_at': file_info.updated_at,
                'file_ext': file_info.file_ext
            }
            file_data.append(file_dict)
        
        batch_param = BatchCreateFileCacheParam(
            drive_account_id=drive_account_id,
            files=file_data,
            cache_version=cache_version
        )
        
        return await FileCacheService.batch_create_file_cache(db, batch_param=batch_param)

    @staticmethod
    async def smart_cache_write(
        db: AsyncSession,
        *,
        drive_account_id: int,
        files: list[BaseFileInfo],
        cache_version: str | None = None,
        force_update: bool = False
    ) -> tuple[list[GetFileCacheDetail], int, int]:
        """
        智能缓存写入：检查现有缓存，只更新变化的文件
        
        :param db: 数据库会话
        :param drive_account_id: 网盘账户ID
        :param files: 文件信息列表
        :param cache_version: 缓存版本
        :param force_update: 是否强制更新
        :return: (缓存列表, 新增数量, 更新数量)
        """
        if not cache_version:
            cache_version = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        new_count = 0
        updated_count = 0
        result_caches = []
        
        for file_info in files:
            # 检查是否已存在缓存
            existing_cache = await file_cache_crud.get_by_file_id_and_account(
                db, file_id=file_info.file_id, drive_account_id=drive_account_id
            )
            
            if existing_cache:
                # 检查是否需要更新
                needs_update = force_update or (
                    existing_cache.file_name != file_info.file_name or
                    existing_cache.file_path != file_info.file_path or
                    existing_cache.file_size != file_info.file_size or
                    existing_cache.file_updated_at != file_info.updated_at
                )
                
                if needs_update:
                    # 更新现有缓存
                    update_data = {
                        'file_name': file_info.file_name,
                        'file_path': file_info.file_path,
                        'file_size': file_info.file_size,
                        'file_updated_at': file_info.updated_at,
                        'cache_version': cache_version,
                        'is_valid': True,
                        'file_ext': json.dumps(file_info.file_ext, ensure_ascii=False) if file_info.file_ext else None
                    }
                    updated_cache = await file_cache_crud.update(db, db_obj=existing_cache, obj_in=update_data)
                    result_caches.append(GetFileCacheDetail.model_validate(updated_cache))
                    updated_count += 1
                else:
                    # 无需更新，直接返回现有缓存
                    result_caches.append(GetFileCacheDetail.model_validate(existing_cache))
            else:
                # 创建新缓存
                cache_in = CreateFileCacheParam(
                    drive_account_id=drive_account_id,
                    file_id=file_info.file_id,
                    file_name=file_info.file_name,
                    file_path=file_info.file_path,
                    is_folder=file_info.is_folder,
                    parent_id=file_info.parent_id,
                    file_size=file_info.file_size,
                    file_created_at=file_info.created_at,
                    file_updated_at=file_info.updated_at,
                    cache_version=cache_version,
                    file_ext=file_info.file_ext
                )
                new_cache = await file_cache_crud.create_with_ext(db, obj_in=cache_in)
                result_caches.append(GetFileCacheDetail.model_validate(new_cache))
                new_count += 1
        
        log.info(f"智能缓存写入完成: 新增 {new_count} 个，更新 {updated_count} 个")
        return result_caches, new_count, updated_count

    @staticmethod
    async def check_cache_freshness(
        db: AsyncSession,
        *,
        drive_account_id: int,
        parent_id: str,
        max_age_hours: int = 24
    ) -> bool:
        """
        检查缓存新鲜度
        
        :param db: 数据库会话
        :param drive_account_id: 网盘账户ID
        :param parent_id: 父目录ID
        :param max_age_hours: 最大缓存时间（小时）
        :return: 缓存是否新鲜
        """
        from datetime import timedelta
        
        # 获取该目录下最新的缓存记录
        query_param = FileCacheQueryParam(
            drive_account_id=drive_account_id,
            parent_id=parent_id,
            is_valid=True
        )
        
        caches = await file_cache_crud.get_list_by_query(
            db, query_param=query_param, skip=0, limit=1
        )
        
        if not caches:
            return False
        
        latest_cache = caches[0]
        cache_age = datetime.now() - latest_cache.updated_time
        
        return cache_age < timedelta(hours=max_age_hours)

    @staticmethod
    async def invalidate_cache(
        db: AsyncSession,
        *,
        drive_account_id: int,
        cache_version: str | None = None
    ) -> int:
        """
        使缓存失效
        
        :param db: 数据库会话
        :param drive_account_id: 网盘账户ID
        :param cache_version: 缓存版本（可选）
        :return: 更新的记录数
        """
        return await file_cache_crud.update_cache_validity(
            db, drive_account_id=drive_account_id, cache_version=cache_version, is_valid=False
        )

    @staticmethod
    async def clear_cache(
        db: AsyncSession,
        *,
        drive_account_id: int,
        cache_version: str | None = None
    ) -> int:
        """
        清除缓存
        
        :param db: 数据库会话
        :param drive_account_id: 网盘账户ID
        :param cache_version: 缓存版本（可选）
        :return: 删除的记录数
        """
        return await file_cache_crud.delete_by_account(
            db, drive_account_id=drive_account_id, cache_version=cache_version
        )

    @staticmethod
    async def get_cache_stats(
        db: AsyncSession, 
        *, 
        stats_param: FileCacheStatsParam
    ) -> GetFileCacheStats:
        """
        获取缓存统计信息
        
        :param db: 数据库会话
        :param stats_param: 统计参数
        :return: 缓存统计信息
        """
        return await file_cache_crud.get_cache_stats(
            db, drive_account_id=stats_param.drive_account_id
        )


file_cache_service = FileCacheService() 