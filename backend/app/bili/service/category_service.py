#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.bili.crud import bili_category_dao
from backend.app.bili.model import BiliCategory
from backend.app.bili.schema.category import CreateBiliCategoryParam, UpdateBiliCategoryParam
from backend.common.exception import errors
from backend.utils.build_tree import get_tree_data


class BiliCategoryService:
    """B 站分类服务类"""

    @staticmethod
    async def get(db: AsyncSession, pk: int) -> BiliCategory:
        """
        获取分类详情

        :param db: 数据库会话
        :param pk: 主键 ID
        :return:
        """
        category = await bili_category_dao.get(db, pk)
        if not category:
            raise errors.NotFoundError(msg='分类不存在')
        return category

    @staticmethod
    async def get_tree(
        db: AsyncSession, name: str | None = None, status: int | None = None
    ) -> list[dict[str, Any]]:
        """
        获取分类树形结构

        :param db: 数据库会话
        :param name: 分类名称
        :param status: 状态
        :return:
        """
        categories = await bili_category_dao.get_list(db, name=name, status=status)
        tree = get_tree_data(categories)
        return tree

    @staticmethod
    async def create(db: AsyncSession, obj: CreateBiliCategoryParam) -> None:
        """
        创建分类

        :param db: 数据库会话
        :param obj: 创建参数
        :return:
        """
        category = await bili_category_dao.get_by_name(db, obj.name)
        if category:
            raise errors.ForbiddenError(msg='分类名称已存在')
        await bili_category_dao.create(db, obj)

    @staticmethod
    async def update(db: AsyncSession, pk: int, obj: UpdateBiliCategoryParam) -> int:
        """
        更新分类

        :param db: 数据库会话
        :param pk: 主键 ID
        :param obj: 更新参数
        :return:
        """
        category = await bili_category_dao.get(db, pk)
        if not category:
            raise errors.NotFoundError(msg='分类不存在')
        if obj.name and obj.name != category.name:
            exist_category = await bili_category_dao.get_by_name(db, obj.name)
            if exist_category:
                raise errors.ForbiddenError(msg='分类名称已存在')
        count = await bili_category_dao.update(db, pk, obj)
        return count

    @staticmethod
    async def delete(db: AsyncSession, pk: int) -> int:
        """
        删除分类

        :param db: 数据库会话
        :param pk: 主键 ID
        :return:
        """
        category = await bili_category_dao.get(db, pk)
        if not category:
            raise errors.NotFoundError(msg='分类不存在')
        children = await bili_category_dao.get_children(db, pk)
        if children:
            raise errors.ForbiddenError(msg='存在子分类，无法删除')
        count = await bili_category_dao.delete(db, pk)
        return count


bili_category_service = BiliCategoryService()
