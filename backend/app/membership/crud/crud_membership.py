#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from collections.abc import Sequence

from sqlalchemy import Select, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.membership.model.membership import UserMembership
from backend.utils.timezone import timezone


class CRUDUserMembership(CRUDPlus[UserMembership]):
    """用户会员状态数据库操作类"""

    async def get_active_by_user(self, db: AsyncSession, user_id: int) -> Sequence[UserMembership]:
        """
        获取用户当前生效会员

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
            .order_by(self.model.tier_weight.desc(), self.model.valid_to.desc())
        )
        result = await db.execute(stmt)
        return result.scalars().all()

    async def get_max_active_weight(self, db: AsyncSession, user_id: int) -> int:
        """
        获取用户当前最高会员等级权重

        :param db: 数据库会话
        :param user_id: 用户 ID
        :return:
        """
        now = timezone.now()
        stmt: Select = select(func.max(self.model.tier_weight)).where(
            self.model.user_id == user_id,
            self.model.status == 1,
            self.model.valid_to > now,
        )
        result = await db.execute(stmt)
        max_weight = result.scalar_one_or_none()
        return int(max_weight or 0)

    async def get_by_user_and_tier(
        self,
        db: AsyncSession,
        user_id: int,
        tier_id: int,
        *,
        for_update: bool = False,
    ) -> UserMembership | None:
        """
        根据用户与等级获取会员状态

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param tier_id: 等级 ID
        :param for_update: 是否加行锁
        :return:
        """
        stmt = select(self.model).where(
            self.model.user_id == user_id,
            self.model.tier_id == tier_id,
        )
        if for_update:
            stmt = stmt.with_for_update()
        result = await db.execute(stmt)
        return result.scalars().first()

    async def get_by_user_and_family(
        self,
        db: AsyncSession,
        user_id: int,
        family_code: str,
        *,
        for_update: bool = False,
    ) -> UserMembership | None:
        """
        根据用户与族群获取会员状态

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param family_code: 族群编码
        :param for_update: 是否加行锁
        :return:
        """
        stmt = select(self.model).where(
            self.model.user_id == user_id,
            self.model.family_code == family_code,
        )
        if for_update:
            stmt = stmt.with_for_update()
        result = await db.execute(stmt)
        return result.scalars().first()

    async def get_expired(self, db: AsyncSession) -> Sequence[UserMembership]:
        """
        获取已过期但状态仍生效的数据

        :param db: 数据库会话
        :return:
        """
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
        批量标记过期

        :param db: 数据库会话
        :param ids: 记录 ID 列表
        :return:
        """
        if not ids:
            return
        stmt = update(self.model).where(self.model.id.in_(ids)).values(status=2)
        await db.execute(stmt)


user_membership_dao: CRUDUserMembership = CRUDUserMembership(UserMembership)
