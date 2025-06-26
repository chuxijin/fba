#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json
from typing import Any

from sqlalchemy import and_, func, select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.coulddrive.model.file_cache import FileCache
from backend.app.coulddrive.schema.file_cache import (
    CreateFileCacheParam,
    UpdateFileCacheParam,
    FileCacheQueryParam,
    BatchCreateFileCacheParam,
    GetFileCacheStats
)
from sqlalchemy_crud_plus import CRUDPlus


class CRUDFileCache(CRUDPlus[FileCache]):
    """文件缓存 CRUD"""

    async def get_by_file_id_and_account(
        self, 
        db: AsyncSession, 
        *, 
        file_id: str, 
        drive_account_id: int
    ) -> FileCache | None:
        """
        通过文件ID和账户ID获取缓存
        
        :param db: 数据库会话
        :param file_id: 文件ID
        :param drive_account_id: 网盘账户ID
        :return: 文件缓存对象
        """
        stmt = select(self.model).where(
            and_(
                self.model.file_id == file_id,
                self.model.drive_account_id == drive_account_id
            )
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_path_and_account(
        self, 
        db: AsyncSession, 
        *, 
        file_path: str, 
        drive_account_id: int
    ) -> FileCache | None:
        """
        通过文件路径和账户ID获取缓存
        
        :param db: 数据库会话
        :param file_path: 文件路径
        :param drive_account_id: 网盘账户ID
        :return: 文件缓存对象
        """
        stmt = select(self.model).where(
            and_(
                self.model.file_path == file_path,
                self.model.drive_account_id == drive_account_id
            )
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_children_by_parent(
        self, 
        db: AsyncSession, 
        *, 
        parent_id: str, 
        drive_account_id: int,
        is_valid: bool = True
    ) -> list[FileCache]:
        """
        获取指定父目录下的子文件/文件夹
        
        :param db: 数据库会话
        :param parent_id: 父目录ID
        :param drive_account_id: 网盘账户ID
        :param is_valid: 是否只获取有效缓存
        :return: 子文件列表
        """
        conditions = [
            self.model.parent_id == parent_id,
            self.model.drive_account_id == drive_account_id
        ]
        
        if is_valid:
            conditions.append(self.model.is_valid == True)
            
        stmt = select(self.model).where(and_(*conditions)).order_by(
            self.model.is_folder.desc(),
            self.model.file_name
        )
        result = await db.execute(stmt)
        return result.scalars().all()

    async def get_list_by_query(
        self, 
        db: AsyncSession, 
        *, 
        query_param: FileCacheQueryParam,
        skip: int = 0,
        limit: int = 100
    ) -> list[FileCache]:
        """
        根据查询参数获取文件缓存列表
        
        :param db: 数据库会话
        :param query_param: 查询参数
        :param skip: 跳过数量
        :param limit: 限制数量
        :return: 文件缓存列表
        """
        conditions = []
        
        if query_param.drive_account_id is not None:
            conditions.append(self.model.drive_account_id == query_param.drive_account_id)
        if query_param.file_path is not None:
            conditions.append(self.model.file_path.like(f"%{query_param.file_path}%"))
        if query_param.parent_id is not None:
            conditions.append(self.model.parent_id == query_param.parent_id)
        if query_param.is_folder is not None:
            conditions.append(self.model.is_folder == query_param.is_folder)
        if query_param.is_valid is not None:
            conditions.append(self.model.is_valid == query_param.is_valid)
        if query_param.cache_version is not None:
            conditions.append(self.model.cache_version == query_param.cache_version)
            
        stmt = select(self.model)
        if conditions:
            stmt = stmt.where(and_(*conditions))
            
        stmt = stmt.order_by(
            self.model.is_folder.desc(),
            self.model.file_name
        ).offset(skip).limit(limit)
        
        result = await db.execute(stmt)
        return result.scalars().all()

    async def get_select_by_query(self, *, query_param: FileCacheQueryParam):
        """
        根据查询参数获取文件缓存查询语句
        
        :param query_param: 查询参数
        :return: SQLAlchemy Select 对象
        """
        conditions = []
        
        if query_param.drive_account_id is not None:
            conditions.append(self.model.drive_account_id == query_param.drive_account_id)
        if query_param.file_path is not None:
            conditions.append(self.model.file_path.like(f"%{query_param.file_path}%"))
        if query_param.parent_id is not None:
            conditions.append(self.model.parent_id == query_param.parent_id)
        if query_param.is_folder is not None:
            conditions.append(self.model.is_folder == query_param.is_folder)
        if query_param.is_valid is not None:
            conditions.append(self.model.is_valid == query_param.is_valid)
        if query_param.cache_version is not None:
            conditions.append(self.model.cache_version == query_param.cache_version)
            
        stmt = select(self.model)
        if conditions:
            stmt = stmt.where(and_(*conditions))
            
        stmt = stmt.order_by(
            self.model.is_folder.desc(),
            self.model.file_name
        )
        
        return stmt

    async def create_with_ext(
        self, 
        db: AsyncSession, 
        *, 
        obj_in: CreateFileCacheParam
    ) -> FileCache:
        """
        创建文件缓存（处理扩展信息）
        
        :param db: 数据库会话
        :param obj_in: 创建参数
        :return: 创建的文件缓存对象
        """
        # 排除 init=False 的字段
        obj_data = obj_in.model_dump(exclude={'file_ext'})
        
        # 处理扩展信息
        if obj_in.file_ext:
            obj_data['file_ext'] = json.dumps(obj_in.file_ext, ensure_ascii=False)
        
        # 创建对象时只传递 init=True 的字段
        init_fields = {
            'file_id': obj_data['file_id'],
            'file_name': obj_data['file_name'],
            'file_path': obj_data['file_path'],
            'drive_account_id': obj_data['drive_account_id']
        }
        
        db_obj = self.model(**init_fields)
        
        # 设置 init=False 的字段
        if 'parent_id' in obj_data:
            db_obj.parent_id = obj_data['parent_id']
        if 'is_folder' in obj_data:
            db_obj.is_folder = obj_data['is_folder']
        if 'file_size' in obj_data:
            db_obj.file_size = obj_data['file_size']
        if 'file_created_at' in obj_data:
            db_obj.file_created_at = obj_data['file_created_at']
        if 'file_updated_at' in obj_data:
            db_obj.file_updated_at = obj_data['file_updated_at']
        if 'file_ext' in obj_data:
            db_obj.file_ext = obj_data['file_ext']
        if 'cache_version' in obj_data:
            db_obj.cache_version = obj_data['cache_version']
        if 'is_valid' in obj_data:
            db_obj.is_valid = obj_data['is_valid']
        
        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj

    async def batch_create(
        self, 
        db: AsyncSession, 
        *, 
        batch_param: BatchCreateFileCacheParam
    ) -> list[FileCache]:
        """
        批量创建文件缓存
        
        :param db: 数据库会话
        :param batch_param: 批量创建参数
        :return: 创建的文件缓存列表
        """
        db_objs = []
        
        for file_info in batch_param.files:
            obj_data = {
                'drive_account_id': batch_param.drive_account_id,
                'cache_version': batch_param.cache_version,
                **file_info
            }
            
            # 处理扩展信息
            if 'file_ext' in obj_data and obj_data['file_ext']:
                if isinstance(obj_data['file_ext'], dict):
                    obj_data['file_ext'] = json.dumps(obj_data['file_ext'], ensure_ascii=False)
            
            # 创建对象时只传递 init=True 的字段
            init_fields = {
                'file_id': obj_data['file_id'],
                'file_name': obj_data['file_name'],
                'file_path': obj_data['file_path'],
                'drive_account_id': obj_data['drive_account_id']
            }
            
            db_obj = self.model(**init_fields)
            
            # 设置 init=False 的字段
            if 'parent_id' in obj_data:
                db_obj.parent_id = obj_data['parent_id']
            if 'is_folder' in obj_data:
                db_obj.is_folder = obj_data['is_folder']
            if 'file_size' in obj_data:
                db_obj.file_size = obj_data['file_size']
            if 'file_created_at' in obj_data:
                db_obj.file_created_at = obj_data['file_created_at']
            if 'file_updated_at' in obj_data:
                db_obj.file_updated_at = obj_data['file_updated_at']
            if 'file_ext' in obj_data:
                db_obj.file_ext = obj_data['file_ext']
            if 'cache_version' in obj_data:
                db_obj.cache_version = obj_data['cache_version']
            if 'is_valid' in obj_data:
                db_obj.is_valid = obj_data['is_valid']
            
            db_objs.append(db_obj)
        
        db.add_all(db_objs)
        await db.commit()
        
        for db_obj in db_objs:
            await db.refresh(db_obj)
            
        return db_objs

    async def update_cache_validity(
        self, 
        db: AsyncSession, 
        *, 
        drive_account_id: int,
        cache_version: str | None = None,
        is_valid: bool = False
    ) -> int:
        """
        批量更新缓存有效性
        
        :param db: 数据库会话
        :param drive_account_id: 网盘账户ID
        :param cache_version: 缓存版本（可选）
        :param is_valid: 是否有效
        :return: 更新的记录数
        """
        conditions = [self.model.drive_account_id == drive_account_id]
        
        if cache_version is not None:
            conditions.append(self.model.cache_version == cache_version)
            
        stmt = update(self.model).where(and_(*conditions)).values(is_valid=is_valid)
        result = await db.execute(stmt)
        await db.commit()
        return result.rowcount

    async def delete_by_account(
        self, 
        db: AsyncSession, 
        *, 
        drive_account_id: int,
        cache_version: str | None = None
    ) -> int:
        """
        删除指定账户的缓存
        
        :param db: 数据库会话
        :param drive_account_id: 网盘账户ID
        :param cache_version: 缓存版本（可选）
        :return: 删除的记录数
        """
        conditions = [self.model.drive_account_id == drive_account_id]
        
        if cache_version is not None:
            conditions.append(self.model.cache_version == cache_version)
            
        stmt = delete(self.model).where(and_(*conditions))
        result = await db.execute(stmt)
        await db.commit()
        return result.rowcount

    async def get_cache_stats(
        self, 
        db: AsyncSession, 
        *, 
        drive_account_id: int | None = None
    ) -> GetFileCacheStats:
        """
        获取缓存统计信息
        
        :param db: 数据库会话
        :param drive_account_id: 网盘账户ID（可选）
        :return: 缓存统计信息
        """
        conditions = []
        if drive_account_id is not None:
            conditions.append(self.model.drive_account_id == drive_account_id)
            
        base_query = select(self.model)
        if conditions:
            base_query = base_query.where(and_(*conditions))
        
        # 总文件数和文件夹数
        files_stmt = base_query.where(self.model.is_folder == False)
        folders_stmt = base_query.where(self.model.is_folder == True)
        
        # 总大小
        size_stmt = select(func.coalesce(func.sum(self.model.file_size), 0))
        if conditions:
            size_stmt = size_stmt.where(and_(*conditions))
        
        # 有效和无效缓存数
        valid_stmt = base_query.where(self.model.is_valid == True)
        invalid_stmt = base_query.where(self.model.is_valid == False)
        
        # 缓存版本列表
        versions_stmt = select(self.model.cache_version).distinct()
        if conditions:
            versions_stmt = versions_stmt.where(and_(*conditions))
        
        # 执行查询
        total_files = (await db.execute(select(func.count()).select_from(files_stmt.subquery()))).scalar()
        total_folders = (await db.execute(select(func.count()).select_from(folders_stmt.subquery()))).scalar()
        total_size = (await db.execute(size_stmt)).scalar()
        valid_caches = (await db.execute(select(func.count()).select_from(valid_stmt.subquery()))).scalar()
        invalid_caches = (await db.execute(select(func.count()).select_from(invalid_stmt.subquery()))).scalar()
        
        versions_result = await db.execute(versions_stmt)
        cache_versions = [v for v in versions_result.scalars().all() if v is not None]
        
        return GetFileCacheStats(
            total_files=total_files or 0,
            total_folders=total_folders or 0,
            total_size=total_size or 0,
            valid_caches=valid_caches or 0,
            invalid_caches=invalid_caches or 0,
            cache_versions=cache_versions
        )


file_cache_crud = CRUDFileCache(FileCache) 