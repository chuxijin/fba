#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.jia.crud.crud_category import category_dao
from backend.app.jia.model.categories import JiaCategory
from backend.app.jia.schema.category import CreateCategoryParam, UpdateCategoryParam
from backend.common.exception import errors


class CategoryService:
    """分类服务类"""

    @staticmethod
    async def get(*, db: AsyncSession, pk: int) -> JiaCategory:
        """
        获取分类详情

        :param db: 数据库会话
        :param pk: 分类 ID
        :return:
        """
        category = await category_dao.get(db, pk)
        if not category:
            raise errors.NotFoundError(msg='分类不存在')
        return category

    @staticmethod
    async def get_list(
        *,
        db: AsyncSession,
        parent_id: int | None = None,
        name: str | None = None,
        sync_status: str | None = None,
    ) -> list[JiaCategory]:
        """
        获取分类列表

        :param db: 数据库会话
        :param parent_id: 父级分类 ID
        :param name: 分类名称
        :param sync_status: 同步状态
        :return:
        """
        select_stmt = await category_dao.get_select(parent_id, name, sync_status)
        categories = await db.execute(select_stmt)
        return list(categories.scalars().all())

    @staticmethod
    async def get_all(*, db: AsyncSession, user_id: int) -> list[JiaCategory]:
        """
        获取所有分类

        :param db: 数据库会话
        :param user_id: 用户 ID
        :return:
        """
        return list(await category_dao.get_all(db, user_id))

    @staticmethod
    async def get_children(*, db: AsyncSession, parent_id: int) -> list[JiaCategory]:
        """
        获取子分类列表

        :param db: 数据库会话
        :param parent_id: 父级分类 ID
        :return:
        """
        return list(await category_dao.get_children(db, parent_id))

    @staticmethod
    async def create(*, db: AsyncSession, obj: CreateCategoryParam, user_id: int) -> None:
        """
        创建分类

        :param db: 数据库会话
        :param obj: 创建分类参数
        :param user_id: 用户 ID
        :return:
        """
        existing = await category_dao.get_by_name(db, obj.name, user_id)
        if existing:
            raise errors.ConflictError(msg='分类名称已存在')
        if obj.parent_id:
            parent = await category_dao.get(db, obj.parent_id)
            if not parent:
                raise errors.NotFoundError(msg='父级分类不存在')
        await category_dao.create(db, obj, user_id)

    @staticmethod
    async def update(*, db: AsyncSession, pk: int, obj: UpdateCategoryParam, user_id: int) -> int:
        """
        更新分类

        :param db: 数据库会话
        :param pk: 分类 ID
        :param obj: 更新分类参数
        :param user_id: 用户 ID
        :return:
        """
        category = await category_dao.get(db, pk)
        if not category:
            raise errors.NotFoundError(msg='分类不存在')
        if obj.name and obj.name != category.name:
            existing = await category_dao.get_by_name(db, obj.name, user_id)
            if existing:
                raise errors.ConflictError(msg='分类名称已存在')
        if obj.parent_id is not None:
            if obj.parent_id == pk:
                raise errors.ForbiddenError(msg='禁止关联自身为父级')
            if obj.parent_id > 0:
                parent = await category_dao.get(db, obj.parent_id)
                if not parent:
                    raise errors.NotFoundError(msg='父级分类不存在')
        count = await category_dao.update(db, pk, obj, user_id)
        return count

    @staticmethod
    async def delete(*, db: AsyncSession, pks: list[int]) -> int:
        """
        批量删除分类

        :param db: 数据库会话
        :param pks: 分类 ID 列表
        :return:
        """
        for pk in pks:
            children = await category_dao.get_children(db, pk)
            if children:
                raise errors.ConflictError(msg=f'分类 {pk} 下存在子分类，无法删除')
        count = await category_dao.delete(db, pks)
        return count


category_service: CategoryService = CategoryService()

