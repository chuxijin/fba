#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.mydrive.model.account import MyDriveAccount


class CRUDMyDriveAccount(CRUDPlus[MyDriveAccount]):
    """网盘账户 CRUD"""

    async def get(self, db: AsyncSession, pk: int, owner_id: int) -> MyDriveAccount | None:
        """
        获取用户的网盘账户。

        :param db: 数据库会话
        :param pk: 账户 ID
        :param owner_id: 所属用户 ID
        :return:
        """
        stmt = select(self.model).where(self.model.id == pk, self.model.owner_id == owner_id, self.model.deleted == 0)
        return (await db.execute(stmt)).scalars().first()

    async def get_by_external_id(
        self,
        db: AsyncSession,
        owner_id: int,
        provider: str,
        external_account_id: str,
    ) -> MyDriveAccount | None:
        """
        按外部账户标识获取账户。

        :param db: 数据库会话
        :param owner_id: 所属用户 ID
        :param provider: 网盘驱动标识
        :param external_account_id: 网盘侧账户标识
        :return:
        """
        stmt = select(self.model).where(
            self.model.owner_id == owner_id,
            self.model.provider == provider,
            self.model.external_account_id == external_account_id,
            self.model.deleted == 0,
        )
        return (await db.execute(stmt)).scalars().first()

    async def get_select(self, owner_id: int, provider: str | None = None) -> Select:
        """
        获取账户查询语句。

        :param owner_id: 所属用户 ID
        :param provider: 网盘驱动标识
        :return:
        """
        stmt = select(self.model).where(self.model.owner_id == owner_id, self.model.deleted == 0)
        if provider:
            stmt = stmt.where(self.model.provider == provider)
        return stmt.order_by(self.model.created_time.desc())

    async def list_active_share_accounts(self, db: AsyncSession) -> list[MyDriveAccount]:
        """获取支持分享管理的活跃账户。"""
        stmt = select(self.model).where(
            self.model.provider.in_(['baidu', 'quark']),
            self.model.status == 'active',
            self.model.deleted == 0,
        )
        return list((await db.execute(stmt)).scalars().all())

    async def list_active_accounts(self, db: AsyncSession) -> list[MyDriveAccount]:
        """获取所有活跃网盘账户。"""
        stmt = select(self.model).where(self.model.status == 'active', self.model.deleted == 0)
        return list((await db.execute(stmt)).scalars().all())


mydrive_account_dao: CRUDMyDriveAccount = CRUDMyDriveAccount(MyDriveAccount)
