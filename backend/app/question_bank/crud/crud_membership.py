#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.question_bank.model.user import UserMembership
from backend.app.question_bank.schema.membership import CreateMembershipParam, UpdateMembershipParam
from backend.utils.timezone import timezone


class CRUDMembership(CRUDPlus[UserMembership]):
    async def create(self, db: AsyncSession, obj: CreateMembershipParam) -> None:
        """创建会员权益"""
        await self.create_model(db, obj)

    async def update(self, db: AsyncSession, membership_id: int, obj: UpdateMembershipParam) -> int:
        """更新会员权益"""
        return await self.update_model(db, membership_id, obj)

    async def delete(self, db: AsyncSession, membership_ids: list[int]) -> int:
        """删除会员权益"""
        return await self.delete_model_by_column(db, allow_multiple=True, id__in=membership_ids)

    async def get_list(
        self, db: AsyncSession, user_id: int | None = None, category: int | None = None, status: int | None = None
    ) -> list[UserMembership]:
        """
        获取会员权益列表

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param category: 会员分类
        :param status: 状态
        :return: 会员权益列表
        """
        where_list = []
        if user_id is not None:
            where_list.append(UserMembership.user_id == user_id)
        if category is not None:
            where_list.append(UserMembership.category == category)
        if status is not None:
            where_list.append(UserMembership.status == status)

        return await self.select_models(db, *where_list)

    async def check_user_access(
        self, db: AsyncSession, user_id: int, category: int, res_id: int | None = None
    ) -> bool:
        """
        检查用户是否有访问权限

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param category: 会员分类（1=题库 2=词库 3=资料包）
        :param res_id: 资源 ID（题库 ID、章节所属题库 ID 等）
        :return: 是否有权限
        """
        now = timezone.now()

        # 查询用户的有效会员权益
        stmt = (
            select(UserMembership)
            .where(
                UserMembership.user_id == user_id,
                UserMembership.status == 1,
                UserMembership.start_time <= now,
                UserMembership.end_time >= now,
            )
            .where(
                (UserMembership.category == 0)  # 全部分类
                | (UserMembership.category == category)  # 指定分类
            )
        )

        result = await db.execute(stmt)
        memberships = result.scalars().all()

        if not memberships:
            return False

        # 检查是否有全部分类的会员
        for membership in memberships:
            if membership.category == 0:
                return True

        # 检查是否有整个分类的会员
        for membership in memberships:
            if membership.category == category and membership.res_type == 'category':
                return True

        # 检查是否有指定资源的会员
        if res_id is not None:
            for membership in memberships:
                if (
                    membership.category == category
                    and membership.res_type == 'single'
                    and membership.res_id == res_id
                ):
                    return True

        return False

    async def get_user_active_memberships(
        self, db: AsyncSession, user_id: int, category: int | None = None
    ) -> list[UserMembership]:
        """
        获取用户的有效会员权益列表

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param category: 会员分类（可选）
        :return: 会员权益列表
        """
        now = timezone.now()

        stmt = select(UserMembership).where(
            UserMembership.user_id == user_id,
            UserMembership.status == 1,
            UserMembership.start_time <= now,
            UserMembership.end_time >= now,
        )

        if category is not None:
            stmt = stmt.where(
                (UserMembership.category == 0) | (UserMembership.category == category)
            )

        result = await db.execute(stmt)
        return list(result.scalars().all())


membership_dao = CRUDMembership(UserMembership)
