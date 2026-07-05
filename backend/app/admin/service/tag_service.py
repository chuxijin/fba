#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.admin.crud.crud_tag import sys_tag_dao, sys_tag_target_dao
from backend.app.admin.model.tag import SysTag, SysTagTarget
from backend.app.admin.schema.tag import (
    BatchBindTagsParam,
    CreateSysTagParam,
    CreateSysTagTargetParam,
    GetSysTagListItem,
    GetSysTagTargetWithTag,
    UpdateSysTagParam,
)
from backend.common.exception import errors


class SysTagService:
    """标签服务类"""

    @staticmethod
    async def get(*, db: AsyncSession, pk: int) -> SysTag:
        """
        获取标签

        :param db: 数据库会话
        :param pk: 标签 ID
        :return:
        """
        tag = await sys_tag_dao.get(db, pk)
        if not tag:
            raise errors.NotFoundError(msg='标签不存在')
        return tag

    @staticmethod
    async def get_list(
        *,
        db: AsyncSession,
        app_code: str | None = None,
        user_id: int | None = None,
        name: str | None = None,
        status: bool | None = None,
    ) -> list[GetSysTagListItem]:
        """
        获取标签列表（含关联目标数）

        :param db: 数据库会话
        :param app_code: 应用标识
        :param user_id: 用户 ID
        :param name: 标签名称
        :param status: 状态
        :return:
        """
        rows = await sys_tag_dao.get_with_target_count(
            db,
            app_code=app_code,
            user_id=user_id,
            name=name,
            status=status,
        )
        return [GetSysTagListItem(**row) for row in rows]

    @staticmethod
    async def create(*, db: AsyncSession, obj: CreateSysTagParam, created_by: int | None = None) -> SysTag:
        """
        创建标签

        :param db: 数据库会话
        :param obj: 创建标签参数
        :param created_by: 创建者 ID
        :return:
        """
        existing = await sys_tag_dao.get_by_name(
            db,
            app_code=obj.app_code,
            name=obj.name,
            user_id=obj.user_id,
        )
        if existing:
            raise errors.ConflictError(msg=f'标签 "{obj.name}" 已存在')
        return await sys_tag_dao.create(db, obj, created_by=created_by)

    @staticmethod
    async def update(*, db: AsyncSession, pk: int, obj: UpdateSysTagParam) -> int:
        """
        更新标签

        :param db: 数据库会话
        :param pk: 标签 ID
        :param obj: 更新标签参数
        :return:
        """
        await SysTagService.get(db=db, pk=pk)
        if obj.name is not None:
            tag = await SysTagService.get(db=db, pk=pk)
            existing = await sys_tag_dao.get_by_name(
                db,
                app_code=tag.app_code,
                name=obj.name,
                user_id=tag.user_id,
            )
            if existing and existing.id != pk:
                raise errors.ConflictError(msg=f'标签 "{obj.name}" 已存在')
        return await sys_tag_dao.update(db, pk, obj)

    @staticmethod
    async def delete(*, db: AsyncSession, pk: int) -> int:
        """
        删除标签

        :param db: 数据库会话
        :param pk: 标签 ID
        :return:
        """
        await SysTagService.get(db=db, pk=pk)
        return await sys_tag_dao.delete(db, pk)


class SysTagTargetService:
    """标签关联服务类"""

    @staticmethod
    async def get_targets(
        *,
        db: AsyncSession,
        target_type: str,
        target_id: int,
    ) -> list[GetSysTagTargetWithTag]:
        """
        获取目标的所有标签（含标签信息）

        :param db: 数据库会话
        :param target_type: 目标类型
        :param target_id: 目标 ID
        :return:
        """
        rows = await sys_tag_target_dao.get_targets_with_tag(
            db,
            target_type=target_type,
            target_id=target_id,
        )
        return [GetSysTagTargetWithTag(**row) for row in rows]

    @staticmethod
    async def bind(*, db: AsyncSession, obj: CreateSysTagTargetParam, created_by: int | None = None) -> SysTagTarget:
        """
        绑定标签到目标

        :param db: 数据库会话
        :param obj: 绑定参数
        :param created_by: 创建者 ID
        :return:
        """
        tag = await sys_tag_dao.get(db, obj.tag_id)
        if not tag:
            raise errors.NotFoundError(msg='标签不存在')
        if not tag.status:
            raise errors.ForbiddenError(msg='标签已禁用')

        existing = await sys_tag_target_dao.get_by_tag_and_target(
            db,
            tag_id=obj.tag_id,
            target_type=obj.target_type,
            target_id=obj.target_id,
        )
        if existing:
            raise errors.ConflictError(msg='标签已绑定到该目标')

        return await sys_tag_target_dao.create(
            db,
            tag_id=obj.tag_id,
            target_type=obj.target_type,
            target_id=obj.target_id,
            created_by=created_by,
        )

    @staticmethod
    async def batch_bind(*, db: AsyncSession, obj: BatchBindTagsParam, created_by: int | None = None) -> int:
        """
        批量绑定标签到目标

        :param db: 数据库会话
        :param obj: 批量绑定参数
        :param created_by: 创建者 ID
        :return:
        """
        count = 0
        for tag_id in obj.tag_ids:
            existing = await sys_tag_target_dao.get_by_tag_and_target(
                db,
                tag_id=tag_id,
                target_type=obj.target_type,
                target_id=obj.target_id,
            )
            if existing:
                continue
            await sys_tag_target_dao.create(
                db,
                tag_id=tag_id,
                target_type=obj.target_type,
                target_id=obj.target_id,
                created_by=created_by,
            )
            count += 1
        return count

    @staticmethod
    async def unbind(*, db: AsyncSession, pk: int) -> int:
        """
        解绑标签关联

        :param db: 数据库会话
        :param pk: 关联 ID
        :return:
        """
        target = await sys_tag_target_dao.get(db, pk)
        if not target:
            raise errors.NotFoundError(msg='标签关联不存在')
        return await sys_tag_target_dao.delete(db, pk)

    @staticmethod
    async def unbind_by_tag_and_target(
        *,
        db: AsyncSession,
        tag_id: int,
        target_type: str,
        target_id: int,
    ) -> int:
        """
        解绑指定标签与目标的关联

        :param db: 数据库会话
        :param tag_id: 标签 ID
        :param target_type: 目标类型
        :param target_id: 目标 ID
        :return:
        """
        return await sys_tag_target_dao.delete_by_tag_and_target(
            db,
            tag_id=tag_id,
            target_type=target_type,
            target_id=target_id,
        )

    @staticmethod
    async def unbind_all(*, db: AsyncSession, target_type: str, target_id: int) -> int:
        """
        解绑目标的所有标签

        :param db: 数据库会话
        :param target_type: 目标类型
        :param target_id: 目标 ID
        :return:
        """
        return await sys_tag_target_dao.delete_by_target(
            db,
            target_type=target_type,
            target_id=target_id,
        )


sys_tag_service: SysTagService = SysTagService()
sys_tag_target_service: SysTagTargetService = SysTagTargetService()
