#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.mall.model.group_buy_team import GroupBuyMember, GroupBuyTeam


class CRUDGroupBuyTeam(CRUDPlus[GroupBuyTeam]):
    """拼团团队数据库操作类"""

    async def get(self, db: AsyncSession, team_id: int) -> GroupBuyTeam | None:
        """
        获取团队详情

        :param db: 数据库会话
        :param team_id: 团队 ID
        :return:
        """
        return await self.select_model(db, team_id)

    async def get_with_members(self, db: AsyncSession, team_id: int) -> GroupBuyTeam | None:
        """
        获取团队详情（含成员列表）

        :param db: 数据库会话
        :param team_id: 团队 ID
        :return:
        """
        stmt = (
            select(GroupBuyTeam)
            .where(GroupBuyTeam.id == team_id)
            .options(selectinload(GroupBuyTeam.members))
        )
        result = await db.execute(stmt)
        return result.unique().scalars().first()

    async def get_by_activity(self, db: AsyncSession, activity_id: int, status: str | None = None) -> list[GroupBuyTeam]:
        """
        获取活动的团队列表

        :param db: 数据库会话
        :param activity_id: 活动 ID
        :param status: 团队状态
        :return:
        """
        filters = {'activity_id': activity_id}
        if status:
            filters['status'] = status
        return await self.select_models(db, **filters)

    async def get_by_user(self, db: AsyncSession, user_id: int) -> list[GroupBuyTeam]:
        """
        获取用户参与的团队列表

        :param db: 数据库会话
        :param user_id: 用户 ID
        :return:
        """
        stmt = (
            select(GroupBuyTeam)
            .join(GroupBuyMember, GroupBuyMember.team_id == GroupBuyTeam.id)
            .where(GroupBuyMember.user_id == user_id)
            .order_by(GroupBuyTeam.created_time.desc())
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def get_pending_teams(self, db: AsyncSession, activity_id: int, limit: int = 20) -> list[GroupBuyTeam]:
        """
        获取进行中的团队列表

        :param db: 数据库会话
        :param activity_id: 活动 ID
        :param limit: 数量限制
        :return:
        """
        from backend.utils.timezone import timezone
        now = timezone.now()
        stmt = (
            select(GroupBuyTeam)
            .where(
                GroupBuyTeam.activity_id == activity_id,
                GroupBuyTeam.status == 'pending',
                GroupBuyTeam.expire_time > now,
            )
            .order_by(GroupBuyTeam.created_time.desc())
            .limit(limit)
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def get_expired_teams(self, db: AsyncSession, limit: int = 100) -> list[GroupBuyTeam]:
        """
        获取已过期但未处理的团队列表

        :param db: 数据库会话
        :param limit: 数量限制
        :return:
        """
        from backend.utils.timezone import timezone
        now = timezone.now()
        stmt = (
            select(GroupBuyTeam)
            .where(
                GroupBuyTeam.status == 'pending',
                GroupBuyTeam.expire_time <= now,
            )
            .order_by(GroupBuyTeam.expire_time.asc())
            .limit(limit)
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def increment_people(self, db: AsyncSession, team_id: int) -> int:
        """
        增加团队人数

        :param db: 数据库会话
        :param team_id: 团队 ID
        :return:
        """
        team = await self.get(db, team_id)
        if not team:
            return 0
        new_count = team.current_people + 1
        return await self.update_model(db, team_id, {'current_people': new_count})


class CRUDGroupBuyMember(CRUDPlus[GroupBuyMember]):
    """拼团成员数据库操作类"""

    async def get(self, db: AsyncSession, member_id: int) -> GroupBuyMember | None:
        """
        获取成员详情

        :param db: 数据库会话
        :param member_id: 成员 ID
        :return:
        """
        return await self.select_model(db, member_id)

    async def get_by_team(self, db: AsyncSession, team_id: int) -> list[GroupBuyMember]:
        """
        获取团队的成员列表

        :param db: 数据库会话
        :param team_id: 团队 ID
        :return:
        """
        filters = {'team_id': team_id}
        return await self.select_models(db, **filters)

    async def get_by_user_and_team(self, db: AsyncSession, user_id: int, team_id: int) -> GroupBuyMember | None:
        """
        获取用户在团队中的成员记录

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param team_id: 团队 ID
        :return:
        """
        stmt = select(GroupBuyMember).where(
            GroupBuyMember.user_id == user_id,
            GroupBuyMember.team_id == team_id,
        )
        result = await db.execute(stmt)
        return result.scalars().first()

    async def check_user_in_activity(self, db: AsyncSession, user_id: int, activity_id: int) -> bool:
        """
        检查用户是否已参与该活动的拼团

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param activity_id: 活动 ID
        :return:
        """
        stmt = select(GroupBuyMember).where(
            GroupBuyMember.user_id == user_id,
            GroupBuyMember.activity_id == activity_id,
        )
        result = await db.execute(stmt)
        return result.scalars().first() is not None


group_buy_team_dao = CRUDGroupBuyTeam(GroupBuyTeam)
group_buy_member_dao = CRUDGroupBuyMember(GroupBuyMember)
