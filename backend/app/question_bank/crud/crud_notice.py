#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.question_bank.model import Notice
from backend.app.question_bank.schema.notice import CreateNoticeParam, UpdateNoticeParam
from backend.utils.timezone import timezone


class CRUDNotice(CRUDPlus[Notice]):
    """通知栏数据库操作类"""

    async def get(self, db: AsyncSession, notice_id: int) -> Notice | None:
        """
        获取通知详情

        :param db: 数据库会话
        :param notice_id: 通知 ID
        :return:
        """
        return await self.select_model_by_column(db, id=notice_id)

    async def get_all(
        self,
        db: AsyncSession,
        status: int | None = None,
        notice_type: str | None = None,
        scene: str | None = None,
    ) -> Sequence[Notice]:
        """
        获取所有通知

        :param db: 数据库会话
        :param status: 状态筛选
        :param notice_type: 通知类型筛选
        :param scene: 展示场景筛选
        :return:
        """
        filters = {}
        if status is not None:
            filters['status'] = status
        if notice_type is not None:
            filters['notice_type'] = notice_type
        if scene is not None:
            filters['scene'] = scene

        stmt = select(self.model).filter_by(**filters).order_by(self.model.sort, self.model.id.desc())
        result = await db.execute(stmt)
        return result.scalars().all()

    async def get_active_list(self, db: AsyncSession, scene: str | None = None) -> Sequence[Notice]:
        """
        获取启用且在有效期内的通知列表

        :param db: 数据库会话
        :param scene: 展示场景筛选
        :return:
        """
        now = timezone.now()
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

    async def create(self, db: AsyncSession, obj_in: CreateNoticeParam) -> None:
        """
        创建通知

        :param db: 数据库会话
        :param obj_in: 创建参数
        :return:
        """
        await self.create_model(db, obj_in)

    async def update(self, db: AsyncSession, notice_id: int, obj_in: UpdateNoticeParam) -> int:
        """
        更新通知

        :param db: 数据库会话
        :param notice_id: 通知 ID
        :param obj_in: 更新参数
        :return:
        """
        return await self.update_model(db, notice_id, obj_in)

    async def delete(self, db: AsyncSession, notice_id: int) -> int:
        """
        删除通知

        :param db: 数据库会话
        :param notice_id: 通知 ID
        :return:
        """
        return await self.delete_model(db, notice_id)


notice_dao: CRUDNotice = CRUDNotice(Notice)
