#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.quest.crud.crud_quest import quest_claim_dao, quest_dao
from backend.app.quest.model import Quest
from backend.app.quest.schema.quest import (
    CreateQuestParam,
    GetQuestDetail,
    GetQuestWithUserDetail,
    UpdateQuestParam,
)
from backend.common.exception import errors
from backend.common.pagination import paging_data


class QuestService:
    """悬赏任务服务类"""

    @staticmethod
    async def create_quest(*, db: AsyncSession, user_id: int, obj: CreateQuestParam) -> GetQuestDetail:
        """
        创建任务

        :param db: 数据库会话
        :param user_id: 创建者用户 ID
        :param obj: 创建参数
        :return:
        """
        existing = await quest_dao.get_by_code(db, obj.code)
        if existing:
            raise errors.ConflictError(msg='任务码已存在')

        quest = await quest_dao.create_model(db, obj, created_by=user_id, commit=False)
        await db.commit()
        await db.refresh(quest)
        return GetQuestDetail.model_validate(quest)

    @staticmethod
    async def update_quest(*, db: AsyncSession, pk: int, obj: UpdateQuestParam) -> int:
        """
        更新任务

        :param db: 数据库会话
        :param pk: 任务 ID
        :param obj: 更新参数
        :return:
        """
        quest = await quest_dao.select_model(db, pk)
        if not quest:
            raise errors.NotFoundError(msg='任务不存在')

        update_data = obj.model_dump(exclude_unset=True)
        if not update_data:
            return 0
        return await quest_dao.update_model(db, pk, update_data)

    @staticmethod
    async def delete_quest(*, db: AsyncSession, pk: int) -> int:
        """
        删除任务（物理删除）

        :param db: 数据库会话
        :param pk: 任务 ID
        :return:
        """
        quest = await quest_dao.select_model(db, pk)
        if not quest:
            raise errors.NotFoundError(msg='任务不存在')
        return await quest_dao.delete_model(db, pk)

    @staticmethod
    async def get_quest(*, db: AsyncSession, pk: int) -> Quest:
        """
        获取任务实体

        :param db: 数据库会话
        :param pk: 任务 ID
        :return:
        """
        quest = await quest_dao.select_model(db, pk)
        if not quest:
            raise errors.NotFoundError(msg='任务不存在')
        return quest

    @staticmethod
    async def get_quest_detail(*, db: AsyncSession, pk: int) -> GetQuestDetail:
        """
        获取任务详情

        :param db: 数据库会话
        :param pk: 任务 ID
        :return:
        """
        quest = await QuestService.get_quest(db=db, pk=pk)
        return GetQuestDetail.model_validate(quest)

    @staticmethod
    async def get_quest_detail_with_user(
        *, db: AsyncSession, pk: int, user_id: int | None
    ) -> GetQuestWithUserDetail:
        """
        获取任务详情（含当前用户参与状态）

        :param db: 数据库会话
        :param pk: 任务 ID
        :param user_id: 当前用户 ID
        :return:
        """
        quest = await QuestService.get_quest(db=db, pk=pk)
        detail = GetQuestWithUserDetail.model_validate(quest)

        if user_id is None:
            return detail

        my_count = await quest_claim_dao.count_active_by_user(db, pk, user_id)
        active_claim = await quest_claim_dao.get_active_claim(db, pk, user_id)
        latest_claim = await quest_claim_dao.get_latest_by_user(db, pk, user_id)

        detail.my_claim_count = my_count
        detail.my_active_claim_id = active_claim.id if active_claim else None
        detail.my_latest_claim_status = latest_claim.claim_status if latest_claim else None
        progress_source = active_claim or latest_claim
        detail.my_current_progress = progress_source.progress if progress_source else 0
        return detail

    @staticmethod
    async def get_quest_list(
        *,
        db: AsyncSession,
        status: int | None = None,
        keyword: str | None = None,
        only_active: bool = False,
    ) -> dict[str, Any]:
        """
        获取任务列表

        :param db: 数据库会话
        :param status: 状态过滤
        :param keyword: 关键词
        :param only_active: 是否只看进行中
        :return:
        """
        stmt = await quest_dao.get_select(status=status, keyword=keyword, only_active=only_active)
        return await paging_data(db, stmt)


quest_service: QuestService = QuestService()
