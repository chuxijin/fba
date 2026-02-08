#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.gongkao.crud.crud_guanmei import guanmei_dao
from backend.app.gongkao.model import GkGuanmei
from backend.app.gongkao.schema.guanmei import (
    CreateGuanmeiParam,
    DeleteGuanmeiParam,
    GuanmeiParam,
    UpdateGuanmeiParam,
)
from backend.common.exception import errors
from backend.common.pagination import paging_data


class GuanmeiService:
    """官媒学言语服务类"""

    @staticmethod
    async def get(*, db: AsyncSession, pk: int) -> GkGuanmei:
        """
        获取详情

        :param db: 数据库会话
        :param pk: ID
        :return:
        """
        guanmei = await guanmei_dao.get(db, pk)
        if not guanmei:
            raise errors.NotFoundError(msg='记录不存在')
        return guanmei

    @staticmethod
    async def get_list(*, db: AsyncSession, params: GuanmeiParam) -> dict[str, Any]:
        """
        获取列表（分页）

        :param db: 数据库会话
        :param params: 查询参数
        :return:
        """
        guanmei_select = await guanmei_dao.get_select(
            daily_date=params.daily_date,
        )
        return await paging_data(db, guanmei_select)

    @staticmethod
    async def create(*, db: AsyncSession, obj: CreateGuanmeiParam, created_by: int) -> GkGuanmei:
        """
        创建

        :param db: 数据库会话
        :param obj: 创建参数
        :param created_by: 创建者 ID
        :return:
        """
        return await guanmei_dao.create(db, obj, created_by)

    @staticmethod
    async def update(*, db: AsyncSession, pk: int, obj: UpdateGuanmeiParam, updated_by: int) -> int:
        """
        更新

        :param db: 数据库会话
        :param pk: ID
        :param obj: 更新参数
        :param updated_by: 修改者 ID
        :return:
        """
        guanmei = await guanmei_dao.get(db, pk)
        if not guanmei:
            raise errors.NotFoundError(msg='记录不存在')
        return await guanmei_dao.update(db, pk, obj, updated_by)

    @staticmethod
    async def delete(*, db: AsyncSession, obj: DeleteGuanmeiParam) -> int:
        """
        删除

        :param db: 数据库会话
        :param obj: 删除参数
        :return:
        """
        return await guanmei_dao.delete(db, obj.ids)

    @staticmethod
    async def increment_view(*, db: AsyncSession, pk: int) -> int:
        """
        增加阅读量

        :param db: 数据库会话
        :param pk: ID
        :return:
        """
        guanmei = await guanmei_dao.get(db, pk)
        if not guanmei:
            raise errors.NotFoundError(msg='记录不存在')
        return await guanmei_dao.increment_view_count(db, pk)


guanmei_service: GuanmeiService = GuanmeiService()
