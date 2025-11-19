#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from collections.abc import Sequence

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.bili.model import BiliWork
from backend.app.bili.schema.work import CreateBiliWorkParam, UpdateBiliWorkParam


class CRUDBiliWork(CRUDPlus[BiliWork]):
    """B 站作品数据库操作类"""

    async def get(self, db: AsyncSession, pk: int) -> BiliWork | None:
        """
        获取作品详情

        :param db: 数据库会话
        :param pk: 主键 ID
        :return:
        """
        return await self.select_model(db, pk)

    async def get_by_work_id(self, db: AsyncSession, work_id: str) -> BiliWork | None:
        """
        通过作品 ID 获取作品

        :param db: 数据库会话
        :param work_id: B 站作品 ID
        :return:
        """
        return await self.select_model_by_column(db, work_id=work_id)

    async def get_list(
        self,
        db: AsyncSession,
        work_id: str | None = None,
        title: str | None = None,
        work_type: str | None = None,
        mid: str | None = None,
    ) -> Sequence[BiliWork]:
        """
        获取作品列表

        :param db: 数据库会话
        :param work_id: 作品 ID
        :param title: 标题
        :param work_type: 作品类型
        :param mid: 所属 MID
        :return:
        """
        filters = {}
        if work_id is not None:
            filters['work_id'] = work_id
        if title is not None:
            filters['title__like'] = f'%{title}%'
        if work_type is not None:
            filters['work_type'] = work_type
        if mid is not None:
            filters['mid'] = mid
        return await self.select_models_order(db, 'publish_time', 'desc', **filters)

    async def create(self, db: AsyncSession, obj: CreateBiliWorkParam) -> BiliWork:
        """
        创建作品

        :param db: 数据库会话
        :param obj: 创建参数
        :return: 创建的作品对象
        """
        work = await self.create_model(db, obj)
        await db.flush()
        await db.refresh(work)
        return work

    async def update(self, db: AsyncSession, pk: int, obj: UpdateBiliWorkParam) -> int:
        """
        更新作品

        :param db: 数据库会话
        :param pk: 主键 ID
        :param obj: 更新参数
        :return:
        """
        return await self.update_model(db, pk, obj)

    async def delete(self, db: AsyncSession, pk: int) -> int:
        """
        删除作品

        :param db: 数据库会话
        :param pk: 主键 ID
        :return:
        """
        return await self.delete_model(db, pk)


bili_work_dao: CRUDBiliWork = CRUDBiliWork(BiliWork)
