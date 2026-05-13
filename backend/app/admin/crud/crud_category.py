#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from collections.abc import Sequence
from typing import Any

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.admin.model.category import Category
from backend.app.admin.schema.category import CreateCategoryParam, UpdateCategoryParam


class CRUDCategory(CRUDPlus[Category]):
    """分类数据库操作类"""

    async def get(self, db: AsyncSession, pk: int) -> Category | None:
        """
        获取分类

        :param db: 数据库会话
        :param pk: 分类 ID
        :return:
        """
        return await self.select_model(db, pk)

    async def get_by_code(
        self, db: AsyncSession, app_code: str, type_: str, code: str
    ) -> Category | None:
        """
        通过编码获取分类

        :param db: 数据库会话
        :param app_code: 应用标识
        :param type_: 分类类型
        :param code: 分类编码
        :return:
        """
        return await self.select_model_by_column(db, app_code=app_code, type=type_, code=code)

    async def get_by_name(
        self, db: AsyncSession, app_code: str, type_: str, name: str, parent_id: int | None = None
    ) -> Category | None:
        """
        通过名称获取分类

        :param db: 数据库会话
        :param app_code: 应用标识
        :param type_: 分类类型
        :param name: 分类名称
        :param parent_id: 父级 ID
        :return:
        """
        return await self.select_model_by_column(
            db, app_code=app_code, type=type_, name=name, parent_id=parent_id
        )

    async def get_all(
        self,
        db: AsyncSession,
        app_code: str | None = None,
        type_: str | None = None,
        name: str | None = None,
        status: bool | None = None,
    ) -> Sequence[Category]:
        """
        获取所有分类

        :param db: 数据库会话
        :param app_code: 应用标识
        :param type_: 分类类型
        :param name: 分类名称
        :param status: 状态
        :return:
        """
        filters = {}
        if app_code is not None:
            filters['app_code'] = app_code
        if type_ is not None:
            filters['type'] = type_
        if name is not None:
            filters['name__like'] = f'%{name}%'
        if status is not None:
            filters['status'] = status

        return await self.select_models_order(db, 'sort_order', 'asc', **filters)

    def get_select(
        self,
        app_code: str | None = None,
        type_: str | None = None,
        name: str | None = None,
        status: bool | None = None,
    ) -> Select:
        """
        获取分类列表查询表达式

        :param app_code: 应用标识
        :param type_: 分类类型
        :param name: 分类名称
        :param status: 状态
        :return:
        """
        stmt = select(Category).order_by(Category.sort_order.asc())

        if app_code is not None:
            stmt = stmt.where(Category.app_code == app_code)
        if type_ is not None:
            stmt = stmt.where(Category.type == type_)
        if name is not None:
            stmt = stmt.where(Category.name.like(f'%{name}%'))
        if status is not None:
            stmt = stmt.where(Category.status == status)

        return stmt

    async def get_children(self, db: AsyncSession, parent_id: int) -> Sequence[Category]:
        """
        获取子分类

        :param db: 数据库会话
        :param parent_id: 父级分类 ID
        :return:
        """
        return await self.select_models_order(db, 'sort_order', 'asc', parent_id=parent_id)

    async def has_children(self, db: AsyncSession, pk: int) -> bool:
        """
        判断是否有子分类

        :param db: 数据库会话
        :param pk: 分类 ID
        :return:
        """
        children = await self.select_models(db, parent_id=pk)
        return len(children) > 0

    async def create(self, db: AsyncSession, obj: CreateCategoryParam, created_by: int) -> Category:
        """
        创建分类

        :param db: 数据库会话
        :param obj: 创建分类参数
        :param created_by: 创建者 ID
        :return:
        """
        # 计算层级和路径
        level = 1
        path = ''
        if obj.parent_id:
            parent = await self.get(db, obj.parent_id)
            if parent:
                level = parent.level + 1
                path = f'{parent.path}/{parent.id}' if parent.path else str(parent.id)

        create_data = obj.model_dump()
        create_data['level'] = level
        create_data['path'] = path or None
        create_data['created_by'] = created_by

        new_category = self.model(**create_data)
        db.add(new_category)
        await db.flush()
        return new_category

    async def update(self, db: AsyncSession, pk: int, obj: UpdateCategoryParam, updated_by: int) -> int:
        """
        更新分类

        :param db: 数据库会话
        :param pk: 分类 ID
        :param obj: 更新分类参数
        :param updated_by: 修改者 ID
        :return:
        """
        update_data = obj.model_dump(exclude_unset=True)
        update_data['updated_by'] = updated_by

        # 如果修改了 parent_id，需要重新计算 level 和 path
        if 'parent_id' in update_data:
            parent_id = update_data['parent_id']
            if parent_id:
                parent = await self.get(db, parent_id)
                if parent:
                    update_data['level'] = parent.level + 1
                    update_data['path'] = f'{parent.path}/{parent.id}' if parent.path else str(parent.id)
            else:
                update_data['level'] = 1
                update_data['path'] = None

        return await self.update_model_by_column(db, update_data, id=pk)

    async def delete(self, db: AsyncSession, pk: int) -> int:
        """
        删除分类

        :param db: 数据库会话
        :param pk: 分类 ID
        :return:
        """
        return await self.delete_model(db, pk)

    async def delete_batch(self, db: AsyncSession, ids: list[int]) -> int:
        """
        批量删除分类

        :param db: 数据库会话
        :param ids: 分类 ID 列表
        :return:
        """
        count = 0
        for pk in ids:
            count += await self.delete(db, pk)
        return count

    async def get_app_types(self, db: AsyncSession, app_code: str) -> list[str]:
        """
        获取应用下的所有分类类型

        :param db: 数据库会话
        :param app_code: 应用标识
        :return:
        """
        stmt = select(Category.type).where(Category.app_code == app_code).distinct()
        result = await db.execute(stmt)
        return [row[0] for row in result.all()]

    async def get_all_app_codes(self, db: AsyncSession) -> list[str]:
        """获取所有应用标识"""
        stmt = select(Category.app_code).distinct().order_by(Category.app_code)
        result = await db.execute(stmt)
        return [row[0] for row in result.all()]

    async def get_all_types(self, db: AsyncSession, app_code: str | None = None) -> list[str]:
        """
        获取所有分类类型

        :param db: 数据库会话
        :param app_code: 应用标识（可选，不传则获取全部）
        :return:
        """
        stmt = select(Category.type).distinct().order_by(Category.type)
        if app_code:
            stmt = stmt.where(Category.app_code == app_code)
        result = await db.execute(stmt)
        return [row[0] for row in result.all()]

    async def get_all_children_ids(self, db: AsyncSession, root_id: int) -> list[int]:
        """
        获取所有子孙分类ID（包含自身）

        :param db: 数据库会话
        :param root_id: 根分类 ID
        :return:
        """
        # 1. 基础查询 (Anchor Member)
        # 获取根节点
        query = select(Category.id).where(Category.id == root_id)

        # 定义递归 CTE
        cte = query.cte('cte', recursive=True)

        # 2. 递归查询 (Recursive Member)
        # 查找所有 parent_id 为 CTE 中 ID 的节点
        recursive_part = select(Category.id).join(cte, Category.parent_id == cte.c.id)

        # 3. 组合查询
        final_cte = cte.union_all(recursive_part)

        # 4. 执行查询
        stmt = select(final_cte.c.id)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def get_subtree_by_root_codes(
        self,
        db: AsyncSession,
        *,
        app_code: str,
        root_codes: list[str],
    ) -> list[dict[str, Any]]:
        """
        通过根编码递归查询子树扁平列表，跳过 ORM 实例化

        :param db: 数据库会话
        :param app_code: 应用标识
        :param root_codes: 根分类编码列表
        :return:
        """
        if not root_codes:
            return []

        anchor = select(
            Category.id,
            Category.parent_id,
            Category.app_code,
            Category.type,
            Category.code,
            Category.name,
            Category.sort_order,
        ).where(
            Category.app_code == app_code,
            Category.code.in_(root_codes),
            Category.status.is_(True),
        )
        cte = anchor.cte('category_subtree', recursive=True)

        recursive_part = (
            select(
                Category.id,
                Category.parent_id,
                Category.app_code,
                Category.type,
                Category.code,
                Category.name,
                Category.sort_order,
            )
            .join(cte, Category.parent_id == cte.c.id)
            .where(Category.status.is_(True))
        )

        final_cte = cte.union_all(recursive_part)
        stmt = select(final_cte)
        result = await db.execute(stmt)
        return [dict(row) for row in result.mappings().all()]


category_dao: CRUDCategory = CRUDCategory(Category)
