#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.gongkao.crud.crud_jingyan import jingyan_dao
from backend.app.gongkao.model import GkJingyan
from backend.app.gongkao.schema.jingyan import (
    CreateJingyanParam,
    DeleteJingyanParam,
    JingyanParam,
    UpdateJingyanParam,
)
from backend.common.exception import errors
from backend.common.pagination import paging_data


class JingyanService:
    """经验服务类"""

    @staticmethod
    async def get(*, db: AsyncSession, pk: int) -> GkJingyan:
        """
        获取经验详情

        :param db: 数据库会话
        :param pk: 经验 ID
        :return:
        """
        jingyan = await jingyan_dao.get(db, pk)
        if not jingyan:
            raise errors.NotFoundError(msg='经验不存在')
        return jingyan

    @staticmethod
    async def get_list(*, db: AsyncSession, params: JingyanParam) -> dict[str, Any]:
        """
        获取经验列表（分页）

        :param db: 数据库会话
        :param params: 查询参数
        :return:
        """
        jingyan_select = await jingyan_dao.get_select(
            title=params.title,
            category_id=params.category_id,
            author=params.author,
            tags=params.tags,
            daily_date=params.daily_date,
        )
        return await paging_data(db, jingyan_select)

    @staticmethod
    async def create(*, db: AsyncSession, obj: CreateJingyanParam, created_by: int) -> GkJingyan:
        """
        创建经验

        :param db: 数据库会话
        :param obj: 创建参数
        :param created_by: 创建者 ID
        :return:
        """
        jingyan = await jingyan_dao.get_by_title(db, obj.title)
        if jingyan:
            raise errors.ConflictError(msg='经验标题已存在')
        return await jingyan_dao.create(db, obj, created_by)

    @staticmethod
    async def update(*, db: AsyncSession, pk: int, obj: UpdateJingyanParam, updated_by: int) -> int:
        """
        更新经验

        :param db: 数据库会话
        :param pk: 经验 ID
        :param obj: 更新参数
        :param updated_by: 修改者 ID
        :return:
        """
        jingyan = await jingyan_dao.get(db, pk)
        if not jingyan:
            raise errors.NotFoundError(msg='经验不存在')
        if obj.title and jingyan.title != obj.title:
            existing = await jingyan_dao.get_by_title(db, obj.title)
            if existing:
                raise errors.ConflictError(msg='经验标题已存在')
        return await jingyan_dao.update(db, pk, obj, updated_by)

    @staticmethod
    async def delete(*, db: AsyncSession, obj: DeleteJingyanParam) -> int:
        """
        删除经验

        :param db: 数据库会话
        :param obj: 删除参数
        :return:
        """
        return await jingyan_dao.delete(db, obj.ids)

    @staticmethod
    async def increment_view(*, db: AsyncSession, pk: int) -> int:
        """
        增加阅读量

        :param db: 数据库会话
        :param pk: 经验 ID
        :return:
        """
        jingyan = await jingyan_dao.get(db, pk)
        if not jingyan:
            raise errors.NotFoundError(msg='经验不存在')
        return await jingyan_dao.increment_view_count(db, pk)


jingyan_service: JingyanService = JingyanService()
