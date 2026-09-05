#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.gongkao.crud.crud_hanyu_group import hanyu_group_dao
from backend.app.gongkao.model import GkHanyuGroup
from backend.app.gongkao.schema.hanyu_group import (
    CreateHanyuGroupParam,
    DeleteHanyuGroupParam,
    HanyuGroupParam,
    UpdateHanyuGroupParam,
)
from backend.common.exception import errors
from backend.common.pagination import paging_data


class HanyuGroupService:
    """汉语词语辨析组服务类"""

    @staticmethod
    async def get(*, db: AsyncSession, pk: int) -> GkHanyuGroup:
        """
        获取辨析组详情

        :param db: 数据库会话
        :param pk: 辨析组 ID
        :return:
        """
        group = await hanyu_group_dao.get(db, pk)
        if not group:
            raise errors.NotFoundError(msg='辨析组不存在')
        return group

    @staticmethod
    async def get_list(*, db: AsyncSession, params: HanyuGroupParam) -> dict[str, Any]:
        """
        获取辨析组列表（分页）

        :param db: 数据库会话
        :param params: 查询参数
        :return:
        """
        group_select = await hanyu_group_dao.get_select(params)
        page_data = await paging_data(db, group_select)

        if page_data.get('items'):
            for item in page_data['items']:
                item['item_count'] = len(item.get('items') or [])

        return page_data

    @staticmethod
    async def get_categories(*, db: AsyncSession) -> list[str]:
        """
        获取所有分类

        :param db: 数据库会话
        :return:
        """
        return await hanyu_group_dao.get_categories(db)

    @staticmethod
    async def create(*, db: AsyncSession, obj: CreateHanyuGroupParam, created_by: int) -> GkHanyuGroup:
        """
        创建辨析组

        :param db: 数据库会话
        :param obj: 创建参数
        :param created_by: 创建者 ID
        :return:
        """
        if not obj.items:
            raise errors.ForbiddenError(msg='辨析组成员不能为空')
        existing = await hanyu_group_dao.get_by_title(db, obj.title, obj.category)
        if existing:
            raise errors.ForbiddenError(msg=f'分类 "{obj.category}" 下已存在标题为 "{obj.title}" 的辨析组')
        return await hanyu_group_dao.create(db, obj, created_by)

    @staticmethod
    async def update(*, db: AsyncSession, pk: int, obj: UpdateHanyuGroupParam, updated_by: int) -> None:
        """
        更新辨析组

        :param db: 数据库会话
        :param pk: 辨析组 ID
        :param obj: 更新参数
        :param updated_by: 修改者 ID
        :return:
        """
        group = await hanyu_group_dao.get(db, pk)
        if not group:
            raise errors.NotFoundError(msg='辨析组不存在')
        if obj.title and obj.category and (obj.title != group.title or obj.category != group.category):
            existing = await hanyu_group_dao.get_by_title(db, obj.title, obj.category)
            if existing and existing.id != pk:
                raise errors.ForbiddenError(msg=f'分类 "{obj.category}" 下已存在标题为 "{obj.title}" 的辨析组')
        if obj.items is not None and not obj.items:
            raise errors.ForbiddenError(msg='辨析组成员不能为空')
        await hanyu_group_dao.update(db, group, obj, updated_by)

    @staticmethod
    async def delete(*, db: AsyncSession, obj: DeleteHanyuGroupParam) -> int:
        """
        删除辨析组

        :param db: 数据库会话
        :param obj: 删除参数
        :return:
        """
        return await hanyu_group_dao.delete(db, obj.ids)


hanyu_group_service: HanyuGroupService = HanyuGroupService()
