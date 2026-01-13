#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from collections.abc import Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.gongkao.crud import shiping_dao
from backend.app.gongkao.model import GkShiping
from backend.app.gongkao.schema.shiping import (
    CreateShipingParam,
    DeleteShipingParam,
    ShipingParam,
    UpdateShipingParam,
)
from backend.common.exception import errors


class ShipingService:
    """时评服务类"""

    @staticmethod
    async def get(*, db: AsyncSession, pk: int) -> GkShiping:
        """
        获取时评详情

        :param db: 数据库会话
        :param pk: 时评 ID
        :return:
        """
        shiping = await shiping_dao.get(db, pk)
        if not shiping:
            raise errors.NotFoundError(msg='时评不存在')
        return shiping

    @staticmethod
    async def get_list(*, db: AsyncSession, params: ShipingParam) -> Sequence[GkShiping]:
        """
        获取时评列表

        :param db: 数据库会话
        :param params: 查询参数
        :return:
        """
        return await shiping_dao.get_list(
            db,
            title=params.title,
            source=params.source,
            author=params.author,
            keywords=params.keywords,
            daily_date=params.daily_date,
        )

    @staticmethod
    async def create(*, db: AsyncSession, obj: CreateShipingParam, created_by: int) -> GkShiping:
        """
        创建时评

        :param db: 数据库会话
        :param obj: 创建参数
        :param created_by: 创建者 ID
        :return:
        """
        shiping = await shiping_dao.get_by_title(db, obj.title)
        if shiping:
            raise errors.ConflictError(msg='时评标题已存在')
        return await shiping_dao.create(db, obj, created_by)

    @staticmethod
    async def update(*, db: AsyncSession, pk: int, obj: UpdateShipingParam, updated_by: int) -> int:
        """
        更新时评

        :param db: 数据库会话
        :param pk: 时评 ID
        :param obj: 更新参数
        :param updated_by: 修改者 ID
        :return:
        """
        shiping = await shiping_dao.get(db, pk)
        if not shiping:
            raise errors.NotFoundError(msg='时评不存在')
        if obj.title and shiping.title != obj.title:
            existing = await shiping_dao.get_by_title(db, obj.title)
            if existing:
                raise errors.ConflictError(msg='时评标题已存在')
        return await shiping_dao.update(db, pk, obj, updated_by)

    @staticmethod
    async def delete(*, db: AsyncSession, obj: DeleteShipingParam) -> int:
        """
        删除时评

        :param db: 数据库会话
        :param obj: 删除参数
        :return:
        """
        return await shiping_dao.delete(db, obj.ids)

    @staticmethod
    async def increment_view(*, db: AsyncSession, pk: int) -> int:
        """
        增加阅读量

        :param db: 数据库会话
        :param pk: 时评 ID
        :return:
        """
        shiping = await shiping_dao.get(db, pk)
        if not shiping:
            raise errors.NotFoundError(msg='时评不存在')
        return await shiping_dao.increment_view_count(db, pk)


shiping_service: ShipingService = ShipingService()
