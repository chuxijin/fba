#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.admin.crud.crud_category import category_dao, category_doc_binding_dao
from backend.app.admin.model.category import Category, CategoryDocBinding
from backend.app.admin.schema.category import (
    CreateCategoryDocBindingParam,
    CreateCategoryParam,
    GetCategoryDocBindingDetail,
    UpdateCategoryDocBindingParam,
    UpdateCategoryParam,
)
from backend.common.exception import errors
from backend.common.pagination import paging_data
from backend.utils.build_tree import get_tree_data


class CategoryService:
    """分类服务类"""

    @staticmethod
    def _doc_binding_detail(binding: CategoryDocBinding) -> GetCategoryDocBindingDetail:
        """
        构建分类文档关联详情

        :param binding: 分类文档关联模型
        :return:
        """
        return GetCategoryDocBindingDetail.model_validate(binding)

    @staticmethod
    async def get(*, db: AsyncSession, pk: int) -> Category:
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
    async def get_tree(
        *,
        db: AsyncSession,
        app_code: str | None = None,
        type_: str | None = None,
        name: str | None = None,
        status: bool | None = None,
    ) -> list[dict[str, Any]]:
        """
        获取分类树形结构

        :param db: 数据库会话
        :param app_code: 应用标识
        :param type_: 分类类型
        :param name: 分类名称
        :param status: 状态
        :return:
        """
        categories = await category_dao.get_all(db, app_code=app_code, type_=type_, name=name, status=status)
        tree_data = get_tree_data(categories, sort_key='sort_order')
        return tree_data

    @staticmethod
    async def get_list(
        *,
        db: AsyncSession,
        app_code: str | None = None,
        type_: str | None = None,
        name: str | None = None,
        status: bool | None = None,
    ) -> dict[str, Any]:
        """
        获取分类分页列表

        :param db: 数据库会话
        :param app_code: 应用标识
        :param type_: 分类类型
        :param name: 分类名称
        :param status: 状态
        :return:
        """
        select = category_dao.get_select(app_code=app_code, type_=type_, name=name, status=status)
        return await paging_data(db, select)

    @staticmethod
    async def create(*, db: AsyncSession, obj: CreateCategoryParam, created_by: int) -> None:
        """
        创建分类

        :param db: 数据库会话
        :param obj: 创建分类参数
        :param created_by: 创建者 ID
        :return:
        """
        # 如果指定了 code，检查唯一性
        if obj.code:
            existing = await category_dao.get_by_code(db, obj.app_code, obj.type, obj.code)
            if existing:
                raise errors.ConflictError(msg='分类编码已存在')

        # 同层级下名称唯一性检查
        existing_name = await category_dao.get_by_name(db, obj.app_code, obj.type, obj.name, obj.parent_id)
        if existing_name:
            raise errors.ConflictError(msg='同级下分类名称已存在')

        # 父级分类校验
        if obj.parent_id:
            parent = await category_dao.get(db, obj.parent_id)
            if not parent:
                raise errors.NotFoundError(msg='父级分类不存在')

        await category_dao.create(db, obj, created_by)

    @staticmethod
    async def update(*, db: AsyncSession, pk: int, obj: UpdateCategoryParam, updated_by: int) -> int:
        """
        更新分类

        :param db: 数据库会话
        :param pk: 分类 ID
        :param obj: 更新分类参数
        :param updated_by: 修改者 ID
        :return:
        """
        category = await category_dao.get(db, pk)
        if not category:
            raise errors.NotFoundError(msg='分类不存在')

        # 禁止关联自身为父级
        if obj.parent_id and obj.parent_id == pk:
            raise errors.ForbiddenError(msg='禁止关联自身为父级')

        # 名称唯一性检查（同级下）
        if obj.name and obj.name != category.name:
            parent_id = obj.parent_id if obj.parent_id is not None else category.parent_id
            existing = await category_dao.get_by_name(db, category.app_code, category.type, obj.name, parent_id)
            if existing:
                raise errors.ConflictError(msg='同级下分类名称已存在')

        # 父级分类校验
        if obj.parent_id:
            parent = await category_dao.get(db, obj.parent_id)
            if not parent:
                raise errors.NotFoundError(msg='父级分类不存在')

        count = await category_dao.update(db, pk, obj, updated_by)
        return count

    @staticmethod
    async def delete(*, db: AsyncSession, pk: int) -> int:
        """
        删除分类

        :param db: 数据库会话
        :param pk: 分类 ID
        :return:
        """
        category = await category_dao.get(db, pk)
        if not category:
            raise errors.NotFoundError(msg='分类不存在')

        if category.is_system:
            raise errors.ForbiddenError(msg='系统分类禁止删除')

        has_children = await category_dao.has_children(db, pk)
        if has_children:
            raise errors.ConflictError(msg='分类下存在子分类，无法删除')

        count = await category_dao.delete(db, pk)
        return count

    @staticmethod
    async def delete_batch(*, db: AsyncSession, ids: list[int]) -> int:
        """
        批量删除分类

        :param db: 数据库会话
        :param ids: 分类 ID 列表
        :return:
        """
        count = 0
        for pk in ids:
            category = await category_dao.get(db, pk)
            if not category:
                continue

            if category.is_system:
                raise errors.ForbiddenError(msg=f'系统分类 [{category.name}] 禁止删除')

            has_children = await category_dao.has_children(db, pk)
            if has_children:
                raise errors.ConflictError(msg=f'分类 [{category.name}] 下存在子分类，无法删除')

            count += await category_dao.delete(db, pk)
        return count

    @staticmethod
    async def get_app_types(*, db: AsyncSession, app_code: str) -> list[str]:
        """
        获取应用下的所有分类类型

        :param db: 数据库会话
        :param app_code: 应用标识
        :return:
        """
        return await category_dao.get_app_types(db, app_code)

    @staticmethod
    async def get_all_app_codes(*, db: AsyncSession) -> list[str]:
        """获取所有应用标识"""
        return await category_dao.get_all_app_codes(db)

    @staticmethod
    async def get_all_types(*, db: AsyncSession, app_code: str | None = None) -> list[str]:
        """
        获取所有分类类型

        :param db: 数据库会话
        :param app_code: 应用标识（可选）
        :return:
        """
        return await category_dao.get_all_types(db, app_code)

    @staticmethod
    async def get_doc_bindings(
        *,
        db: AsyncSession,
        category_id: int | None = None,
        relation_type: str | None = None,
        enabled: bool | None = None,
    ) -> list[GetCategoryDocBindingDetail]:
        """
        获取分类文档关联列表

        :param db: 数据库会话
        :param category_id: 分类 ID
        :param relation_type: 关联类型
        :param enabled: 是否启用
        :return:
        """
        if category_id is not None:
            category = await category_dao.get(db, category_id)
            if category is None:
                raise errors.NotFoundError(msg='分类不存在')

        bindings = await category_doc_binding_dao.get_all(
            db,
            category_id=category_id,
            relation_type=relation_type,
            enabled=enabled,
        )
        return [CategoryService._doc_binding_detail(item) for item in bindings]

    @staticmethod
    async def get_doc_binding(*, db: AsyncSession, binding_id: int) -> GetCategoryDocBindingDetail:
        """
        获取分类文档关联详情

        :param db: 数据库会话
        :param binding_id: 关联 ID
        :return:
        """
        binding = await category_doc_binding_dao.get(db, binding_id)
        if binding is None:
            raise errors.NotFoundError(msg='分类文档关联不存在')
        return CategoryService._doc_binding_detail(binding)

    @staticmethod
    async def create_doc_binding(
        *,
        db: AsyncSession,
        category_id: int,
        obj: CreateCategoryDocBindingParam,
        created_by: int,
    ) -> GetCategoryDocBindingDetail:
        """
        创建分类文档关联

        :param db: 数据库会话
        :param category_id: 分类 ID
        :param obj: 创建参数
        :param created_by: 创建者 ID
        :return:
        """
        category = await category_dao.get(db, category_id)
        if category is None:
            raise errors.NotFoundError(msg='分类不存在')

        existing = await category_doc_binding_dao.get_existing(
            db,
            category_id=category_id,
            relation_type=obj.relation_type,
            halo_tree_name=obj.halo_tree_name,
        )
        if existing is not None:
            raise errors.ConflictError(msg='该分类已关联此文档')

        create_data = obj.model_dump()
        create_data['category_id'] = category_id
        create_data['category_code'] = category.code
        create_data['category_path'] = category.path
        create_data['created_by'] = created_by
        binding = await category_doc_binding_dao.create(db, create_data)
        return CategoryService._doc_binding_detail(binding)

    @staticmethod
    async def update_doc_binding(
        *,
        db: AsyncSession,
        binding_id: int,
        obj: UpdateCategoryDocBindingParam,
        updated_by: int,
    ) -> GetCategoryDocBindingDetail:
        """
        更新分类文档关联

        :param db: 数据库会话
        :param binding_id: 关联 ID
        :param obj: 更新参数
        :param updated_by: 修改者 ID
        :return:
        """
        binding = await category_doc_binding_dao.get(db, binding_id)
        if binding is None:
            raise errors.NotFoundError(msg='分类文档关联不存在')

        update_data = obj.model_dump(exclude_unset=True)
        relation_type = update_data.get('relation_type') or binding.relation_type
        halo_tree_name = update_data.get('halo_tree_name') or binding.halo_tree_name
        if relation_type != binding.relation_type or halo_tree_name != binding.halo_tree_name:
            existing = await category_doc_binding_dao.get_existing(
                db,
                category_id=binding.category_id,
                relation_type=relation_type,
                halo_tree_name=halo_tree_name,
            )
            if existing is not None and existing.id != binding.id:
                raise errors.ConflictError(msg='该分类已关联此文档')

        if update_data:
            update_data['updated_by'] = updated_by
            await category_doc_binding_dao.update(db, binding_id, update_data)
            for key, value in update_data.items():
                setattr(binding, key, value)
        return CategoryService._doc_binding_detail(binding)

    @staticmethod
    async def delete_doc_binding(*, db: AsyncSession, binding_id: int) -> int:
        """
        删除分类文档关联

        :param db: 数据库会话
        :param binding_id: 关联 ID
        :return:
        """
        binding = await category_doc_binding_dao.get(db, binding_id)
        if binding is None:
            raise errors.NotFoundError(msg='分类文档关联不存在')
        return await category_doc_binding_dao.delete(db, binding_id)


category_service: CategoryService = CategoryService()
