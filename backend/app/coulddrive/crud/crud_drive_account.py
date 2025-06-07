#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Sequence

from sqlalchemy import Select, and_, desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import noload
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

    async def get_list_with_pagination(self, db: AsyncSession, type: str | None = None, is_valid: bool | None = None) -> Sequence[DriveAccount]:
        """
        获取网盘账户分页列表

        :param db: 数据库会话
        :param type: 网盘类型
        :param is_valid: 账号是否有效
        :return:
        """
        stmt = await self.get_list(type, is_valid)
        # 避免加载关联数据，防止懒加载导致的异步问题
        stmt = stmt.options(noload(DriveAccount.sync_configs), noload(DriveAccount.file_caches))
        result = await db.execute(stmt)
        return result.scalars().all()

    async def get_all(self, db: AsyncSession) -> Sequence[DriveAccount]:
        """
        获取所有网盘账户

        :param db: 数据库会话
        :return:
        """
        stmt = select(self.model).options(noload(DriveAccount.sync_configs), noload(DriveAccount.file_caches))
        result = await db.execute(stmt)
        return result.scalars().all()

    async def get_all_by_type(self, db: AsyncSession, type: str) -> Sequence[DriveAccount]:
        """
        通过类型获取所有网盘账户

        :param db: 数据库会话
        :param type: 网盘类型
        :return:
        """
        stmt = select(self.model).where(
            self.model.type == type, 
            self.model.is_valid == True
        ).options(noload(DriveAccount.sync_configs), noload(DriveAccount.file_caches))
        result = await db.execute(stmt)
        return result.scalars().all()

    async def create(self, db: AsyncSession, obj: CreateDriveAccountParam, current_user_id: int | None = None) -> None:
        """
        创建网盘账户

        :param db: 数据库会话
        :param obj: 创建网盘账户参数
        :param current_user_id: 当前用户ID
        :return:
        """
        if current_user_id and not obj.created_by:
            obj.created_by = current_user_id
        await self.create_model(db, obj)
        await db.commit()

    async def update(self, db: AsyncSession, pk: int, obj: UpdateDriveAccountParam) -> int:
        """
        更新网盘账户

        :param db: 数据库会话
        :param pk: 网盘账户 ID
        :param obj: 更新网盘账户参数
        :return:
        """
        result = await self.update_model(db, pk, obj)
        await db.commit()
        return result

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

    async def create_or_update(
        self, 
        db: AsyncSession, 
        user_info: 'BaseUserInfo', 
        drive_type: str, 
        cookies: str, 
        current_user_id: int
    ) -> None:
        """
        根据用户信息创建或更新网盘账户

        :param db: 数据库会话
        :param user_info: 用户信息
        :param drive_type: 网盘类型
        :param cookies: 认证令牌
        :param current_user_id: 当前用户ID
        :return:
        """
        existing_user = await self.get_by_user_id(db, user_id=user_info.user_id, type=drive_type)
        
        if existing_user:
            # 用户已存在，更新信息
            update_data = UpdateDriveAccountParam(
                username=user_info.username,
                avatar_url=user_info.avatar_url,
                quota=user_info.quota,
                used=user_info.used,
                is_vip=user_info.is_vip,
                is_supervip=user_info.is_supervip,
                cookies=cookies,
                is_valid=True
            )
            await self.update(db, existing_user.id, update_data)
        else:
            # 创建新用户
            create_data = CreateDriveAccountParam(
                user_id=user_info.user_id,
                username=user_info.username,
                avatar_url=user_info.avatar_url,
                quota=user_info.quota,
                used=user_info.used,
                is_vip=user_info.is_vip,
                is_supervip=user_info.is_supervip,
                type=drive_type,
                cookies=cookies,
                is_valid=True,
                created_by=current_user_id
            )
            await self.create(db, create_data, current_user_id=current_user_id)

    async def get_id_by_cookies(self, db: AsyncSession, cookies: str) -> int | None:
        """
        通过cookies获取网盘账户ID
        
        :param db: 数据库会话
        :param cookies: 认证令牌
        :return: 网盘账户ID，如果未找到则返回None
        """
        account = await self.select_model_by_column(db, cookies=cookies, is_valid=True)
        return account.id if account else None

drive_account_dao: CRUDDriveAccount = CRUDDriveAccount(DriveAccount) 