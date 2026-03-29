#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from collections.abc import Sequence

from sqlalchemy import Select, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.membership.model.tier import MembershipTier


class CRUDMembershipTier(CRUDPlus[MembershipTier]):
    """会员等级数据库操作类"""

    async def get_select(
        self,
        *,
        name: str | None = None,
        status: int | None = None,
        family_code: str | None = None,
    ) -> Select:
        """
        获取会员等级分页查询语句

        :param name: 等级名称
        :param status: 状态
        :param family_code: 族群编码
        :return:
        """
        filters = {}
        if name is not None:
            filters['name__like'] = name
        if status is not None:
            filters['status__eq'] = status
        if family_code is not None:
            filters['family_code__eq'] = family_code
        return await self.select_order('sort', 'asc', **filters)

    async def get_by_code(self, db: AsyncSession, code: str) -> MembershipTier | None:
        """
        根据编码获取等级

        :param db: 数据库会话
        :param code: 等级编码
        :return:
        """
        return await self.select_model_by_column(db, code__eq=code)

    async def get_by_weight(self, db: AsyncSession, weight: int) -> MembershipTier | None:
        """
        根据权重获取等级

        :param db: 数据库会话
        :param weight: 权重
        :return:
        """
        return await self.select_model_by_column(db, weight__eq=weight)

    async def get_by_family_grade(self, db: AsyncSession, family_code: str, grade: int) -> MembershipTier | None:
        """
        根据族群与等级获取会员等级

        :param db: 数据库会话
        :param family_code: 族群编码
        :param grade: 族群内等级
        :return:
        """
        return await self.select_model_by_column(db, family_code__eq=family_code, grade__eq=grade)

    async def get_default(self, db: AsyncSession) -> MembershipTier | None:
        """
        获取默认等级

        :param db: 数据库会话
        :return:
        """
        return await self.select_model_by_column(db, is_default__eq=True)

    async def get_active_tiers(self, db: AsyncSession) -> Sequence[MembershipTier]:
        """
        获取启用等级

        :param db: 数据库会话
        :return:
        """
        stmt = (
            select(self.model)
            .where(self.model.status == 1)
            .order_by(self.model.sort.asc(), self.model.weight.asc())
        )
        result = await db.execute(stmt)
        return result.scalars().all()

    async def get_highest_tier_by_exp(self, db: AsyncSession, *, family_code: str, exp: int) -> MembershipTier | None:
        """
        根据经验获取族群内可达最高等级

        :param db: 数据库会话
        :param family_code: 族群编码
        :param exp: 当前经验
        :return:
        """
        stmt = (
            select(self.model)
            .where(
                self.model.family_code == family_code,
                self.model.status == 1,
                self.model.exp_required <= exp,
            )
            .order_by(self.model.grade.desc(), self.model.weight.desc())
            .limit(1)
        )
        result = await db.execute(stmt)
        return result.scalars().first()

    async def get_next_tier(
        self,
        db: AsyncSession,
        *,
        family_code: str,
        current_grade: int,
    ) -> MembershipTier | None:
        """
        获取族群内下一个等级

        :param db: 数据库会话
        :param family_code: 族群编码
        :param current_grade: 当前等级
        :return:
        """
        stmt = (
            select(self.model)
            .where(
                self.model.family_code == family_code,
                self.model.status == 1,
                self.model.grade > current_grade,
            )
            .order_by(self.model.grade.asc(), self.model.weight.asc())
            .limit(1)
        )
        result = await db.execute(stmt)
        return result.scalars().first()

    async def clear_default(self, db: AsyncSession) -> None:
        """
        清空默认标记

        :param db: 数据库会话
        :return:
        """
        stmt = update(self.model).where(self.model.is_default.is_(True)).values(is_default=False)
        await db.execute(stmt)


membership_tier_dao: CRUDMembershipTier = CRUDMembershipTier(MembershipTier)
