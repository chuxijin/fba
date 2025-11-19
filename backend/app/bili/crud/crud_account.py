#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from collections.abc import Sequence

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.bili.model import BiliAccount
from backend.app.bili.schema.account import CreateBiliAccountParam, UpdateBiliAccountParam


class CRUDBiliAccount(CRUDPlus[BiliAccount]):
    """B 站账号数据库操作类"""

    async def get(self, db: AsyncSession, pk: int) -> BiliAccount | None:
        """
        获取账号详情

        :param db: 数据库会话
        :param pk: 主键 ID
        :return:
        """
        return await self.select_model(db, pk)

    async def get_by_mid(self, db: AsyncSession, mid: str) -> BiliAccount | None:
        """
        通过 MID 获取账号

        :param db: 数据库会话
        :param mid: B 站用户 MID
        :return:
        """
        return await self.select_model_by_column(db, mid=mid)

    async def get_list(
        self,
        db: AsyncSession,
        account_name: str | None = None,
        mid: str | None = None,
        status: int | None = None,
        category_id: int | None = None,
    ) -> Sequence[BiliAccount]:
        """
        获取账号列表

        :param db: 数据库会���
        :param account_name: 账号名称
        :param mid: B 站用户 MID
        :param status: 状态
        :param category_id: 分类 ID
        :return:
        """
        filters = {}
        if account_name is not None:
            filters['account_name__like'] = f'%{account_name}%'
        if mid is not None:
            filters['mid'] = mid
        if status is not None:
            filters['status'] = status
        if category_id is not None:
            filters['category_id'] = category_id
        return await self.select_models(db, **filters)

    async def create(self, db: AsyncSession, obj: CreateBiliAccountParam) -> None:
        """
        创建账号

        :param db: 数据库会话
        :param obj: 创建参数
        :return:
        """
        await self.create_model(db, obj)

    async def update(self, db: AsyncSession, pk: int, obj: UpdateBiliAccountParam) -> int:
        """
        更新账号

        :param db: 数据库会话
        :param pk: 主键 ID
        :param obj: 更新参数
        :return:
        """
        return await self.update_model(db, pk, obj)

    async def delete(self, db: AsyncSession, pk: int) -> int:
        """
        删除账号

        :param db: 数据库会话
        :param pk: 主键 ID
        :return:
        """
        return await self.delete_model(db, pk)


bili_account_dao: CRUDBiliAccount = CRUDBiliAccount(BiliAccount)
