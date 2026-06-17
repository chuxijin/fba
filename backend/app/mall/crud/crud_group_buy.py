#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.mall.model.group_buy import GroupBuyActivity, GroupBuyLadderPrice
from backend.app.mall.schema.group_buy import (
    CreateGroupBuyActivityParam,
    CreateGroupBuyLadderPriceParam,
    GroupBuyActivityBase,
    UpdateGroupBuyActivityParam,
)


class CRUDGroupBuyActivity(CRUDPlus[GroupBuyActivity]):
    """拼团活动数据库操作类"""

    async def get(self, db: AsyncSession, activity_id: int) -> GroupBuyActivity | None:
        """
        获取活动详情

        :param db: 数据库会话
        :param activity_id: 活动 ID
        :return:
        """
        return await self.select_model(db, activity_id)

    async def get_with_prices(self, db: AsyncSession, activity_id: int) -> GroupBuyActivity | None:
        """
        获取活动详情（含阶梯价格）

        :param db: 数据库会话
        :param activity_id: 活动 ID
        :return:
        """
        stmt = (
            select(GroupBuyActivity)
            .where(GroupBuyActivity.id == activity_id)
            .options(selectinload(GroupBuyActivity.ladder_prices))
        )
        result = await db.execute(stmt)
        return result.unique().scalars().first()

    async def get_active_activities(self, db: AsyncSession, limit: int = 20) -> list[GroupBuyActivity]:
        """
        获取进行中的活动列表

        :param db: 数据库会话
        :param limit: 数量限制
        :return:
        """
        from backend.utils.timezone import timezone

        now = timezone.now()
        stmt = (
            select(GroupBuyActivity)
            .where(
                GroupBuyActivity.status == 'active',
                GroupBuyActivity.start_time <= now,
                GroupBuyActivity.end_time >= now,
            )
            .order_by(GroupBuyActivity.created_time.desc())
            .limit(limit)
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def get_by_product(self, db: AsyncSession, product_id: int) -> list[GroupBuyActivity]:
        """
        获取商品的拼团活动列表

        :param db: 数据库会话
        :param product_id: 商品 ID
        :return:
        """
        filters = {'product_id': product_id}
        return await self.select_models(db, **filters)

    async def create(self, db: AsyncSession, obj_in: CreateGroupBuyActivityParam, user_id: int) -> GroupBuyActivity:
        """
        创建拼团活动

        :param db: 数据库会话
        :param obj_in: 创建参数
        :param user_id: 创建者 ID
        :return:
        """
        activity_base = GroupBuyActivityBase(**obj_in.model_dump(exclude={'ladder_prices'}))
        activity = await self.create_model(db, activity_base, created_by=user_id)

        for ladder_price in obj_in.ladder_prices:
            await group_buy_ladder_price_dao.create_model(db, ladder_price, activity_id=activity.id, created_by=user_id)

        return activity

    async def update(self, db: AsyncSession, activity_id: int, obj_in: UpdateGroupBuyActivityParam) -> int:
        """
        更新拼团活动

        :param db: 数据库会话
        :param activity_id: 活动 ID
        :param obj_in: 更新参数
        :return:
        """
        update_data = obj_in.model_dump(exclude_unset=True)
        return await self.update_model(db, activity_id, update_data)

    async def deduct_stock(self, db: AsyncSession, activity_id: int, quantity: int) -> bool:
        """
        扣减活动库存（原子更新，防止超卖）

        :param db: 数据库会话
        :param activity_id: 活动 ID
        :param quantity: 扣减数量
        :return:
        """
        from sqlalchemy import update

        stmt = (
            update(GroupBuyActivity)
            .where(
                GroupBuyActivity.id == activity_id,
                GroupBuyActivity.stock >= quantity,
            )
            .values(stock=GroupBuyActivity.stock - quantity)
        )
        result = await db.execute(stmt)
        await db.commit()
        return result.rowcount > 0


class CRUDGroupBuyLadderPrice(CRUDPlus[GroupBuyLadderPrice]):
    """拼团阶梯价格数据库操作类"""

    async def get(self, db: AsyncSession, price_id: int) -> GroupBuyLadderPrice | None:
        """
        获取阶梯价格详情

        :param db: 数据库会话
        :param price_id: 价格 ID
        :return:
        """
        return await self.select_model(db, price_id)

    async def get_by_activity(self, db: AsyncSession, activity_id: int) -> list[GroupBuyLadderPrice]:
        """
        获取活动的阶梯价格列表

        :param db: 数据库会话
        :param activity_id: 活动 ID
        :return:
        """
        filters = {'activity_id': activity_id}
        return await self.select_models(db, **filters)

    async def get_by_people_count(
        self, db: AsyncSession, activity_id: int, people_count: int
    ) -> GroupBuyLadderPrice | None:
        """
        获取指定人数的阶梯价格

        :param db: 数据库会话
        :param activity_id: 活动 ID
        :param people_count: 成团人数
        :return:
        """
        stmt = select(GroupBuyLadderPrice).where(
            GroupBuyLadderPrice.activity_id == activity_id,
            GroupBuyLadderPrice.people_count == people_count,
        )
        result = await db.execute(stmt)
        return result.scalars().first()

    async def create(
        self, db: AsyncSession, obj_in: CreateGroupBuyLadderPriceParam, activity_id: int, user_id: int
    ) -> GroupBuyLadderPrice:
        """
        创建阶梯价格

        :param db: 数据库会话
        :param obj_in: 创建参数
        :param activity_id: 活动 ID
        :param user_id: 创建者 ID
        :return:
        """
        return await self.create_model(db, obj_in, activity_id=activity_id, created_by=user_id)


group_buy_activity_dao = CRUDGroupBuyActivity(GroupBuyActivity)
group_buy_ladder_price_dao = CRUDGroupBuyLadderPrice(GroupBuyLadderPrice)
