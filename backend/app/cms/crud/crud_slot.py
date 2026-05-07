#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime

from sqlalchemy import Select, and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.cms.model import CmsSlot, CmsSlotLog


class CRUDCmsSlot(CRUDPlus[CmsSlot]):
    """内容运营位数据库操作类"""

    async def get_by_code(self, db: AsyncSession, code: str) -> CmsSlot | None:
        """
        根据业务码获取运营位

        :param db: 数据库会话
        :param code: 业务码
        :return:
        """
        return await self.select_model_by_column(db, code__eq=code)

    async def get_active_candidates(self, db: AsyncSession, scene: str, now: datetime) -> list[CmsSlot]:
        """
        获取场景下当前生效的候选运营位列表(按 priority desc 排序)

        :param db: 数据库会话
        :param scene: 触发场景
        :param now: 当前时间
        :return:
        """
        stmt = (
            select(CmsSlot)
            .where(
                CmsSlot.status == 1,
                CmsSlot.scene == scene,
                or_(CmsSlot.start_time.is_(None), CmsSlot.start_time <= now),
                or_(CmsSlot.end_time.is_(None), CmsSlot.end_time >= now),
            )
            .order_by(CmsSlot.priority.desc(), CmsSlot.id.asc())
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def get_select(
        self,
        status: int | None = None,
        slot_type: str | None = None,
        scene: str | None = None,
        keyword: str | None = None,
    ) -> Select:
        """
        获取运营位列表查询表达式

        :param status: 状态过滤
        :param slot_type: 形态过滤
        :param scene: 场景过滤
        :param keyword: 关键词(匹配 code/name/title)
        :return:
        """
        stmt = select(CmsSlot)

        conditions = []
        if status is not None:
            conditions.append(CmsSlot.status == status)
        if slot_type:
            conditions.append(CmsSlot.slot_type == slot_type)
        if scene:
            conditions.append(CmsSlot.scene == scene)
        if keyword:
            keyword_like = f'%{keyword}%'
            conditions.append(
                or_(CmsSlot.code.like(keyword_like), CmsSlot.name.like(keyword_like), CmsSlot.title.like(keyword_like))
            )

        if conditions:
            stmt = stmt.where(and_(*conditions))

        return stmt.order_by(CmsSlot.priority.desc(), CmsSlot.created_time.desc())


class CRUDCmsSlotLog(CRUDPlus[CmsSlotLog]):
    """内容运营位行为流水数据库操作类"""

    async def count_by_action(
        self,
        db: AsyncSession,
        *,
        slot_id: int,
        user_id: int,
        action: int,
        since: datetime | None = None,
    ) -> int:
        """
        统计某用户在某运营位的某种行为次数

        :param db: 数据库会话
        :param slot_id: 运营位 ID
        :param user_id: 用户 ID
        :param action: 行为类型(0 曝光 1 点击 2 关闭)
        :param since: 起始时间(包含)
        :return:
        """
        stmt = select(func.count()).where(
            CmsSlotLog.slot_id == slot_id,
            CmsSlotLog.user_id == user_id,
            CmsSlotLog.action == action,
        )
        if since is not None:
            stmt = stmt.where(CmsSlotLog.created_time >= since)
        result = await db.execute(stmt)
        return result.scalar() or 0

    async def aggregate_actions(self, db: AsyncSession, *, slot_id: int, since: datetime) -> dict[int, int]:
        """
        按行为类型聚合某运营位指定时间段内的次数

        :param db: 数据库会话
        :param slot_id: 运营位 ID
        :param since: 起始时间(包含)
        :return:
        """
        stmt = (
            select(CmsSlotLog.action, func.count())
            .where(CmsSlotLog.slot_id == slot_id, CmsSlotLog.created_time >= since)
            .group_by(CmsSlotLog.action)
        )
        rows = (await db.execute(stmt)).all()
        return {action: cnt for action, cnt in rows}


cms_slot_dao: CRUDCmsSlot = CRUDCmsSlot(CmsSlot)
cms_slot_log_dao: CRUDCmsSlotLog = CRUDCmsSlotLog(CmsSlotLog)
