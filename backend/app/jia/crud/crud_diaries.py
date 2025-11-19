#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from collections.abc import Sequence

from sqlalchemy import Select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.jia.model.diaries import Diary
from backend.app.jia.schema.diaries import CreateDiaryParam, UpdateDiaryParam


class CRUDDiary(CRUDPlus[Diary]):
    """日记数据库操作类"""

    async def get(self, db: AsyncSession, diary_id: int) -> Diary | None:
        """
        获取日记详情

        :param db: 数据库会话
        :param diary_id: 日记 ID
        :return:
        """
        return await self.select_model_by_column(db, id=diary_id, deleted_at=None)

    async def get_by_server_id(self, db: AsyncSession, server_id: str) -> Diary | None:
        """
        通过服务器 ID 获取日记

        :param db: 数据库会话
        :param server_id: 服务器 ID
        :return:
        """
        return await self.select_model_by_column(db, server_id=server_id, deleted_at=None)

    async def get_by_date(self, db: AsyncSession, date: int, user_id: int) -> Diary | None:
        """
        通过日期获取日记

        :param db: 数据库会话
        :param date: 日期时间戳
        :param user_id: 用户 ID
        :return:
        """
        return await self.select_model_by_column(db, date=date, created_by=user_id, deleted_at=None)

    async def get_select(
        self,
        date_start: int | None,
        date_end: int | None,
        mood: str | None,
        weather: str | None,
        is_starred: int | None,
        is_pinned: int | None,
        priority: int | None,
        sync_status: str | None,
    ) -> Select:
        """
        获取日记列表查询表达式

        :param date_start: 开始日期时间戳
        :param date_end: 结束日期时间戳
        :param mood: 主要心情
        :param weather: 天气
        :param is_starred: 是否星标
        :param is_pinned: 是否置顶
        :param priority: 优先级
        :param sync_status: 同步状态
        :return:
        """
        filters = {'deleted_at': None}

        if date_start is not None:
            filters['date__ge'] = date_start
        if date_end is not None:
            filters['date__le'] = date_end
        if mood is not None:
            filters['mood'] = mood
        if weather is not None:
            filters['weather'] = weather
        if is_starred is not None:
            filters['is_starred'] = is_starred
        if is_pinned is not None:
            filters['is_pinned'] = is_pinned
        if priority is not None:
            filters['priority'] = priority
        if sync_status is not None:
            filters['sync_status'] = sync_status

        return await self.select_order('date', 'desc', **filters)

    async def get_all(self, db: AsyncSession, user_id: int) -> Sequence[Diary]:
        """
        获取所有日记

        :param db: 数据库会话
        :param user_id: 用户 ID
        :return:
        """
        return await self.select_models_order(db, 'date', 'desc', created_by=user_id, deleted_at=None)

    async def create(self, db: AsyncSession, obj: CreateDiaryParam, user_id: int) -> Diary:
        """
        创建日记

        :param db: 数据库会话
        :param obj: 创建日记参数
        :param user_id: 用户 ID
        :return:
        """
        dict_obj = obj.model_dump()
        dict_obj['created_by'] = user_id
        return await self.create_model(db, dict_obj, commit=False)

    async def update(self, db: AsyncSession, diary_id: int, obj: UpdateDiaryParam, user_id: int) -> int:
        """
        更新日记

        :param db: 数据库会话
        :param diary_id: 日记 ID
        :param obj: 更新日记参数
        :param user_id: 用户 ID
        :return:
        """
        dict_obj = obj.model_dump(exclude_unset=True)
        dict_obj['updated_by'] = user_id
        return await self.update_model(db, diary_id, dict_obj)

    async def delete(self, db: AsyncSession, pks: list[int]) -> int:
        """
        批量软删除日记

        :param db: 数据库会话
        :param pks: 日记 ID 列表
        :return:
        """
        import time
        deleted_at = int(time.time())
        count = 0
        for pk in pks:
            count += await self.update_model_by_column(db, {'deleted_at': deleted_at}, id=pk)
        return count


diary_dao: CRUDDiary = CRUDDiary(Diary)

