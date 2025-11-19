#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.jia.crud.crud_diaries import diary_dao
from backend.app.jia.model.diaries import Diary
from backend.app.jia.schema.diaries import CreateDiaryParam, UpdateDiaryParam
from backend.common.exception import errors


class DiaryService:
    """日记服务类"""

    @staticmethod
    async def get(*, db: AsyncSession, pk: int) -> Diary:
        """
        获取日记详情

        :param db: 数据库会话
        :param pk: 日记 ID
        :return:
        """
        diary = await diary_dao.get(db, pk)
        if not diary:
            raise errors.NotFoundError(msg='日记不存在')
        return diary

    @staticmethod
    async def get_by_date(*, db: AsyncSession, date: int, user_id: int) -> Diary | None:
        """
        通过日期获取日记

        :param db: 数据库会话
        :param date: 日期时间戳
        :param user_id: 用户 ID
        :return:
        """
        return await diary_dao.get_by_date(db, date, user_id)

    @staticmethod
    async def get_list(
        *,
        db: AsyncSession,
        date_start: int | None = None,
        date_end: int | None = None,
        mood: str | None = None,
        weather: str | None = None,
        is_starred: int | None = None,
        is_pinned: int | None = None,
        priority: int | None = None,
        sync_status: str | None = None,
    ) -> list[Diary]:
        """
        获取日记列表

        :param db: 数据库会话
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
        select_stmt = await diary_dao.get_select(
            date_start, date_end, mood, weather, is_starred, is_pinned, priority, sync_status
        )
        diaries = await db.execute(select_stmt)
        return list(diaries.scalars().all())

    @staticmethod
    async def get_all(*, db: AsyncSession, user_id: int) -> list[Diary]:
        """
        获取所有日记

        :param db: 数据库会话
        :param user_id: 用户 ID
        :return:
        """
        return list(await diary_dao.get_all(db, user_id))

    @staticmethod
    async def create(*, db: AsyncSession, obj: CreateDiaryParam, user_id: int) -> None:
        """
        创建日记

        :param db: 数据库会话
        :param obj: 创建日记参数
        :param user_id: 用户 ID
        :return:
        """
        existing = await diary_dao.get_by_date(db, obj.date, user_id)
        if existing:
            raise errors.ConflictError(msg='该日期已存在日记')
        await diary_dao.create(db, obj, user_id)

    @staticmethod
    async def update(*, db: AsyncSession, pk: int, obj: UpdateDiaryParam, user_id: int) -> int:
        """
        更新日记

        :param db: 数据库会话
        :param pk: 日记 ID
        :param obj: 更新日记参数
        :param user_id: 用户 ID
        :return:
        """
        diary = await diary_dao.get(db, pk)
        if not diary:
            raise errors.NotFoundError(msg='日记不存在')
        if obj.date is not None and obj.date != diary.date:
            existing = await diary_dao.get_by_date(db, obj.date, user_id)
            if existing and existing.id != pk:
                raise errors.ConflictError(msg='该日期已存在日记')
        count = await diary_dao.update(db, pk, obj, user_id)
        return count

    @staticmethod
    async def delete(*, db: AsyncSession, pks: list[int]) -> int:
        """
        批量删除日记

        :param db: 数据库会话
        :param pks: 日记 ID 列表
        :return:
        """
        count = await diary_dao.delete(db, pks)
        return count


diary_service: DiaryService = DiaryService()

