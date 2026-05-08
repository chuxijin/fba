#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.vocab.crud.crud_group import group_word_dao, word_group_dao
from backend.app.vocab.schema.group import CreateGroupParam, GetGroupDetail, GroupAddWordsParam, UpdateGroupParam
from backend.common.exception import errors
from backend.common.pagination import paging_data
from backend.utils.timezone import timezone


class GroupService:
    """学习组服务类"""

    @staticmethod
    async def create_group(*, db: AsyncSession, user_id: int, obj: CreateGroupParam) -> GetGroupDetail:
        """
        创建学习组

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param obj: 创建参数
        :return:
        """
        data = obj.model_dump()
        data['user_id'] = user_id
        group = await word_group_dao.create_model(db, data, commit=False)
        await db.commit()
        await db.refresh(group)
        detail = GetGroupDetail.model_validate(group)
        detail.word_count = 0
        return detail

    @staticmethod
    async def update_group(*, db: AsyncSession, pk: int, user_id: int, obj: UpdateGroupParam) -> int:
        """
        更新学习组

        :param db: 数据库会话
        :param pk: 学习组 ID
        :param user_id: 用户 ID
        :param obj: 更新参数
        :return:
        """
        group = await word_group_dao.select_model(db, pk)
        if not group or group.user_id != user_id:
            raise errors.NotFoundError(msg='学习组不存在')
        update_data = obj.model_dump(exclude_unset=True)
        if not update_data:
            return 0
        return await word_group_dao.update_model(db, pk, update_data)

    @staticmethod
    async def delete_group(*, db: AsyncSession, pk: int, user_id: int) -> int:
        """
        删除学习组

        :param db: 数据库会话
        :param pk: 学习组 ID
        :param user_id: 用户 ID
        :return:
        """
        group = await word_group_dao.select_model(db, pk)
        if not group or group.user_id != user_id:
            raise errors.NotFoundError(msg='学习组不存在')
        return await word_group_dao.delete_model(db, pk)

    @staticmethod
    async def get_group_list(*, db: AsyncSession, user_id: int) -> dict[str, Any]:
        """
        获取用户学习组列表

        :param db: 数据库会话
        :param user_id: 用户 ID
        :return:
        """
        stmt = await word_group_dao.get_select_by_user(user_id)
        return await paging_data(db, stmt)

    @staticmethod
    async def add_words(*, db: AsyncSession, pk: int, user_id: int, obj: GroupAddWordsParam) -> int:
        """
        向学习组添加单词

        :param db: 数据库会话
        :param pk: 学习组 ID
        :param user_id: 用户 ID
        :param obj: 添加参数
        :return:
        """
        group = await word_group_dao.select_model(db, pk)
        if not group or group.user_id != user_id:
            raise errors.NotFoundError(msg='学习组不存在')

        added = 0
        for word_id in obj.word_ids:
            existing = await group_word_dao.get_by_group_and_word(db, pk, word_id)
            if not existing:
                await group_word_dao.create_model(
                    db, {'group_id': pk, 'word_id': word_id, 'added_at': timezone.now()}, commit=False
                )
                added += 1
        if added > 0:
            await db.commit()
        return added

    @staticmethod
    async def remove_words(*, db: AsyncSession, pk: int, user_id: int, word_ids: list[int]) -> int:
        """
        从学习组移除单词

        :param db: 数据库会话
        :param pk: 学习组 ID
        :param user_id: 用户 ID
        :param word_ids: 单词 ID 列表
        :return:
        """
        group = await word_group_dao.select_model(db, pk)
        if not group or group.user_id != user_id:
            raise errors.NotFoundError(msg='学习组不存在')

        removed = 0
        for word_id in word_ids:
            existing = await group_word_dao.get_by_group_and_word(db, pk, word_id)
            if existing:
                await db.delete(existing)
                removed += 1
        if removed > 0:
            await db.commit()
        return removed


group_service: GroupService = GroupService()
