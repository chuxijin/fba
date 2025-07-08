#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.coulddrive.crud.crud_category import category_dao
from backend.app.coulddrive.model.category import Category
from backend.app.coulddrive.schema.category import (
    CreateCategoryParam,
    UpdateCategoryParam,
    GetCategoryDetail,
    GetCategoryListParam,
    CategoryTreeNode,
    CategoryOption,
    GetCategoryOptionsParam,
    CategoryStatistics
)
from backend.common.exception.errors import NotFoundError, ForbiddenError, ConflictError
from backend.common.pagination import paging_data


class CategoryService:
    """分类服务类"""

    @staticmethod
    async def get(db: AsyncSession, category_id: int) -> GetCategoryDetail:
        """获取分类详情"""
        category = await category_dao.get(db, category_id)
        if not category:
            raise NotFoundError(msg="分类不存在")
        return GetCategoryDetail.model_validate(category)

    @staticmethod
    async def get_by_code(db: AsyncSession, code: str) -> Category:
        """通过编码获取分类"""
        category = await category_dao.get_by_code(db, code)
        if not category:
            raise NotFoundError(msg="分类不存在")
        return category

    @staticmethod
    async def get_list(db: AsyncSession, params: GetCategoryListParam) -> dict:
        """获取分类列表"""
        stmt = await category_dao.get_list(params)
        return await paging_data(db, stmt)

    @staticmethod
    async def get_tree(db: AsyncSession, category_type: str = None, status: int = None) -> list[CategoryTreeNode]:
        """获取分类树"""
        from sqlalchemy import select, case
        
        stmt = select(Category)
        if category_type:
            stmt = stmt.where(Category.category_type == category_type)
        if status is not None:
            stmt = stmt.where(Category.status == status)
        
        # 自定义排序：先按层级，再按分类类型（domain优先），最后按sort值
        type_order = case(
            (Category.category_type == 'domain', 1),
            (Category.category_type == 'subject', 2),
            (Category.category_type == 'resource_type', 3),
            else_=4
        )
        
        result = await db.execute(stmt.order_by(Category.level, type_order, Category.sort))
        categories = result.scalars().all()
        return CategoryService._build_tree(categories)

    @staticmethod
    def _build_tree(categories: Sequence[Category]) -> list[CategoryTreeNode]:
        """构建分类树"""
        # 手动构建 CategoryTreeNode 对象，避免 SQLAlchemy 懒加载问题
        category_map = {}
        for cat in categories:
            category_map[cat.id] = CategoryTreeNode(
                id=cat.id,
                name=cat.name,
                code=cat.code,
                description=cat.description,
                category_type=cat.category_type,
                parent_id=cat.parent_id,
                level=cat.level,
                path=cat.path,
                sort=cat.sort,
                status=cat.status,
                is_system=cat.is_system,
                children=[]
            )
        
        root_nodes = []
        for category in categories:
            node = category_map[category.id]
            if category.parent_id is None:
                root_nodes.append(node)
            elif category.parent_id in category_map:
                category_map[category.parent_id].children.append(node)
        
        return root_nodes

    @staticmethod
    async def get_options(db: AsyncSession, params: GetCategoryOptionsParam) -> list[CategoryOption]:
        """获取分类选项"""
        categories = await category_dao.get_options(db, params)
        return [
            CategoryOption(
                label=cat.name,
                value=cat.code,
                category_type=cat.category_type,
                level=cat.level,
                disabled=cat.status == 0
            )
            for cat in categories
        ]

    @staticmethod
    async def create(db: AsyncSession, obj: CreateCategoryParam, created_by: int) -> GetCategoryDetail:
        """创建分类"""
        # 验证编码唯一性
        if await category_dao.get_by_code(db, obj.code):
            raise ConflictError(msg="分类编码已存在")

        # 验证同级名称唯一性
        if await category_dao.get_by_name_and_parent(db, obj.name, obj.parent_id, obj.category_type):
            raise ConflictError(msg="同级分类名称已存在")

        # 验证父级分类
        if obj.parent_id:
            parent_category = await category_dao.get(db, obj.parent_id)
            if not parent_category:
                raise NotFoundError(msg="父级分类不存在")
            
            # 验证分类层次结构：domain -> subject -> resource_type
            valid_parent_child_mapping = {
                'domain': ['subject'],
                'subject': ['resource_type'],
                'resource_type': []  # 资源类型不能有子分类
            }
            
            if obj.category_type not in valid_parent_child_mapping.get(parent_category.category_type, []):
                raise ConflictError(msg=f"'{parent_category.category_type}' 类型的分类不能包含 '{obj.category_type}' 类型的子分类")

        # 获取排序值
        if obj.sort <= 0:
            obj.sort = await category_dao.get_max_sort(db, obj.parent_id, obj.category_type) + 1

        # 创建分类（CRUD 层会自动处理层级和路径）
        category = await category_dao.create(db, obj, created_by)
        return GetCategoryDetail.model_validate(category)

    @staticmethod
    async def update(db: AsyncSession, category_id: int, obj: UpdateCategoryParam, updated_by: int) -> GetCategoryDetail:
        """更新分类"""
        category = await category_dao.get(db, category_id)
        if not category:
            raise NotFoundError(msg="分类不存在")

        # 验证编码唯一性
        if obj.code and obj.code != category.code:
            if await category_dao.get_by_code(db, obj.code):
                raise ConflictError(msg="分类编码已存在")

        # 验证名称唯一性
        if obj.name and obj.name != category.name:
            if await category_dao.get_by_name_and_parent(db, obj.name, category.parent_id, category.category_type):
                raise ConflictError(msg="同级分类名称已存在")

        # 验证父级变更
        if obj.parent_id is not None and obj.parent_id != category.parent_id:
            if obj.parent_id == category_id:
                raise ConflictError(msg="不能将自己设为父级分类")
            
            if obj.parent_id:
                parent = await category_dao.get(db, obj.parent_id)
                if not parent:
                    raise NotFoundError(msg="父级分类不存在")
                
                # 验证分类层次结构：domain -> subject -> resource_type
                valid_parent_child_mapping = {
                    'domain': ['subject'],
                    'subject': ['resource_type'],
                    'resource_type': []  # 资源类型不能有子分类
                }
                
                if category.category_type not in valid_parent_child_mapping.get(parent.category_type, []):
                    raise ConflictError(msg=f"'{parent.category_type}' 类型的分类不能包含 '{category.category_type}' 类型的子分类")

        # 更新分类（CRUD 层会自动处理层级和路径）
        await category_dao.update(db, category_id, obj, updated_by)
        updated_category = await category_dao.get(db, category_id)
        return GetCategoryDetail.model_validate(updated_category)



    @staticmethod
    async def delete(db: AsyncSession, category_id: int) -> None:
        """删除分类"""
        category = await category_dao.get(db, category_id)
        if not category:
            raise NotFoundError(msg="分类不存在")
        if category.is_system:
            raise ForbiddenError(msg="系统分类不能删除")
        
        children = await category_dao.get_children(db, category_id)
        if children:
            raise ConflictError(msg="存在子分类，不能删除")

        await category_dao.delete(db, [category_id])

    @staticmethod
    async def get_statistics(db: AsyncSession) -> CategoryStatistics:
        """获取分类统计信息"""
        stats = await category_dao.get_statistics(db)
        return CategoryStatistics(**stats)

    @staticmethod
    async def get_domain_subject_mapping(db: AsyncSession) -> dict:
        """获取领域和科目映射关系"""
        domains = await category_dao.get_by_category_type(db, "domain")
        subjects = await category_dao.get_by_category_type(db, "subject")
        
        mapping = {}
        for domain in domains:
            domain_subjects = [s.name for s in subjects if s.parent_id == domain.id]
            mapping[domain.name] = domain_subjects
        
        return mapping


# 创建服务实例
category_service = CategoryService() 