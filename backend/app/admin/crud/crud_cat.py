#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from collections.abc import Sequence
from typing import Any

from sqlalchemy import Select, delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.admin.model.cat import SysCat, SysCatTarget
from backend.app.admin.schema.cat import CreateSysCatParam, UpdateSysCatParam


class CRUDSysCat(CRUDPlus[SysCat]):
    """分类数据库操作类"""

    async def get(self, db: AsyncSession, pk: int) -> SysCat | None:
        return await self.select_model(db, pk)

    async def get_by_name(
        self, db: AsyncSession, app_code: str, name: str, parent_id: int | None, user_id: int | None
    ) -> SysCat | None:
        return await self.select_model_by_column(
            db, app_code=app_code, name=name, parent_id=parent_id, user_id=user_id
        )

    async def get_all(
        self,
        db: AsyncSession,
        app_code: str | None = None,
        user_id: int | None = None,
        name: str | None = None,
        status: bool | None = None,
    ) -> Sequence[SysCat]:
        filters = {}
        if app_code is not None:
            filters['app_code'] = app_code
        if user_id is not None:
            filters['user_id'] = user_id
        if name is not None:
            filters['name__like'] = f'%{name}%'
        if status is not None:
            filters['status'] = status
        return await self.select_models_order(db, 'sort_order', 'asc', **filters)

    def get_select(
        self,
        app_code: str | None = None,
        user_id: int | None = None,
        name: str | None = None,
        status: bool | None = None,
    ) -> Select:
        stmt = select(SysCat).order_by(SysCat.sort_order.asc())
        if app_code is not None:
            stmt = stmt.where(SysCat.app_code == app_code)
        if user_id is not None:
            stmt = stmt.where(SysCat.user_id == user_id)
        if name is not None:
            stmt = stmt.where(SysCat.name.like(f'%{name}%'))
        if status is not None:
            stmt = stmt.where(SysCat.status == status)
        return stmt

    async def get_children(self, db: AsyncSession, parent_id: int) -> Sequence[SysCat]:
        return await self.select_models_order(db, 'sort_order', 'asc', parent_id=parent_id)

    async def has_children(self, db: AsyncSession, pk: int) -> bool:
        children = await self.select_models(db, parent_id=pk)
        return len(children) > 0

    async def create(self, db: AsyncSession, obj: CreateSysCatParam, created_by: int) -> SysCat:
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

        new_cat = self.model(**create_data)
        db.add(new_cat)
        await db.flush()
        return new_cat

    async def update(self, db: AsyncSession, pk: int, obj: UpdateSysCatParam, updated_by: int) -> int:
        update_data = obj.model_dump(exclude_unset=True)
        update_data['updated_by'] = updated_by

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
        return await self.delete_model(db, pk)

    async def get_subtree_ids_by_path(self, db: AsyncSession, root_id: int) -> list[int]:
        root = await self.get(db, root_id)
        if root is None:
            return []

        path_prefix = root.path or str(root.id)
        stmt = select(SysCat.id).where(
            or_(
                SysCat.id == root_id,
                SysCat.path == path_prefix,
                SysCat.path.like(f'{path_prefix}/%'),
            )
        ).order_by(SysCat.level.asc(), SysCat.sort_order.asc())
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def get_tree_data(
        self,
        db: AsyncSession,
        app_code: str | None = None,
        user_id: int | None = None,
        status: bool | None = None,
    ) -> Sequence[SysCat]:
        filters = {}
        if app_code is not None:
            filters['app_code'] = app_code
        if user_id is not None:
            filters['user_id'] = user_id
        if status is not None:
            filters['status'] = status
        return await self.select_models_order(db, 'sort_order', 'asc', **filters)

    async def get_with_target_count(
        self,
        db: AsyncSession,
        app_code: str | None = None,
        user_id: int | None = None,
        status: bool | None = None,
    ) -> list[dict]:
        stmt = (
            select(
                SysCat,
                func.coalesce(func.count(SysCatTarget.id), 0).label('target_count'),
            )
            .outerjoin(SysCatTarget, SysCatTarget.cat_id == SysCat.id)
            .group_by(SysCat.id)
            .order_by(SysCat.sort_order.asc())
        )
        if app_code is not None:
            stmt = stmt.where(SysCat.app_code == app_code)
        if user_id is not None:
            stmt = stmt.where(SysCat.user_id == user_id)
        if status is not None:
            stmt = stmt.where(SysCat.status == status)

        result = await db.execute(stmt)
        rows = result.all()
        return [
            {
                'id': cat.id,
                'app_code': cat.app_code,
                'name': cat.name,
                'color': cat.color,
                'icon': cat.icon,
                'user_id': cat.user_id,
                'parent_id': cat.parent_id,
                'level': cat.level,
                'path': cat.path,
                'sort_order': cat.sort_order,
                'status': cat.status,
                'remark': cat.remark,
                'created_by': cat.created_by,
                'created_time': cat.created_time,
                'updated_time': cat.updated_time,
                'target_count': int(target_count),
            }
            for cat, target_count in rows
        ]


class CRUDSysCatTarget(CRUDPlus[SysCatTarget]):
    """分类关联数据库操作类"""

    async def get(self, db: AsyncSession, pk: int) -> SysCatTarget | None:
        return await self.select_model(db, pk)

    async def get_by_target(self, db: AsyncSession, target_type: str, target_id: int) -> Sequence[SysCatTarget]:
        return await self.select_models(db, target_type=target_type, target_id=target_id)

    async def get_by_cat_and_target(
        self, db: AsyncSession, cat_id: int, target_type: str, target_id: int
    ) -> SysCatTarget | None:
        return await self.select_model_by_column(db, cat_id=cat_id, target_type=target_type, target_id=target_id)

    async def get_targets_with_cat(self, db: AsyncSession, target_type: str, target_id: int) -> list[dict]:
        stmt = (
            select(SysCatTarget, SysCat.name, SysCat.color, SysCat.icon, SysCat.path)
            .join(SysCat, SysCat.id == SysCatTarget.cat_id)
            .where(SysCatTarget.target_type == target_type, SysCatTarget.target_id == target_id)
            .order_by(SysCat.sort_order.asc())
        )
        result = await db.execute(stmt)
        return [
            {
                'id': row[0].id,
                'cat_id': row[0].cat_id,
                'target_type': row[0].target_type,
                'target_id': row[0].target_id,
                'created_by': row[0].created_by,
                'created_time': row[0].created_time,
                'cat_name': row[1],
                'cat_color': row[2],
                'cat_icon': row[3],
                'cat_path': row[4],
            }
            for row in result.all()
        ]

    async def create(self, db: AsyncSession, cat_id: int, target_type: str, target_id: int, created_by: int | None = None) -> SysCatTarget:
        target = self.model(cat_id=cat_id, target_type=target_type, target_id=target_id, created_by=created_by)
        db.add(target)
        await db.flush()
        return target

    async def delete(self, db: AsyncSession, pk: int) -> int:
        return await self.delete_model(db, pk)

    async def delete_by_cat_and_target(self, db: AsyncSession, cat_id: int, target_type: str, target_id: int) -> int:
        stmt = delete(SysCatTarget).where(
            SysCatTarget.cat_id == cat_id,
            SysCatTarget.target_type == target_type,
            SysCatTarget.target_id == target_id,
        )
        result = await db.execute(stmt)
        return result.rowcount

    async def delete_by_target(self, db: AsyncSession, target_type: str, target_id: int) -> int:
        stmt = delete(SysCatTarget).where(
            SysCatTarget.target_type == target_type,
            SysCatTarget.target_id == target_id,
        )
        result = await db.execute(stmt)
        return result.rowcount


sys_cat_dao: CRUDSysCat = CRUDSysCat(SysCat)
sys_cat_target_dao: CRUDSysCatTarget = CRUDSysCatTarget(SysCatTarget)
