#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.jia.crud.crud_tag import tag_dao
from backend.app.jia.model.tag import Tag
from backend.app.jia.schema.tag import CreateTagParam, UpdateTagParam
from backend.common.exception import errors


class TagService:
    """标签服务类"""

    @staticmethod
    async def get(*, db: AsyncSession, pk: int) -> Tag:
        """
        获取标签详情

        :param db: 数据库会话
        :param pk: 标签 ID
        :return:
        """
        tag = await tag_dao.get(db, pk)
        if not tag:
            raise errors.NotFoundError(msg='标签不存在')
        return tag

    @staticmethod
    async def get_list(
        *,
        db: AsyncSession,
        name: str | None = None,
        sync_status: str | None = None,
    ) -> list[Tag]:
        """
        获取标签列表

        :param db: 数据库会话
        :param name: 标签名称
        :param sync_status: 同步状态
        :return:
        """
        select_stmt = await tag_dao.get_select(name, sync_status)
        tags = await db.execute(select_stmt)
        return list(tags.scalars().all())

    @staticmethod
    async def get_all(*, db: AsyncSession, user_id: int) -> list[Tag]:
        """
        获取所有标签

        :param db: 数据库会话
        :param user_id: 用户 ID
        :return:
        """
        return list(await tag_dao.get_all(db, user_id))

    @staticmethod
    async def create(*, db: AsyncSession, obj: CreateTagParam, user_id: int) -> None:
        """
        创建标签

        :param db: 数据库会话
        :param obj: 创建标签参数
        :param user_id: 用户 ID
        :return:
        """
        existing = await tag_dao.get_by_name(db, obj.name, user_id)
        if existing:
            raise errors.ConflictError(msg='标签名称已存在')
        await tag_dao.create(db, obj, user_id)

    @staticmethod
    async def update(*, db: AsyncSession, pk: int, obj: UpdateTagParam, user_id: int) -> int:
        """
        更新标签

        :param db: 数据库会话
        :param pk: 标签 ID
        :param obj: 更新标签参数
        :param user_id: 用户 ID
        :return:
        """
        tag = await tag_dao.get(db, pk)
        if not tag:
            raise errors.NotFoundError(msg='标签不存在')
        if obj.name and obj.name != tag.name:
            existing = await tag_dao.get_by_name(db, obj.name, user_id)
            if existing:
                raise errors.ConflictError(msg='标签名称已存在')
        count = await tag_dao.update(db, pk, obj, user_id)
        return count

    @staticmethod
    async def delete(*, db: AsyncSession, pks: list[int]) -> int:
        """
        批量删除标签

        :param db: 数据库会话
        :param pks: 标签 ID 列表
        :return:
        """
        count = await tag_dao.delete(db, pks)
        return count


tag_service: TagService = TagService()

