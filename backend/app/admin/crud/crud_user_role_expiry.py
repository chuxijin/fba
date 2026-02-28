#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from collections.abc import Sequence

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.admin.model.user_role_expiry import UserRoleExpiry
from backend.utils.timezone import timezone


class CRUDUserRoleExpiry(CRUDPlus[UserRoleExpiry]):
    """用户角色有效期数据库操作类"""

    async def get_by_user_and_role(self, db: AsyncSession, user_id: int, role_id: int) -> UserRoleExpiry | None:
        """
        根据用户 ID 和角色 ID 获取有效期记录

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param role_id: 角色 ID
        :return:
        """
        return await self.select_model_by_column(db, user_id__eq=user_id, role_id__eq=role_id)

    async def get_active_role_ids(self, db: AsyncSession, user_id: int) -> set[int] | None:
        """
        获取用户当前有效的角色 ID 集合

        如果用户没有任何有效期记录，返回 None（表示所有角色均为永久有效）。
        如果有记录，返回当前有效的角色 ID 集合（含无有效期记录的永久角色）。

        :param db: 数据库会话
        :param user_id: 用户 ID
        :return:
        """
        stmt = select(self.model).where(self.model.user_id == user_id)
        result = await db.execute(stmt)
        records = result.scalars().all()

        if not records:
            return None

        now = timezone.now()
        active_ids = set()
        for record in records:
            if record.status != 1:
                continue
            if record.valid_from and now < record.valid_from:
                continue
            if record.valid_to and now > record.valid_to:
                continue
            active_ids.add(record.role_id)

        return active_ids

    async def get_expired(self, db: AsyncSession) -> Sequence[UserRoleExpiry]:
        """获取所有已过期但状态仍为正常的记录"""
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

    async def get_by_user(self, db: AsyncSession, user_id: int) -> Sequence[UserRoleExpiry]:
        """
        获取用户的所有有效期记录

        :param db: 数据库会话
        :param user_id: 用户 ID
        :return:
        """
        stmt = select(self.model).where(self.model.user_id == user_id).order_by(self.model.created_time.desc())
        result = await db.execute(stmt)
        return result.scalars().all()


user_role_expiry_dao: CRUDUserRoleExpiry = CRUDUserRoleExpiry(UserRoleExpiry)
