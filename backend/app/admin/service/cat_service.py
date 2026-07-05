#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from collections.abc import Sequence
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.admin.crud.crud_cat import sys_cat_dao, sys_cat_target_dao
from backend.app.admin.model.cat import SysCat, SysCatTarget
from backend.app.admin.schema.cat import (
    BatchBindCatsParam,
    CreateSysCatParam,
    CreateSysCatTargetParam,
    GetSysCatTargetWithCat,
    GetSysCatTree,
    UpdateSysCatParam,
)
from backend.common.exception import errors


class SysCatService:
    """分类服务类"""

    @staticmethod
    async def get(*, db: AsyncSession, pk: int) -> SysCat:
        cat = await sys_cat_dao.get(db, pk)
        if not cat:
            raise errors.NotFoundError(msg='分类不存在')
        return cat

    @staticmethod
    async def get_tree(
        *,
        db: AsyncSession,
        app_code: str | None = None,
        user_id: int | None = None,
        status: bool | None = None,
    ) -> list[GetSysCatTree]:
        rows = await sys_cat_dao.get_with_target_count(
            db, app_code=app_code, user_id=user_id, status=status
        )
        flat = [GetSysCatTree(**row) for row in rows]
        return SysCatService._build_tree(flat)

    @staticmethod
    def _build_tree(items: list[GetSysCatTree]) -> list[GetSysCatTree]:
        by_id = {item.id: item for item in items}
        roots: list[GetSysCatTree] = []
        for item in items:
            if item.parent_id and item.parent_id in by_id:
                parent = by_id[item.parent_id]
                if parent.children is None:
                    parent.children = []
                parent.children.append(item)
            else:
                roots.append(item)
        return roots

    @staticmethod
    async def create(*, db: AsyncSession, obj: CreateSysCatParam, created_by: int) -> SysCat:
        existing = await sys_cat_dao.get_by_name(
            db, app_code=obj.app_code, name=obj.name, parent_id=obj.parent_id, user_id=obj.user_id
        )
        if existing:
            raise errors.ConflictError(msg=f'分类 "{obj.name}" 已存在')
        return await sys_cat_dao.create(db, obj, created_by=created_by)

    @staticmethod
    async def update(*, db: AsyncSession, pk: int, obj: UpdateSysCatParam, updated_by: int) -> int:
        cat = await SysCatService.get(db=db, pk=pk)
        if obj.name is not None:
            existing = await sys_cat_dao.get_by_name(
                db, app_code=cat.app_code, name=obj.name, parent_id=obj.parent_id or cat.parent_id, user_id=cat.user_id
            )
            if existing and existing.id != pk:
                raise errors.ConflictError(msg=f'分类 "{obj.name}" 已存在')
        return await sys_cat_dao.update(db, pk, obj, updated_by=updated_by)

    @staticmethod
    async def delete(*, db: AsyncSession, pk: int) -> int:
        await SysCatService.get(db=db, pk=pk)
        has_children = await sys_cat_dao.has_children(db, pk)
        if has_children:
            raise errors.ForbiddenError(msg='请先删除子分类')
        return await sys_cat_dao.delete(db, pk)


class SysCatTargetService:
    """分类关联服务类"""

    @staticmethod
    async def get_targets(
        *, db: AsyncSession, target_type: str, target_id: int
    ) -> list[GetSysCatTargetWithCat]:
        rows = await sys_cat_target_dao.get_targets_with_cat(db, target_type=target_type, target_id=target_id)
        return [GetSysCatTargetWithCat(**row) for row in rows]

    @staticmethod
    async def bind(*, db: AsyncSession, obj: CreateSysCatTargetParam, created_by: int | None = None) -> SysCatTarget:
        cat = await sys_cat_dao.get(db, obj.cat_id)
        if not cat:
            raise errors.NotFoundError(msg='分类不存在')
        if not cat.status:
            raise errors.ForbiddenError(msg='分类已禁用')

        existing = await sys_cat_target_dao.get_by_cat_and_target(
            db, cat_id=obj.cat_id, target_type=obj.target_type, target_id=obj.target_id
        )
        if existing:
            raise errors.ConflictError(msg='分类已绑定到该目标')

        return await sys_cat_target_dao.create(
            db, cat_id=obj.cat_id, target_type=obj.target_type, target_id=obj.target_id, created_by=created_by
        )

    @staticmethod
    async def batch_bind(*, db: AsyncSession, obj: BatchBindCatsParam, created_by: int | None = None) -> int:
        count = 0
        for cat_id in obj.cat_ids:
            existing = await sys_cat_target_dao.get_by_cat_and_target(
                db, cat_id=cat_id, target_type=obj.target_type, target_id=obj.target_id
            )
            if existing:
                continue
            await sys_cat_target_dao.create(
                db, cat_id=cat_id, target_type=obj.target_type, target_id=obj.target_id, created_by=created_by
            )
            count += 1
        return count

    @staticmethod
    async def unbind(*, db: AsyncSession, pk: int) -> int:
        target = await sys_cat_target_dao.get(db, pk)
        if not target:
            raise errors.NotFoundError(msg='分类关联不存在')
        return await sys_cat_target_dao.delete(db, pk)


sys_cat_service: SysCatService = SysCatService()
sys_cat_target_service: SysCatTargetService = SysCatTargetService()
