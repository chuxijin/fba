#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Any, Optional, Sequence

from sqlalchemy import Select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.common.pagination import paging_data

from backend.app.coulddrive.model.filesync import SyncConfig, SyncTask, SyncTaskItem
from backend.app.coulddrive.schema.filesync import (
    CreateSyncConfigParam,
    CreateSyncTaskParam,
    CreateSyncTaskItemParam,
    UpdateSyncConfigParam,
    UpdateSyncTaskParam,
    UpdateSyncTaskItemParam,
)


class CRUDSyncConfig(CRUDPlus[SyncConfig]):
    async def create(self, db: AsyncSession, *, obj_in: CreateSyncConfigParam, current_user_id: int) -> SyncConfig:
        """
        创建同步配置
        
        :param db: 数据库会话
        :param obj_in: 创建同步配置参数
        :return: 创建的同步配置对象
        """
        dict_obj = obj_in.model_dump()
        
        # 分离可以在__init__中传递的字段和需要单独设置的字段
        init_fields = {
            'type': dict_obj.get('type'),
            'src_path': dict_obj.get('src_path'),
            'dst_path': dict_obj.get('dst_path'),
            'user_id': dict_obj.get('user_id'),
            'created_by': current_user_id,
        }
        
        # 创建对象，只传递可以在__init__中使用的字段
        new_config = self.model(**init_fields)
        
        # 设置其他字段
        for key, value in dict_obj.items():
            if key not in init_fields and hasattr(new_config, key):
                setattr(new_config, key, value)
        
        db.add(new_config)
        await db.flush()
        await db.refresh(new_config)
        await db.commit()
        return new_config

    async def get_all(self, db: AsyncSession) -> Sequence[SyncConfig]:
        """获取所有同步配置"""
        return await self.select_models(db)

    async def get_by_user_id(self, db: AsyncSession, *, user_id: int) -> list[SyncConfig]:
        """根据用户ID获取同步配置列表"""
        return await self.get_list(db, user_id=user_id)

    async def get_enabled_configs(self, db: AsyncSession) -> list[SyncConfig]:
        """获取所有启用的同步配置"""
        return await self.get_list(db, enable=True)

    async def get_list(self, db: AsyncSession, **filters) -> list[SyncConfig]:
        """
        获取同步配置列表
        
        :param db: 数据库会话
        :param filters: 过滤条件
        :return: 同步配置列表
        """
        from sqlalchemy import select, desc
        from sqlalchemy.orm import noload
        
        stmt = (
            select(SyncConfig)
            .options(
                noload(SyncConfig.drive_account),
                noload(SyncConfig.sync_tasks),
                noload(SyncConfig.exclude_template),
                noload(SyncConfig.rename_template)
            )
            .order_by(desc(SyncConfig.created_time))
        )
        
        # 应用过滤条件
        filter_conditions = []
        for key, value in filters.items():
            if hasattr(SyncConfig, key) and value is not None:
                filter_conditions.append(getattr(SyncConfig, key) == value)
        
        if filter_conditions:
            stmt = stmt.where(and_(*filter_conditions))
        
        result = await db.execute(stmt)
        return result.scalars().all()

    async def get_with_validation(self, db: AsyncSession, config_id: int) -> tuple[Optional[SyncConfig], str]:
        """
        获取配置并进行业务验证
        
        :param db: 数据库会话
        :param config_id: 配置ID
        :return: (配置对象, 错误信息)
        """
        config = await self.select_model(db, config_id)
        if not config:
            return None, f"同步配置 {config_id} 不存在"
        
        if not config.enable:
            return config, f"同步配置 {config_id} 已禁用"
        
        return config, ""

    async def update(self, db: AsyncSession, *, db_obj: SyncConfig, obj_in: UpdateSyncConfigParam) -> SyncConfig:
        """
        更新同步配置
        
        :param db: 数据库会话
        :param db_obj: 数据库对象
        :param obj_in: 更新参数
        :return: 更新后的同步配置对象
        """
        update_data = obj_in.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            if hasattr(db_obj, field):
                setattr(db_obj, field, value)
        
        await db.commit()
        await db.refresh(db_obj)
        return db_obj

    async def delete(self, db: AsyncSession, *, id: int) -> bool:
        """
        删除同步配置
        
        :param db: 数据库会话
        :param id: 配置ID
        :return: 是否删除成功
        """
        db_obj = await self.select_model(db, id)
        if not db_obj:
            return False
        
        await db.delete(db_obj)
        await db.commit()
        return True

    def get_list_select(
        self,
        *,
        enable: bool | None = None,
        type: str | None = None,
        remark: str | None = None,
        created_by: int | None = None
    ) -> Select:
        """
        获取同步配置列表的查询语句
        
        :param enable: 是否启用
        :param type: 网盘类型
        :param remark: 备注关键词
        :param created_by: 创建人ID
        :return: 查询语句
        """
        from sqlalchemy import select, desc
        from sqlalchemy.orm import noload
        
        stmt = (
            select(SyncConfig)
            .options(
                noload(SyncConfig.drive_account),
                noload(SyncConfig.sync_tasks),
                noload(SyncConfig.exclude_template),
                noload(SyncConfig.rename_template)
            )
            .order_by(desc(SyncConfig.created_time))
        )
        
        filters = []
        if enable is not None:
            filters.append(SyncConfig.enable == enable)
        if type is not None:
            filters.append(SyncConfig.type == type)
        if remark is not None:
            filters.append(SyncConfig.remark.ilike(f"%{remark}%"))
        if created_by is not None:
            filters.append(SyncConfig.created_by == created_by)
        
        if filters:
            stmt = stmt.where(and_(*filters))
        
        return stmt


class CRUDSyncTask(CRUDPlus[SyncTask]):
    async def create(self, db: AsyncSession, *, obj_in: CreateSyncTaskParam, current_user_id: int = 1) -> SyncTask:
        """
        创建同步任务
        
        :param db: 数据库会话
        :param obj_in: 创建同步任务参数
        :param current_user_id: 当前用户ID
        :return: 创建的同步任务对象
        """
        dict_obj = obj_in.model_dump()
        
        # 分离可以在__init__中传递的字段和需要单独设置的字段
        init_fields = {
            'config_id': dict_obj.get('config_id'),
            'created_by': current_user_id,
        }
        
        # 创建对象，只传递可以在__init__中使用的字段
        new_task = self.model(**init_fields)
        
        # 设置其他字段（init=False的字段）
        for key, value in dict_obj.items():
            if key not in init_fields and hasattr(new_task, key):
                setattr(new_task, key, value)
        
        db.add(new_task)
        await db.flush()
        await db.refresh(new_task)
        return new_task

    async def update(self, db: AsyncSession, *, db_obj: SyncTask, obj_in: UpdateSyncTaskParam) -> SyncTask:
        """
        更新同步任务
        
        :param db: 数据库会话
        :param db_obj: 数据库对象
        :param obj_in: 更新参数
        :return: 更新后的同步任务对象
        """
        update_data = obj_in.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            if hasattr(db_obj, field):
                setattr(db_obj, field, value)
        
        await db.flush()
        await db.refresh(db_obj)
        return db_obj

    async def get_tasks_by_config_id(
        self, 
        db: AsyncSession, 
        *, 
        config_id: int, 
        status: str | None = None
    ) -> list[SyncTask]:
        """
        根据配置ID获取同步任务列表
        
        :param db: 数据库会话
        :param config_id: 配置ID
        :param status: 任务状态筛选
        :return: 同步任务列表
        """
        from sqlalchemy import select, desc
        
        stmt = (
            select(SyncTask)
            .where(SyncTask.config_id == config_id)
            .order_by(desc(SyncTask.created_time))
        )
        
        if status:
            stmt = stmt.where(SyncTask.status == status)
        
        result = await db.execute(stmt)
        return result.scalars().all()

    async def get_task_with_items(self, db: AsyncSession, *, task_id: int) -> SyncTask | None:
        """
        获取包含任务项的同步任务详情
        
        :param db: 数据库会话
        :param task_id: 任务ID
        :return: 同步任务对象
        """
        from sqlalchemy import select
        from sqlalchemy.orm import joinedload
        
        stmt = (
            select(SyncTask)
            .options(joinedload(SyncTask.task_items))
            .where(SyncTask.id == task_id)
        )
        
        result = await db.execute(stmt)
        return result.scalars().first()


class CRUDSyncTaskItem(CRUDPlus[SyncTaskItem]):
    async def create(self, db: AsyncSession, *, obj_in: CreateSyncTaskItemParam) -> SyncTaskItem:
        """
        创建同步任务项
        
        :param db: 数据库会话
        :param obj_in: 创建同步任务项参数
        :return: 创建的同步任务项对象
        """
        dict_obj = obj_in.model_dump()
        
        # 分离可以在__init__中传递的字段和需要单独设置的字段
        init_fields = {
            'task_id': dict_obj.get('task_id'),
            'type': dict_obj.get('type'),
            'src_path': dict_obj.get('src_path'),
            'dst_path': dict_obj.get('dst_path'),
            'file_name': dict_obj.get('file_name'),
        }
        
        # 创建对象，只传递可以在__init__中使用的字段
        new_item = self.model(**init_fields)
        
        # 设置其他字段（init=False的字段）
        for key, value in dict_obj.items():
            if key not in init_fields and hasattr(new_item, key):
                setattr(new_item, key, value)
        
        db.add(new_item)
        await db.flush()
        await db.refresh(new_item)
        return new_item

    async def get_items_by_task_id(
        self, 
        db: AsyncSession, 
        *, 
        task_id: int, 
        status: str | None = None,
        operation_type: str | None = None
    ) -> list[SyncTaskItem]:
        """
        根据任务ID获取同步任务项列表
        
        :param db: 数据库会话
        :param task_id: 任务ID
        :param status: 任务项状态筛选
        :param operation_type: 操作类型筛选
        :return: 同步任务项列表
        """
        from sqlalchemy import select, desc
        
        stmt = (
            select(SyncTaskItem)
            .where(SyncTaskItem.task_id == task_id)
            .order_by(desc(SyncTaskItem.created_time))
        )
        
        filters = []
        if status:
            filters.append(SyncTaskItem.status == status)
        if operation_type:
            filters.append(SyncTaskItem.type == operation_type)
        
        if filters:
            stmt = stmt.where(and_(*filters))
        
        result = await db.execute(stmt)
        return result.scalars().all()

    async def get_task_statistics(self, db: AsyncSession, *, task_id: int) -> dict[str, int]:
        """
        获取任务统计信息
        
        :param db: 数据库会话
        :param task_id: 任务ID
        :return: 统计信息字典
        """
        from sqlalchemy import select, func
        
        # 总数统计
        total_stmt = select(func.count(SyncTaskItem.id)).where(SyncTaskItem.task_id == task_id)
        total_result = await db.execute(total_stmt)
        total_count = total_result.scalar() or 0
        
        # 状态统计
        status_stmt = (
            select(SyncTaskItem.status, func.count(SyncTaskItem.id))
            .where(SyncTaskItem.task_id == task_id)
            .group_by(SyncTaskItem.status)
        )
        status_result = await db.execute(status_stmt)
        status_counts = dict(status_result.fetchall())
        
        # 操作类型统计
        type_stmt = (
            select(SyncTaskItem.type, func.count(SyncTaskItem.id))
            .where(SyncTaskItem.task_id == task_id)
            .group_by(SyncTaskItem.type)
        )
        type_result = await db.execute(type_stmt)
        type_counts = dict(type_result.fetchall())
        
        return {
            'total_count': total_count,
            'status_counts': status_counts,
            'type_counts': type_counts,
            'pending_count': status_counts.get('pending', 0),
            'running_count': status_counts.get('running', 0),
            'completed_count': status_counts.get('completed', 0),
            'failed_count': status_counts.get('failed', 0),
        }


# 创建 CRUD 实例
sync_config_dao: CRUDSyncConfig = CRUDSyncConfig(SyncConfig)
sync_task_dao: CRUDSyncTask = CRUDSyncTask(SyncTask)
sync_task_item_dao: CRUDSyncTaskItem = CRUDSyncTaskItem(SyncTaskItem) 