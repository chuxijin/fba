#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from collections.abc import Sequence

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.membership.model.membership import UserMembership
from backend.utils.timezone import timezone


class CRUDUserMembership(CRUDPlus[UserMembership]):
    """用户会员记录数据库操作类"""

    async def get_by_user(self, db: AsyncSession, user_id: int) -> Sequence[UserMembership]:
        """
        获取用户所有会员记录

        :param db: 数据库会话
        :param user_id: 用户 ID
        :return:
        """
        stmt = (
            select(self.model)
            .where(self.model.user_id == user_id)
            .order_by(self.model.created_time.desc())
        )
        result = await db.execute(stmt)
        return result.scalars().all()

    async def get_active_by_user(self, db: AsyncSession, user_id: int) -> Sequence[UserMembership]:
        """
        获取用户当前生效的会员

        :param db: 数据库会话
        :param user_id: 用户 ID
        :return:
        """
        now = timezone.now()
        stmt = (
            select(self.model)
            .where(
                self.model.user_id == user_id,
                self.model.status == 1,
                self.model.valid_to > now,
            )
            .order_by(self.model.level.desc())
        )
        result = await db.execute(stmt)
        return result.scalars().all()

    async def get_by_user_and_plan(
        self, db: AsyncSession, user_id: int, plan_id: int
    ) -> UserMembership | None:
        """
        根据用户 ID 和计划 ID 获取记录

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param plan_id: 会员计划 ID
        :return:
        """
        return await self.select_model_by_column(db, user_id__eq=user_id, plan_id__eq=plan_id)

    async def get_expired(self, db: AsyncSession) -> Sequence[UserMembership]:
        """获取已过期但状态仍为生效中的记录"""
        now = timezone.now()
        stmt = (
            select(self.model)
            .where(
                self.model.status == 1,
                self.model.valid_to.isnot(None),
                self.model.valid_to <= now,
            )
        )
        result = await db.execute(stmt)
        return result.scalars().all()

    async def mark_expired(self, db: AsyncSession, ids: list[int]) -> None:
        """
        批量标记为已过期

        :param db: 数据库会话
        :param ids: 记录 ID 列表
        :return:
        """
        if not ids:
            return
        stmt = update(self.model).where(self.model.id.in_(ids)).values(status=2)
        await db.execute(stmt)


user_membership_dao: CRUDUserMembership = CRUDUserMembership(UserMembership)
