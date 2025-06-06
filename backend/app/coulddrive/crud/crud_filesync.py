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
                noload(SyncConfig.sync_tasks)
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
    pass


class CRUDSyncTaskItem(CRUDPlus[SyncTaskItem]):
    pass


# 创建 CRUD 实例
sync_config_dao: CRUDSyncConfig = CRUDSyncConfig(SyncConfig)
sync_task_dao: CRUDSyncTask = CRUDSyncTask(SyncTask)
sync_task_item_dao: CRUDSyncTaskItem = CRUDSyncTaskItem(SyncTaskItem) 