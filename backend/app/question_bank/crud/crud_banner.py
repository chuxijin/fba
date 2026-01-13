#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.question_bank.model import Banner
from backend.app.question_bank.schema.banner import CreateBannerParam, UpdateBannerParam


class CRUDBanner(CRUDPlus[Banner]):
    """轮播图数据库操作类"""

    async def get(self, db: AsyncSession, banner_id: int) -> Banner | None:
        """
        获取轮播图详情

        :param db: 数据库会话
        :param banner_id: 轮播图 ID
        :return:
        """
        return await self.select_model_by_column(db, id=banner_id)

    async def get_all(
        self,
        db: AsyncSession,
        status: int | None = None,
        scene: str | None = None,
    ) -> Sequence[Banner]:
        """
        获取所有轮播图

        :param db: 数据库会话
        :param status: 状态筛选
        :param scene: 展示场景筛选
        :return:
        """
        filters = {}
        if status is not None:
            filters['status'] = status
        if scene is not None:
            filters['scene'] = scene

        stmt = select(self.model).filter_by(**filters).order_by(self.model.sort, self.model.id.desc())
        result = await db.execute(stmt)
        return result.scalars().all()

    async def get_active_list(self, db: AsyncSession, scene: str | None = None) -> Sequence[Banner]:
        """
        获取启用且在有效期内的轮播图列表

        :param db: 数据库会话
        :param scene: 展示场景筛选
        :return:
        """
        now = datetime.now()
        stmt = (
            select(self.model)
            .where(self.model.status == 1)
            .where(
                (self.model.start_time.is_(None)) | (self.model.start_time <= now),
            )
            .where(
                (self.model.end_time.is_(None)) | (self.model.end_time >= now),
            )
        )
        if scene is not None:
            stmt = stmt.where(self.model.scene == scene)
        stmt = stmt.order_by(self.model.sort, self.model.id.desc())
        result = await db.execute(stmt)
        return result.scalars().all()

    async def create(self, db: AsyncSession, obj_in: CreateBannerParam) -> None:
        """
        创建轮播图

        :param db: 数据库会话
        :param obj_in: 创建参数
        :return:
        """
        await self.create_model(db, obj_in)

    async def update(self, db: AsyncSession, banner_id: int, obj_in: UpdateBannerParam) -> int:
        """
        更新轮播图

        :param db: 数据库会话
        :param banner_id: 轮播图 ID
        :param obj_in: 更新参数
        :return:
        """
        return await self.update_model(db, banner_id, obj_in)

    async def delete(self, db: AsyncSession, banner_id: int) -> int:
        """
        删除轮播图

        :param db: 数据库会话
        :param banner_id: 轮播图 ID
        :return:
        """
        return await self.delete_model(db, banner_id)

    async def increment_click(self, db: AsyncSession, banner_id: int) -> None:
        """
        增加点击次数

        :param db: 数据库会话
        :param banner_id: 轮播图 ID
        :return:
        """
        banner = await self.get(db, banner_id)
        if banner:
            await self.update_model(db, banner_id, {'click_count': banner.click_count + 1})


banner_dao: CRUDBanner = CRUDBanner(Banner)
