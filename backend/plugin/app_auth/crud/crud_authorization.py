#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.plugin.app_auth.model import AppAuthorization
from backend.plugin.app_auth.schema.authorization import CreateAuthorizationParam, UpdateAuthorizationParam


class CRUDAuthorization(CRUDPlus[AppAuthorization]):
    """授权数据库操作类"""

    async def get(self, db: AsyncSession, auth_id: int) -> AppAuthorization | None:
        """
        获取授权详情

        :param db: 数据库会话
        :param auth_id: 授权 ID
        :return:
        """
        return await self.select_model(db, auth_id)

    async def create(self, db: AsyncSession, obj_in: CreateAuthorizationParam) -> AppAuthorization:
        """
        创建授权

        :param db: 数据库会话
        :param obj_in: 创建参数
        :return:
        """
        return await self.create_model(db, obj_in)

    async def update(self, db: AsyncSession, auth_id: int, obj_in: UpdateAuthorizationParam) -> int:
        """
        更新授权

        :param db: 数据库会话
        :param auth_id: 授权 ID
        :param obj_in: 更新参数
        :return:
        """
        return await self.update_model(db, auth_id, obj_in)

    async def delete(self, db: AsyncSession, auth_id: int) -> int:
        """删除授权"""
        return await self.delete_model(db, auth_id)

    async def get_by_app_and_device(self, db: AsyncSession, application_id: int, 
                                   device_id: int) -> AppAuthorization | None:
        """
        获取应用和设备的授权

        :param db: 数据库会话
        :param application_id: 应用 ID
        :param device_id: 设备 ID
        :return:
        """
        stmt = select(self.model).where(
            and_(
                self.model.application_id == application_id,
                self.model.device_id == device_id,
                self.model.status == 1
            )
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def check_authorization(self, db: AsyncSession, application_id: int, 
                                 device_id: int, current_time: datetime) -> AppAuthorization | None:
        """
        检查授权是否有效

        :param db: 数据库会话
        :param application_id: 应用 ID
        :param device_id: 设备 ID
        :param current_time: 当前时间
        :return:
        """
        stmt = select(self.model).where(
            and_(
                self.model.application_id == application_id,
                self.model.device_id == device_id,
                self.model.status == 1,
                self.model.start_time <= current_time,
                (self.model.end_time.is_(None) | (self.model.end_time >= current_time))
            )
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_device(self, db: AsyncSession, device_id: int) -> list[AppAuthorization]:
        """
        获取设备的所有授权

        :param db: 数据库会话
        :param device_id: 设备 ID
        :return:
        """
        stmt = select(self.model).where(self.model.device_id == device_id).order_by(self.model.created_time.desc())
        return await self.select_models(db, stmt)

    async def get_by_application(self, db: AsyncSession, application_id: int) -> list[AppAuthorization]:
        """
        获取应用的所有授权

        :param db: 数据库会话
        :param application_id: 应用 ID
        :return:
        """
        stmt = select(self.model).where(self.model.application_id == application_id).order_by(self.model.created_time.desc())
        return await self.select_models(db, stmt)

    async def get_list(self, db: AsyncSession, application_id: int = None, device_id: int = None, 
                      status: int = None) -> list[AppAuthorization]:
        """获取授权列表"""
        stmt = select(self.model)
        if application_id:
            stmt = stmt.where(self.model.application_id == application_id)
        if device_id:
            stmt = stmt.where(self.model.device_id == device_id)
        if status is not None:
            stmt = stmt.where(self.model.status == status)
        stmt = stmt.order_by(self.model.created_time.desc())
        return await self.select_models(db, stmt)

    def get_select(self, application_id: int = None, device_id: int = None, 
                  auth_type: int = None, status: int = None):
        """
        获取授权查询语句

        :param application_id: 应用 ID
        :param device_id: 设备 ID
        :param auth_type: 授权类型
        :param status: 状态
        :return:
        """
        stmt = select(self.model)
        if application_id:
            stmt = stmt.where(self.model.application_id == application_id)
        if device_id:
            stmt = stmt.where(self.model.device_id == device_id)
        if auth_type is not None:
            stmt = stmt.where(self.model.auth_type == auth_type)
        if status is not None:
            stmt = stmt.where(self.model.status == status)
        stmt = stmt.order_by(self.model.created_time.desc())
        return stmt


authorization_dao: CRUDAuthorization = CRUDAuthorization(AppAuthorization)