#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.admin.model import user_role
from backend.utils.timezone import timezone


@dataclass(slots=True)
class UserRoleExpiryRecord:
    """用户角色有效期记录"""

    id: int
    user_id: int
    role_id: int
    valid_from: datetime | None
    valid_to: datetime | None
    status: int


class CRUDUserRoleExpiry:
    """用户角色有效期数据库操作类"""

    @staticmethod
    def _build_record(row) -> UserRoleExpiryRecord:  # noqa: ANN001
        mapping = row._mapping
        return UserRoleExpiryRecord(
            id=mapping['id'],
            user_id=mapping['user_id'],
            role_id=mapping['role_id'],
            valid_from=mapping['valid_from'],
            valid_to=mapping['valid_to'],
            status=mapping['status'],
        )

    async def get_by_user_and_role(self, db: AsyncSession, user_id: int, role_id: int) -> UserRoleExpiryRecord | None:
        """
        根据用户 ID 和角色 ID 获取有效期记录

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param role_id: 角色 ID
        :return:
        """
        stmt = select(
            user_role.c.id,
            user_role.c.user_id,
            user_role.c.role_id,
            user_role.c.valid_from,
            user_role.c.valid_to,
            user_role.c.status,
        ).where(
            user_role.c.user_id == user_id,
            user_role.c.role_id == role_id,
        )
        result = await db.execute(stmt)
        row = result.first()
        if not row:
            return None
        return self._build_record(row)

    async def get_active_role_ids(self, db: AsyncSession, user_id: int) -> set[int] | None:
        """
        获取用户当前有效的角色 ID 集合

        :param db: 数据库会话
        :param user_id: 用户 ID
        :return:
        """
        stmt = select(
            user_role.c.role_id,
            user_role.c.valid_from,
            user_role.c.valid_to,
            user_role.c.status,
        ).where(user_role.c.user_id == user_id)
        result = await db.execute(stmt)
        rows = result.fetchall()
        if not rows:
            return None

        now = timezone.now()
        active_ids: set[int] = set()
        for row in rows:
            mapping = row._mapping
            status = int(mapping['status']) if mapping['status'] is not None else 1
            valid_from = mapping['valid_from']
            valid_to = mapping['valid_to']
            if status != 1:
                continue
            if valid_from and now < valid_from:
                continue
            if valid_to and now > valid_to:
                continue
            active_ids.add(mapping['role_id'])

        return active_ids

    async def get_expired(self, db: AsyncSession) -> Sequence[UserRoleExpiryRecord]:
        """
        获取所有已过期但状态仍为正常的记录

        :param db: 数据库会话
        :return:
        """
        now = timezone.now()
        stmt = select(
            user_role.c.id,
            user_role.c.user_id,
            user_role.c.role_id,
            user_role.c.valid_from,
            user_role.c.valid_to,
            user_role.c.status,
        ).where(
            user_role.c.status == 1,
            user_role.c.valid_to.is_not(None),
            user_role.c.valid_to <= now,
        )
        result = await db.execute(stmt)
        rows = result.fetchall()
        return [self._build_record(row) for row in rows]

    async def mark_expired(self, db: AsyncSession, ids: list[int]) -> None:
        """
        批量标记为已过期

        :param db: 数据库会话
        :param ids: 记录 ID 列表
        :return:
        """
        if not ids:
            return
        stmt = update(user_role).where(user_role.c.id.in_(ids)).values(status=2)
        await db.execute(stmt)

    async def get_by_user(self, db: AsyncSession, user_id: int) -> Sequence[UserRoleExpiryRecord]:
        """
        获取用户的所有有效期记录

        :param db: 数据库会话
        :param user_id: 用户 ID
        :return:
        """
        stmt = select(
            user_role.c.id,
            user_role.c.user_id,
            user_role.c.role_id,
            user_role.c.valid_from,
            user_role.c.valid_to,
            user_role.c.status,
        ).where(
            user_role.c.user_id == user_id,
        ).order_by(
            user_role.c.valid_to.desc().nulls_last(),
            user_role.c.id.desc(),
        )
        result = await db.execute(stmt)
        rows = result.fetchall()
        return [self._build_record(row) for row in rows]

    async def upsert_expiry(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        role_id: int,
        valid_from: datetime | None,
        valid_to: datetime | None,
        status: int = 1,
    ) -> None:
        """
        写入或更新有效期记录

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param role_id: 角色 ID
        :param valid_from: 有效期开始
        :param valid_to: 有效期结束
        :param status: 状态
        :return:
        """
        existing = await self.get_by_user_and_role(db, user_id, role_id)
        if existing:
            stmt = (
                update(user_role)
                .where(user_role.c.id == existing.id)
                .values(valid_from=valid_from, valid_to=valid_to, status=status)
            )
            await db.execute(stmt)
            return

        stmt = insert(user_role).values(
            user_id=user_id,
            role_id=role_id,
            valid_from=valid_from,
            valid_to=valid_to,
            status=status,
        )
        await db.execute(stmt)


user_role_expiry_dao: CRUDUserRoleExpiry = CRUDUserRoleExpiry()
