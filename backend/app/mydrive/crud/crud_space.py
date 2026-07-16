#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.mydrive.model.space import MyDriveSpace


class CRUDMyDriveSpace(CRUDPlus[MyDriveSpace]):
    """文件空间 CRUD"""

    async def get(self, db: AsyncSession, pk: int, owner_id: int) -> MyDriveSpace | None:
        """
        获取用户的文件空间。

        :param db: 数据库会话
        :param pk: 文件空间 ID
        :param owner_id: 所属用户 ID
        :return:
        """
        stmt = select(self.model).where(self.model.id == pk, self.model.owner_id == owner_id, self.model.deleted == 0)
        return (await db.execute(stmt)).scalars().first()

    async def get_by_source_key(
        self,
        db: AsyncSession,
        owner_id: int,
        provider: str,
        space_type: str,
        source_key: str,
    ) -> MyDriveSpace | None:
        """
        按来源唯一标识获取文件空间。

        :param db: 数据库会话
        :param owner_id: 所属用户 ID
        :param provider: 网盘驱动标识
        :param space_type: 文件空间类型
        :param source_key: 来源唯一标识
        :return:
        """
        stmt = select(self.model).where(
            self.model.owner_id == owner_id,
            self.model.provider == provider,
            self.model.space_type == space_type,
            self.model.source_key == source_key,
            self.model.deleted == 0,
        )
        return (await db.execute(stmt)).scalars().first()

    async def get_select(self, owner_id: int, space_type: str | None = None) -> Select:
        """
        获取文件空间查询语句。

        :param owner_id: 所属用户 ID
        :param space_type: 文件空间类型
        :return:
        """
        stmt = select(self.model).where(self.model.owner_id == owner_id, self.model.deleted == 0)
        if space_type:
            stmt = stmt.where(self.model.space_type == space_type)
        return stmt.order_by(self.model.created_time.desc())


mydrive_space_dao: CRUDMyDriveSpace = CRUDMyDriveSpace(MyDriveSpace)
