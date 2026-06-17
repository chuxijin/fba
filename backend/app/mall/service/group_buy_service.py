#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import logging

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.mall.crud.crud_group_buy import group_buy_activity_dao, group_buy_ladder_price_dao
from backend.app.mall.crud.crud_product import product_dao, product_sku_dao
from backend.app.mall.model.group_buy import GroupBuyActivity, GroupBuyLadderPrice
from backend.app.mall.schema.group_buy import (
    CreateGroupBuyActivityParam,
    CreateGroupBuyLadderPriceParam,
    UpdateGroupBuyActivityParam,
)
from backend.common.exception import errors

log = logging.getLogger(__name__)


class GroupBuyService:
    """拼团活动服务类"""

    @staticmethod
    async def get_activity(*, db: AsyncSession, activity_id: int, with_prices: bool = False) -> GroupBuyActivity:
        """
        获取拼团活动详情

        :param db: 数据库会话
        :param activity_id: 活动 ID
        :param with_prices: 是否包含阶梯价格
        :return:
        """
        if with_prices:
            activity = await group_buy_activity_dao.get_with_prices(db, activity_id)
        else:
            activity = await group_buy_activity_dao.get(db, activity_id)
        if not activity:
            raise errors.NotFoundError(msg='拼团活动不存在')
        return activity

    @staticmethod
    async def get_activity_list(*, db: AsyncSession, product_id: int | None = None) -> list[GroupBuyActivity]:
        """
        获取拼团活动列表

        :param db: 数据库会话
        :param product_id: 商品 ID
        :return:
        """
        if product_id:
            return await group_buy_activity_dao.get_by_product(db, product_id)
        return await group_buy_activity_dao.get_active_activities(db)

    @staticmethod
    async def create_activity(*, db: AsyncSession, obj: CreateGroupBuyActivityParam, user_id: int) -> GroupBuyActivity:
        """
        创建拼团活动

        :param db: 数据库会话
        :param obj: 创建参数
        :param user_id: 创建者 ID
        :return:
        """
        product = await product_dao.get(db, obj.product_id)
        if not product:
            raise errors.NotFoundError(msg='商品不存在')

        sku = await product_sku_dao.get(db, obj.sku_id)
        if not sku or sku.product_id != obj.product_id:
            raise errors.NotFoundError(msg='SKU 不存在或不属于该商品')

        if obj.start_time >= obj.end_time:
            raise errors.ForbiddenError(msg='活动开始时间必须早于结束时间')

        if obj.min_people > obj.max_people:
            raise errors.ForbiddenError(msg='最小成团人数不能大于最大成团人数')

        people_counts = [lp.people_count for lp in obj.ladder_prices]
        if len(people_counts) != len(set(people_counts)):
            raise errors.ForbiddenError(msg='阶梯价格中存在重复的成团人数')

        for lp in obj.ladder_prices:
            if lp.people_count < obj.min_people or lp.people_count > obj.max_people:
                raise errors.ForbiddenError(msg=f'阶梯价格人数 {lp.people_count} 超出活动人数范围')

        return await group_buy_activity_dao.create(db, obj, user_id)

    @staticmethod
    async def update_activity(*, db: AsyncSession, activity_id: int, obj: UpdateGroupBuyActivityParam) -> int:
        """
        更新拼团活动

        :param db: 数据库会话
        :param activity_id: 活动 ID
        :param obj: 更新参数
        :return:
        """
        activity = await group_buy_activity_dao.get(db, activity_id)
        if not activity:
            raise errors.NotFoundError(msg='拼团活动不存在')

        if obj.start_time and obj.end_time and obj.start_time >= obj.end_time:
            raise errors.ForbiddenError(msg='活动开始时间必须早于结束时间')

        return await group_buy_activity_dao.update(db, activity_id, obj)

    @staticmethod
    async def delete_activity(*, db: AsyncSession, activity_id: int) -> int:
        """
        删除拼团活动

        :param db: 数据库会话
        :param activity_id: 活动 ID
        :return:
        """
        activity = await group_buy_activity_dao.get(db, activity_id)
        if not activity:
            raise errors.NotFoundError(msg='拼团活动不存在')

        if activity.status == 'active':
            raise errors.ForbiddenError(msg='进行中的活动无法删除')

        return await group_buy_activity_dao.delete_model(db, activity_id)

    @staticmethod
    async def get_ladder_price_list(*, db: AsyncSession, activity_id: int) -> list[GroupBuyLadderPrice]:
        """
        获取活动的阶梯价格列表

        :param db: 数据库会话
        :param activity_id: 活动 ID
        :return:
        """
        activity = await group_buy_activity_dao.get(db, activity_id)
        if not activity:
            raise errors.NotFoundError(msg='拼团活动不存在')
        return await group_buy_ladder_price_dao.get_by_activity(db, activity_id)

    @staticmethod
    async def add_ladder_price(
        *, db: AsyncSession, activity_id: int, obj: CreateGroupBuyLadderPriceParam, user_id: int
    ) -> GroupBuyLadderPrice:
        """
        添加阶梯价格

        :param db: 数据库会话
        :param activity_id: 活动 ID
        :param obj: 创建参数
        :param user_id: 创建者 ID
        :return:
        """
        activity = await group_buy_activity_dao.get(db, activity_id)
        if not activity:
            raise errors.NotFoundError(msg='拼团活动不存在')

        if obj.people_count < activity.min_people or obj.people_count > activity.max_people:
            raise errors.ForbiddenError(msg='成团人数超出活动人数范围')

        existing = await group_buy_ladder_price_dao.get_by_people_count(db, activity_id, obj.people_count)
        if existing:
            raise errors.ForbiddenError(msg='该成团人数的阶梯价格已存在')

        return await group_buy_ladder_price_dao.create(db, obj, activity_id, user_id)

    @staticmethod
    async def delete_ladder_price(*, db: AsyncSession, price_id: int) -> int:
        """
        删除阶梯价格

        :param db: 数据库会话
        :param price_id: 价格 ID
        :return:
        """
        price = await group_buy_ladder_price_dao.get(db, price_id)
        if not price:
            raise errors.NotFoundError(msg='阶梯价格不存在')
        return await group_buy_ladder_price_dao.delete_model(db, price_id)


group_buy_service = GroupBuyService()
