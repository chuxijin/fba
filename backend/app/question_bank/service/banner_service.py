#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from collections.abc import Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.question_bank.crud.crud_banner import banner_dao
from backend.app.question_bank.schema.banner import (
    CreateBannerParam,
    GetActiveBanner,
    GetBannerDetail,
    UpdateBannerParam,
)
from backend.common.exception import errors


class BannerService:
    """轮播图服务类"""

    @staticmethod
    async def get(*, db: AsyncSession, pk: int) -> GetBannerDetail:
        """
        获取轮播图详情

        :param db: 数据库会话
        :param pk: 轮播图 ID
        :return:
        """
        banner = await banner_dao.get(db, pk)
        if not banner:
            raise errors.NotFoundError(msg='轮播图不存在')
        return GetBannerDetail.model_validate(banner)

    @staticmethod
    async def get_list(
        *,
        db: AsyncSession,
        status: int | None = None,
        scene: str | None = None,
    ) -> Sequence[GetBannerDetail]:
        """
        获取轮播图列表

        :param db: 数据库会话
        :param status: 状态筛选
        :param scene: 展示场景筛选
        :return:
        """
        banners = await banner_dao.get_all(db, status=status, scene=scene)
        return [GetBannerDetail.model_validate(banner) for banner in banners]

    @staticmethod
    async def get_active_list(*, db: AsyncSession, scene: str | None = None) -> Sequence[GetActiveBanner]:
        """
        获取启用且在有效期内的轮播图列表

        :param db: 数据库会话
        :param scene: 展示场景筛选
        :return:
        """
        banners = await banner_dao.get_active_list(db, scene=scene)
        return [GetActiveBanner.model_validate(banner) for banner in banners]

    @staticmethod
    async def create(*, db: AsyncSession, obj_in: CreateBannerParam) -> None:
        """
        创建轮播图

        :param db: 数据库会话
        :param obj_in: 创建参数
        :return:
        """
        await banner_dao.create(db, obj_in)

    @staticmethod
    async def update(*, db: AsyncSession, pk: int, obj_in: UpdateBannerParam) -> int:
        """
        更新轮播图

        :param db: 数据库会话
        :param pk: 轮播图 ID
        :param obj_in: 更新参数
        :return:
        """
        banner = await banner_dao.get(db, pk)
        if not banner:
            raise errors.NotFoundError(msg='轮播图不存在')
        count = await banner_dao.update(db, pk, obj_in)
        return count

    @staticmethod
    async def delete(*, db: AsyncSession, pk: int) -> int:
        """
        删除轮播图

        :param db: 数据库会话
        :param pk: 轮播图 ID
        :return:
        """
        banner = await banner_dao.get(db, pk)
        if not banner:
            raise errors.NotFoundError(msg='轮播图不存在')
        count = await banner_dao.delete(db, pk)
        return count

    @staticmethod
    async def increment_click(*, db: AsyncSession, pk: int) -> None:
        """
        增加点击次数

        :param db: 数据库会话
        :param pk: 轮播图 ID
        :return:
        """
        await banner_dao.increment_click(db, pk)
