#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from sqlalchemy import Select, String, and_, cast, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.quest.model import Quest, QuestClaim, QuestRewardLog


class CRUDQuest(CRUDPlus[Quest]):
    """悬赏任务数据库操作类"""

    async def get_by_code(self, db: AsyncSession, code: str) -> Quest | None:
        """
        根据任务码获取任务

        :param db: 数据库会话
        :param code: 任务码
        :return:
        """
        return await self.select_model_by_column(db, code__eq=code)

    async def lock_for_claim(self, db: AsyncSession, pk: int) -> Quest | None:
        """
        加行锁获取任务（用于领取时防超卖）

        :param db: 数据库会话
        :param pk: 任务 ID
        :return:
        """
        stmt = select(Quest).where(Quest.id == pk).with_for_update()
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def increment_claimed_count(self, db: AsyncSession, pk: int) -> None:
        """
        领取数累加 1

        :param db: 数据库会话
        :param pk: 任务 ID
        :return:
        """
        quest = await self.select_model(db, pk)
        if quest:
            await self.update_model(db, pk, {'claimed_count': quest.claimed_count + 1}, commit=False)

    async def get_select(
        self,
        status: int | None = None,
        keyword: str | None = None,
        only_active: bool = False,
        domain_code: str | None = None,
    ) -> Select:
        """
        获取任务列表查询表达式

        :param status: 状态过滤
        :param keyword: 搜索关键词（匹配名称/任务码）
        :param only_active: 是否只看进行中（status=1）
        :param domain_code: 领域码过滤
        :return:
        """
        stmt = select(Quest)

        conditions = []
        if status is not None:
            conditions.append(Quest.status == status)
        elif only_active:
            conditions.append(Quest.status == 1)

        if keyword:
            keyword_like = f'%{keyword}%'
            conditions.append(or_(Quest.name.like(keyword_like), Quest.code.like(keyword_like)))

        if domain_code:
            domain_like = f'%"{domain_code}"%'
            conditions.append(or_(Quest.domain_codes.is_(None), cast(Quest.domain_codes, String).like(domain_like)))

        if conditions:
            stmt = stmt.where(and_(*conditions))

        return stmt.order_by(Quest.sort.asc(), Quest.created_time.desc())


class CRUDQuestClaim(CRUDPlus[QuestClaim]):
    """悬赏任务领取记录数据库操作类"""

    async def count_active_by_user(self, db: AsyncSession, quest_id: int, user_id: int) -> int:
        """
        统计用户在某任务下未放弃的领取数

        :param db: 数据库会话
        :param quest_id: 任务 ID
        :param user_id: 用户 ID
        :return:
        """
        stmt = select(func.count()).where(
            QuestClaim.quest_id == quest_id,
            QuestClaim.user_id == user_id,
            QuestClaim.claim_status != 5,
        )
        result = await db.execute(stmt)
        return result.scalar() or 0

    async def get_active_claim(self, db: AsyncSession, quest_id: int, user_id: int) -> QuestClaim | None:
        """
        获取用户当前进行中的领取记录（claim_status=0）

        :param db: 数据库会话
        :param quest_id: 任务 ID
        :param user_id: 用户 ID
        :return:
        """
        return await self.select_model_by_column(
            db, quest_id__eq=quest_id, user_id__eq=user_id, claim_status__eq=0
        )

    async def get_latest_by_user(self, db: AsyncSession, quest_id: int, user_id: int) -> QuestClaim | None:
        """
        获取用户在某任务的最近一条领取记录

        :param db: 数据库会话
        :param quest_id: 任务 ID
        :param user_id: 用户 ID
        :return:
        """
        stmt = (
            select(QuestClaim)
            .where(QuestClaim.quest_id == quest_id, QuestClaim.user_id == user_id)
            .order_by(QuestClaim.created_time.desc())
            .limit(1)
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_select(
        self,
        quest_id: int | None = None,
        user_id: int | None = None,
        claim_status: int | None = None,
    ) -> Select:
        """
        获取领取记录列表查询表达式

        :param quest_id: 任务 ID
        :param user_id: 用户 ID
        :param claim_status: 领取状态
        :return:
        """
        filters = {}
        if quest_id is not None:
            filters['quest_id__eq'] = quest_id
        if user_id is not None:
            filters['user_id__eq'] = user_id
        if claim_status is not None:
            filters['claim_status__eq'] = claim_status
        return await self.select_order('created_time', 'desc', **filters)


class CRUDQuestRewardLog(CRUDPlus[QuestRewardLog]):
    """悬赏任务奖励发放流水数据库操作类"""

    async def get_by_claim(self, db: AsyncSession, claim_id: int) -> QuestRewardLog | None:
        """
        根据领取记录 ID 获取流水

        :param db: 数据库会话
        :param claim_id: 领取记录 ID
        :return:
        """
        return await self.select_model_by_column(db, claim_id__eq=claim_id)


quest_dao: CRUDQuest = CRUDQuest(Quest)
quest_claim_dao: CRUDQuestClaim = CRUDQuestClaim(QuestClaim)
quest_reward_log_dao: CRUDQuestRewardLog = CRUDQuestRewardLog(QuestRewardLog)
