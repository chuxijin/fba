#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from collections.abc import Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.gongkao.crud.crud_shizhen import shizhen_dao
from backend.app.gongkao.model.shizhen import GkShizhen
from backend.app.gongkao.schema.shizhen import (
    CreateShizhenParam,
    DeleteShizhenParam,
    ShizhenParam,
    UpdateShizhenParam,
)
from backend.common.exception import errors


class ShizhenService:
    """时政服务类"""

    @staticmethod
    async def get(*, db: AsyncSession, pk: int) -> GkShizhen:
        """
        获取时政详情

        :param db: 数据库会话
        :param pk: 时政 ID
        :return:
        """
        shizhen = await shizhen_dao.get(db, pk)
        if not shizhen:
            raise errors.NotFoundError(msg='时政不存在')
        return shizhen

    @staticmethod
    async def get_list(*, db: AsyncSession, params: ShizhenParam) -> Sequence[GkShizhen]:
        """
        获取时政列表

        :param db: 数据库会话
        :param params: 查询参数
        :return:
        """
        return await shizhen_dao.get_list(db, daily_date=params.daily_date)

    @staticmethod
    async def create(*, db: AsyncSession, obj: CreateShizhenParam, created_by: int) -> GkShizhen:
        """
        创建时政

        :param db: 数据库会话
        :param obj: 创建参数
        :param created_by: 创建者 ID
        :return:
        """
        return await shizhen_dao.create(db, obj, created_by)

    @staticmethod
    async def update(*, db: AsyncSession, pk: int, obj: UpdateShizhenParam, updated_by: int) -> int:
        """
        更新时政

        :param db: 数据库会话
        :param pk: 时政 ID
        :param obj: 更新参数
        :param updated_by: 修改者 ID
        :return:
        """
        shizhen = await shizhen_dao.get(db, pk)
        if not shizhen:
            raise errors.NotFoundError(msg='时政不存在')
        return await shizhen_dao.update(db, pk, obj, updated_by)

    @staticmethod
    async def delete(*, db: AsyncSession, obj: DeleteShizhenParam) -> int:
        """
        删除时政

        :param db: 数据库会话
        :param obj: 删除参数
        :return:
        """
        return await shizhen_dao.delete(db, obj.ids)


shizhen_service: ShizhenService = ShizhenService()
