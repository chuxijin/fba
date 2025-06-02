#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Sequence

from sqlalchemy import Select, and_, desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.coulddrive.model.user import DriveAccount
from backend.app.coulddrive.schema.user import CreateDriveAccountParam, UpdateDriveAccountParam


class CRUDDriveAccount(CRUDPlus[DriveAccount]):
    """网盘账户数据库操作类"""

    async def get(self, db: AsyncSession, pk: int) -> DriveAccount | None:
        """
        获取网盘账户详情

        :param db: 数据库会话
        :param pk: 网盘账户 ID
        :return:
        """
        return await self.select_model(db, pk)

    async def get_by_user_id(self, db: AsyncSession, user_id: str, type: str) -> DriveAccount | None:
        """
        通过用户ID和类型获取网盘账户

        :param db: 数据库会话
        :param user_id: 用户ID
        :param type: 网盘类型
        :return:
        """
        return await self.select_model_by_column(db, user_id=user_id, type=type)

    async def get_list(self, type: str | None, is_valid: bool | None) -> Select:
        """
        获取网盘账户列表

        :param type: 网盘类型
        :param is_valid: 账号是否有效
        :return:
        """
        stmt = select(self.model).order_by(desc(self.model.created_time))

        filters = []
        if type is not None:
            filters.append(self.model.type == type)
        if is_valid is not None:
            filters.append(self.model.is_valid == is_valid)

        if filters:
            stmt = stmt.where(and_(*filters))

        return stmt

    async def get_all(self, db: AsyncSession) -> Sequence[DriveAccount]:
        """
        获取所有网盘账户

        :param db: 数据库会话
        :return:
        """
        return await self.select_models(db)

    async def get_all_by_type(self, db: AsyncSession, type: str) -> Sequence[DriveAccount]:
        """
        通过类型获取所有网盘账户

        :param db: 数据库会话
        :param type: 网盘类型
        :return:
        """
        return await self.select_models(db, type=type, is_valid=True)

    async def create(self, db: AsyncSession, obj: CreateDriveAccountParam) -> None:
        """
        创建网盘账户

        :param db: 数据库会话
        :param obj: 创建网盘账户参数
        :return:
        """
        await self.create_model(db, obj)

    async def update(self, db: AsyncSession, pk: int, obj: UpdateDriveAccountParam) -> int:
        """
        更新网盘账户

        :param db: 数据库会话
        :param pk: 网盘账户 ID
        :param obj: 更新网盘账户参数
        :return:
        """
        return await self.update_model(db, pk, obj)

    async def delete(self, db: AsyncSession, pk: list[int]) -> int:
        """
        删除网盘账户

        :param db: 数据库会话
        :param pk: 网盘账户 ID 列表
        :return:
        """
        return await self.delete_model_by_column(db, allow_multiple=True, id__in=pk)

    async def update_quota_info(self, db: AsyncSession, pk: int, quota: int, used: int) -> int:
        """
        更新网盘账户配额信息

        :param db: 数据库会话
        :param pk: 网盘账户 ID
        :param quota: 总空间配额
        :param used: 已使用空间
        :return:
        """
        return await self.update_model(db, pk, {"quota": quota, "used": used})

    async def update_vip_status(self, db: AsyncSession, pk: int, is_vip: bool, is_supervip: bool) -> int:
        """
        更新网盘账户VIP状态

        :param db: 数据库会话
        :param pk: 网盘账户 ID
        :param is_vip: 是否VIP用户
        :param is_supervip: 是否超级会员
        :return:
        """
        return await self.update_model(db, pk, {
            "is_vip": is_vip,
            "is_supervip": is_supervip
        })

    async def update_validity(self, db: AsyncSession, pk: int, is_valid: bool) -> int:
        """
        更新网盘账户有效性

        :param db: 数据库会话
        :param pk: 网盘账户 ID
        :param is_valid: 账号是否有效
        :return:
        """
        return await self.update_model(db, pk, {"is_valid": is_valid})

drive_account_dao: CRUDDriveAccount = CRUDDriveAccount(DriveAccount) 