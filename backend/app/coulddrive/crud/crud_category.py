#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Sequence

from sqlalchemy import Select, and_, or_, func, desc, asc
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.coulddrive.model.category import Category
from backend.app.coulddrive.schema.category import (
    CreateCategoryParam,
    UpdateCategoryParam,
    GetCategoryListParam,
    GetCategoryTreeParam,
    GetCategoryOptionsParam
)
from sqlalchemy_crud_plus import CRUDPlus


class CRUDCategory(CRUDPlus[Category]):
    """分类 CRUD"""

    async def get(self, db: AsyncSession, pk: int) -> Category | None:
        """
        通过主键获取分类

        :param db: 数据库会话
        :param pk: 主键
        :return:
        """
        result = await self.select_model_by_column(db, id=pk)
        return result

    async def get_by_code(self, db: AsyncSession, code: str) -> Category | None:
        """通过编码获取分类"""
        stmt = Select(Category).where(Category.code == code)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_name_and_parent(
        self, 
        db: AsyncSession, 
        name: str, 
        parent_id: int | None, 
        category_type: str
    ) -> Category | None:
        """通过名称、父级ID和分类类型获取分类"""
        stmt = Select(Category).where(
            and_(
                Category.name == name,
                Category.parent_id == parent_id,
                Category.category_type == category_type
            )
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_children(self, db: AsyncSession, parent_id: int) -> Sequence[Category]:
        """获取子分类列表"""
        stmt = Select(Category).where(Category.parent_id == parent_id).order_by(Category.sort, Category.id)
        result = await db.execute(stmt)
        return result.scalars().all()

    async def get_by_category_type(self, db: AsyncSession, category_type: str) -> Sequence[Category]:
        """通过分类类型获取分类列表"""
        stmt = Select(Category).where(Category.category_type == category_type).order_by(Category.sort, Category.id)
        result = await db.execute(stmt)
        return result.scalars().all()
    
    async def create(self, db: AsyncSession, obj: CreateCategoryParam, current_user_id: int | None = None) -> Category:
        """
        创建分类

        :param db: 数据库会话
        :param obj: 创建分类参数
        :param current_user_id: 当前用户ID
        :return:
        """
        from backend.utils.timezone import timezone
        
        # 构建分类数据
        category_data = obj.model_dump()
        
        # 设置创建者
        if current_user_id:
            category_data["created_by"] = current_user_id
        
        # 如果有父分类，自动计算层级和路径
        if obj.parent_id:
            parent = await self.get(db, obj.parent_id)
            if parent:
                category_data["level"] = parent.level + 1
                category_data["path"] = f"{parent.path}/{obj.code}"
        else:
            category_data["level"] = 1
            category_data["path"] = f"/{obj.code}"
        
        # 移除不能在初始化时传递的字段
        category_data.pop("created_time", None)
        category_data.pop("updated_time", None)
        
        # 创建分类
        category = Category(**category_data)
        db.add(category)
        await db.commit()
        await db.refresh(category)
        return category
    
    async def update(self, db: AsyncSession, pk: int, obj: UpdateCategoryParam, current_user_id: int | None = None) -> int:
        """
        更新分类

        :param db: 数据库会话
        :param pk: 分类 ID
        :param obj: 更新参数
        :param current_user_id: 当前用户 ID
        :return:
        """
        from backend.utils.timezone import timezone
        
        # 将 schema 对象转换为字典，并添加 updated_by
        update_data = obj.model_dump(exclude_unset=True)
        if current_user_id:
            update_data["updated_by"] = current_user_id
        
        # 确保不会更新 created_time 和 created_by 字段
        update_data.pop("created_time", None)
        update_data.pop("created_by", None)
        
        # 手动设置 updated_time
        update_data["updated_time"] = timezone.now()
        
        # 如果更新了父分类，需要重新计算层级和路径
        if "parent_id" in update_data:
            if update_data["parent_id"]:
                parent = await self.get(db, update_data["parent_id"])
                if parent:
                    update_data["level"] = parent.level + 1
                    # 如果更新了 code，使用新的 code，否则获取原有的 code
                    current_category = await self.get(db, pk)
                    code = update_data.get("code", current_category.code)
                    update_data["path"] = f"{parent.path}/{code}"
            else:
                update_data["level"] = 1
                # 如果更新了 code，使用新的 code，否则获取原有的 code
                current_category = await self.get(db, pk)
                code = update_data.get("code", current_category.code)
                update_data["path"] = f"/{code}"
        
        # 使用 update_model_by_column 方法，只更新指定的字段
        result = await self.update_model_by_column(db, update_data, id=pk)
        await db.commit()
        return result
    
    async def delete(self, db: AsyncSession, pk: list[int]) -> int:
        """
        删除分类

        :param db: 数据库会话
        :param pk: 分类 ID 列表
        :return:
        """
        result = await self.delete_model_by_column(db, allow_multiple=True, id__in=pk)
        await db.commit()
        return result

    async def get_list(self, params: GetCategoryListParam) -> Select:
        """获取分类列表查询语句"""
        stmt = Select(Category)
        
        if params.category_type:
            stmt = stmt.where(Category.category_type == params.category_type)
        if params.parent_id is not None:
            stmt = stmt.where(Category.parent_id == params.parent_id)
        if params.level:
            stmt = stmt.where(Category.level == params.level)
        if params.status is not None:
            stmt = stmt.where(Category.status == params.status)
        if params.keyword:
            stmt = stmt.where(
                or_(
                    Category.name.ilike(f'%{params.keyword}%'),
                    Category.code.ilike(f'%{params.keyword}%')
                )
            )
        
        return stmt.order_by(Category.sort, Category.id)

    async def get_tree_data(self, db: AsyncSession, params: GetCategoryTreeParam) -> Sequence[Category]:
        """
        获取分类树数据
        
        :param db: 数据库会话
        :param params: 查询参数
        :return: 分类树数据
        """
        stmt = Select(Category)
        
        # 分类类型过滤
        if params.category_type:
            stmt = stmt.where(Category.category_type == params.category_type)
        
        # 状态过滤
        if params.status is not None:
            stmt = stmt.where(Category.status == params.status)
        
        # 最大层级过滤
        if params.max_level:
            stmt = stmt.where(Category.level <= params.max_level)
        
        # 排序
        stmt = stmt.order_by(Category.level, Category.sort, Category.id)
        
        result = await db.execute(stmt)
        return result.scalars().all()

    async def get_options(self, db: AsyncSession, params: GetCategoryOptionsParam) -> Sequence[Category]:
        """
        获取分类选项数据
        
        :param db: 数据库会话
        :param params: 查询参数
        :return: 分类选项数据
        """
        stmt = Select(Category)
        
        # 分类类型过滤
        if params.category_type:
            stmt = stmt.where(Category.category_type == params.category_type)
        
        # 父级ID过滤
        if params.parent_id is not None:
            stmt = stmt.where(Category.parent_id == params.parent_id)
        
        # 状态过滤
        if params.status is not None:
            stmt = stmt.where(Category.status == params.status)
        
        # 排序
        stmt = stmt.order_by(Category.sort, Category.id)
        
        result = await db.execute(stmt)
        return result.scalars().all()

    async def update_path(self, db: AsyncSession, category_id: int, path: str) -> None:
        """
        更新分类路径
        
        :param db: 数据库会话
        :param category_id: 分类ID
        :param path: 新路径
        :return:
        """
        category = await self.get(db, category_id)
        if category:
            category.path = path
            await db.commit()

    async def update_level(self, db: AsyncSession, category_id: int, level: int) -> None:
        """
        更新分类层级
        
        :param db: 数据库会话
        :param category_id: 分类ID
        :param level: 新层级
        :return:
        """
        category = await self.get(db, category_id)
        if category:
            category.level = level
            await db.commit()

    async def get_max_sort(self, db: AsyncSession, parent_id: int | None, category_type: str) -> int:
        """获取同级分类的最大排序值"""
        stmt = Select(func.max(Category.sort)).where(
            and_(
                Category.parent_id == parent_id,
                Category.category_type == category_type
            )
        )
        result = await db.execute(stmt)
        max_sort = result.scalar()
        return max_sort if max_sort is not None else 0

    async def get_statistics(self, db: AsyncSession) -> dict:
        """获取分类统计信息"""
        # 总数量
        total_stmt = Select(func.count(Category.id))
        total_result = await db.execute(total_stmt)
        total_count = total_result.scalar() or 0
        
        # 启用数量
        active_stmt = Select(func.count(Category.id)).where(Category.status == 1)
        active_result = await db.execute(active_stmt)
        active_count = active_result.scalar() or 0
        
        # 停用数量
        inactive_stmt = Select(func.count(Category.id)).where(Category.status == 0)
        inactive_result = await db.execute(inactive_stmt)
        inactive_count = inactive_result.scalar() or 0
        
        # 系统分类数量
        system_stmt = Select(func.count(Category.id)).where(Category.is_system == True)
        system_result = await db.execute(system_stmt)
        system_count = system_result.scalar() or 0
        
        # 按类型统计
        type_stmt = Select(Category.category_type, func.count(Category.id)).group_by(Category.category_type)
        type_result = await db.execute(type_stmt)
        by_type = {row[0]: row[1] for row in type_result.fetchall()}
        
        # 按层级统计
        level_stmt = Select(Category.level, func.count(Category.id)).group_by(Category.level)
        level_result = await db.execute(level_stmt)
        by_level = {row[0]: row[1] for row in level_result.fetchall()}
        
        return {
            'total_count': total_count,
            'active_count': active_count,
            'inactive_count': inactive_count,
            'system_count': system_count,
            'by_type': by_type,
            'by_level': by_level
        }

    async def _count_by_condition(self, db: AsyncSession, *conditions) -> int:
        """按条件统计数量"""
        stmt = Select(func.count(Category.id))
        for condition in conditions:
            stmt = stmt.where(condition)
        result = await db.execute(stmt)
        return result.scalar() or 0

    async def batch_update_status(self, db: AsyncSession, category_ids: list[int], status: int) -> int:
        """
        批量更新分类状态
        
        :param db: 数据库会话
        :param category_ids: 分类ID列表
        :param status: 状态
        :return: 更新数量
        """
        stmt = Select(Category).where(Category.id.in_(category_ids))
        result = await db.execute(stmt)
        categories = result.scalars().all()
        
        count = 0
        for category in categories:
            category.status = status
            count += 1
        
        await db.commit()
        return count

    async def batch_delete(self, db: AsyncSession, category_ids: list[int], force_delete: bool = False) -> int:
        """
        批量删除分类
        
        :param db: 数据库会话
        :param category_ids: 分类ID列表
        :param force_delete: 是否强制删除
        :return: 删除数量
        """
        stmt = Select(Category).where(Category.id.in_(category_ids))
        result = await db.execute(stmt)
        categories = result.scalars().all()
        
        count = 0
        for category in categories:
            # 如果不是强制删除，跳过系统分类
            if not force_delete and category.is_system:
                continue
            
            await db.delete(category)
            count += 1
        
        await db.commit()
        return count


# 创建实例
category_dao = CRUDCategory(Category) 