#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.pomodoro.model.achievement import PomodoroAchievementRule, PomodoroUserAchievement


class CRUDPomodoroAchievementRule(CRUDPlus[PomodoroAchievementRule]):
    """番茄成就规则数据库操作类"""

    async def get_by_code(self, db: AsyncSession, code: str) -> PomodoroAchievementRule | None:
        """
        通过编码获取成就规则

        :param db: 数据库会话
        :param code: 规则编码
        :return:
        """
        return await self.select_model_by_column(db, code__eq=code)

    async def get_enabled_rules(self, db: AsyncSession) -> list[PomodoroAchievementRule]:
        """
        获取启用的成就规则

        :param db: 数据库会话
        :return:
        """
        stmt = (
            select(PomodoroAchievementRule)
            .where(PomodoroAchievementRule.is_enabled.is_(True))
            .order_by(PomodoroAchievementRule.sort.asc(), PomodoroAchievementRule.threshold_value.asc())
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())


class CRUDPomodoroUserAchievement(CRUDPlus[PomodoroUserAchievement]):
    """番茄用户成就数据库操作类"""

    async def get_by_user(self, db: AsyncSession, user_id: int) -> list[PomodoroUserAchievement]:
        """
        获取用户成就记录

        :param db: 数据库会话
        :param user_id: 用户 ID
        :return:
        """
        stmt = select(PomodoroUserAchievement).where(PomodoroUserAchievement.user_id == user_id)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def get_by_user_and_rule(
        self,
        db: AsyncSession,
        user_id: int,
        rule_id: int,
    ) -> PomodoroUserAchievement | None:
        """
        获取用户指定成就记录

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param rule_id: 成就规则 ID
        :return:
        """
        return await self.select_model_by_column(db, user_id__eq=user_id, rule_id__eq=rule_id)


pomodoro_achievement_rule_dao: CRUDPomodoroAchievementRule = CRUDPomodoroAchievementRule(
    PomodoroAchievementRule
)
pomodoro_user_achievement_dao: CRUDPomodoroUserAchievement = CRUDPomodoroUserAchievement(
    PomodoroUserAchievement
)
