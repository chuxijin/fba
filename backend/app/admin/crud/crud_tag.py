#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from collections.abc import Sequence

from sqlalchemy import Select, delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.admin.model.tag import SysTag, SysTagTarget
from backend.app.admin.schema.tag import CreateSysTagParam, UpdateSysTagParam


class CRUDSysTag(CRUDPlus[SysTag]):
    """标签数据库操作类"""

    async def get(self, db: AsyncSession, pk: int) -> SysTag | None:
        """
        获取标签

        :param db: 数据库会话
        :param pk: 标签 ID
        :return:
        """
        return await self.select_model(db, pk)

    async def get_by_name(self, db: AsyncSession, app_code: str, name: str, user_id: int | None) -> SysTag | None:
        """
        通过名称获取标签

        :param db: 数据库会话
        :param app_code: 应用标识
        :param name: 标签名称
        :param user_id: 用户 ID
        :return:
        """
        return await self.select_model_by_column(db, app_code=app_code, name=name, user_id=user_id)

    async def get_all(
        self,
        db: AsyncSession,
        app_code: str | None = None,
        user_id: int | None = None,
        name: str | None = None,
        status: bool | None = None,
    ) -> Sequence[SysTag]:
        """
        获取标签列表

        :param db: 数据库会话
        :param app_code: 应用标识
        :param user_id: 用户 ID
        :param name: 标签名称
        :param status: 状态
        :return:
        """
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
        """
        获取标签列表查询表达式

        :param app_code: 应用标识
        :param user_id: 用户 ID
        :param name: 标签名称
        :param status: 状态
        :return:
        """
        stmt = select(SysTag).order_by(SysTag.sort_order.asc())

        if app_code is not None:
            stmt = stmt.where(SysTag.app_code == app_code)
        if user_id is not None:
            stmt = stmt.where(SysTag.user_id == user_id)
        if name is not None:
            stmt = stmt.where(SysTag.name.like(f'%{name}%'))
        if status is not None:
            stmt = stmt.where(SysTag.status == status)

        return stmt

    async def create(self, db: AsyncSession, obj: CreateSysTagParam, created_by: int | None = None) -> SysTag:
        """
        创建标签

        :param db: 数据库会话
        :param obj: 创建标签参数
        :param created_by: 创建者 ID
        :return:
        """
        data = obj.model_dump()
        data['created_by'] = created_by
        new_tag = self.model(**data)
        db.add(new_tag)
        await db.flush()
        return new_tag

    async def update(self, db: AsyncSession, pk: int, obj: UpdateSysTagParam) -> int:
        """
        更新标签

        :param db: 数据库会话
        :param pk: 标签 ID
        :param obj: 更新标签参数
        :return:
        """
        update_data = obj.model_dump(exclude_unset=True)
        return await self.update_model_by_column(db, update_data, id=pk)

    async def delete(self, db: AsyncSession, pk: int) -> int:
        """
        删除标签

        :param db: 数据库会话
        :param pk: 标签 ID
        :return:
        """
        return await self.delete_model(db, pk)

    async def get_with_target_count(
        self,
        db: AsyncSession,
        app_code: str | None = None,
        user_id: int | None = None,
        name: str | None = None,
        status: bool | None = None,
    ) -> list[dict]:
        """
        获取标签列表（含关联目标数）

        :param db: 数据库会话
        :param app_code: 应用标识
        :param user_id: 用户 ID
        :param name: 标签名称
        :param status: 状态
        :return:
        """
        stmt = (
            select(
                SysTag,
                func.coalesce(func.count(SysTagTarget.id), 0).label('target_count'),
            )
            .outerjoin(SysTagTarget, SysTagTarget.tag_id == SysTag.id)
            .group_by(SysTag.id)
            .order_by(SysTag.sort_order.asc())
        )

        if app_code is not None:
            stmt = stmt.where(SysTag.app_code == app_code)
        if user_id is not None:
            stmt = stmt.where(SysTag.user_id == user_id)
        if name is not None:
            stmt = stmt.where(SysTag.name.like(f'%{name}%'))
        if status is not None:
            stmt = stmt.where(SysTag.status == status)

        result = await db.execute(stmt)
        rows = result.all()
        return [
            {
                'id': tag.id,
                'name': tag.name,
                'color': tag.color,
                'icon': tag.icon,
                'app_code': tag.app_code,
                'user_id': tag.user_id,
                'sort_order': tag.sort_order,
                'status': tag.status,
                'remark': tag.remark,
                'created_by': tag.created_by,
                'created_time': tag.created_time,
                'updated_time': tag.updated_time,
                'target_count': int(target_count),
            }
            for tag, target_count in rows
        ]


class CRUDSysTagTarget(CRUDPlus[SysTagTarget]):
    """标签关联数据库操作类"""

    async def get(self, db: AsyncSession, pk: int) -> SysTagTarget | None:
        """
        获取标签关联

        :param db: 数据库会话
        :param pk: 关联 ID
        :return:
        """
        return await self.select_model(db, pk)

    async def get_by_target(
        self,
        db: AsyncSession,
        target_type: str,
        target_id: int,
    ) -> Sequence[SysTagTarget]:
        """
        获取目标的所有标签关联

        :param db: 数据库会话
        :param target_type: 目标类型
        :param target_id: 目标 ID
        :return:
        """
        return await self.select_models(db, target_type=target_type, target_id=target_id)

    async def get_by_tag_and_target(
        self,
        db: AsyncSession,
        tag_id: int,
        target_type: str,
        target_id: int,
    ) -> SysTagTarget | None:
        """
        获取标签与目标的关联

        :param db: 数据库会话
        :param tag_id: 标签 ID
        :param target_type: 目标类型
        :param target_id: 目标 ID
        :return:
        """
        return await self.select_model_by_column(
            db,
            tag_id=tag_id,
            target_type=target_type,
            target_id=target_id,
        )

    async def get_targets_with_tag(
        self,
        db: AsyncSession,
        target_type: str,
        target_id: int,
    ) -> list[dict]:
        """
        获取目标的所有标签关联（含标签信息）

        :param db: 数据库会话
        :param target_type: 目标类型
        :param target_id: 目标 ID
        :return:
        """
        stmt = (
            select(SysTagTarget, SysTag.name, SysTag.color, SysTag.icon)
            .join(SysTag, SysTag.id == SysTagTarget.tag_id)
            .where(
                SysTagTarget.target_type == target_type,
                SysTagTarget.target_id == target_id,
            )
            .order_by(SysTag.sort_order.asc())
        )
        result = await db.execute(stmt)
        rows = result.all()
        return [
            {
                'id': row[0].id,
                'tag_id': row[0].tag_id,
                'target_type': row[0].target_type,
                'target_id': row[0].target_id,
                'created_by': row[0].created_by,
                'created_time': row[0].created_time,
                'tag_name': row[1],
                'tag_color': row[2],
                'tag_icon': row[3],
            }
            for row in rows
        ]

    async def get_target_ids_by_tags(
        self,
        db: AsyncSession,
        target_type: str,
        tag_ids: list[int],
    ) -> list[int]:
        """
        通过标签获取目标 ID 列表

        :param db: 数据库会话
        :param target_type: 目标类型
        :param tag_ids: 标签 ID 列表
        :return:
        """
        stmt = (
            select(SysTagTarget.target_id)
            .where(
                SysTagTarget.target_type == target_type,
                SysTagTarget.tag_id.in_(tag_ids),
            )
            .group_by(SysTagTarget.target_id)
            .having(func.count(SysTagTarget.tag_id) == len(tag_ids))
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def create(self, db: AsyncSession, tag_id: int, target_type: str, target_id: int, created_by: int | None = None) -> SysTagTarget:
        """
        创建标签关联

        :param db: 数据库会话
        :param tag_id: 标签 ID
        :param target_type: 目标类型
        :param target_id: 目标 ID
        :param created_by: 创建者 ID
        :return:
        """
        target = self.model(
            tag_id=tag_id,
            target_type=target_type,
            target_id=target_id,
            created_by=created_by,
        )
        db.add(target)
        await db.flush()
        return target

    async def delete(self, db: AsyncSession, pk: int) -> int:
        """
        删除标签关联

        :param db: 数据库会话
        :param pk: 关联 ID
        :return:
        """
        return await self.delete_model(db, pk)

    async def delete_by_tag_and_target(
        self,
        db: AsyncSession,
        tag_id: int,
        target_type: str,
        target_id: int,
    ) -> int:
        """
        删除标签与目标的关联

        :param db: 数据库会话
        :param tag_id: 标签 ID
        :param target_type: 目标类型
        :param target_id: 目标 ID
        :return:
        """
        stmt = delete(SysTagTarget).where(
            SysTagTarget.tag_id == tag_id,
            SysTagTarget.target_type == target_type,
            SysTagTarget.target_id == target_id,
        )
        result = await db.execute(stmt)
        return result.rowcount

    async def delete_by_target(self, db: AsyncSession, target_type: str, target_id: int) -> int:
        """
        删除目标的所有标签关联

        :param db: 数据库会话
        :param target_type: 目标类型
        :param target_id: 目标 ID
        :return:
        """
        stmt = delete(SysTagTarget).where(
            SysTagTarget.target_type == target_type,
            SysTagTarget.target_id == target_id,
        )
        result = await db.execute(stmt)
        return result.rowcount


sys_tag_dao: CRUDSysTag = CRUDSysTag(SysTag)
sys_tag_target_dao: CRUDSysTagTarget = CRUDSysTagTarget(SysTagTarget)
