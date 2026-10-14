#!/usr/bin/env python3
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.admin.model.user import User
from backend.app.payment.model.group_buy import (
    PayGroupBuyActivity,
    PayGroupBuyMember,
    PayGroupBuyTask,
    PayGroupBuyTeam,
)
from backend.utils.timezone import timezone


class CRUDGroupBuy(CRUDPlus[PayGroupBuyTeam]):
    async def team(self, db: AsyncSession, code: str, *, lock: bool = False) -> PayGroupBuyTeam | None:
        stmt = select(self.model).where(self.model.share_code == code)
        if lock:
            stmt = stmt.with_for_update().execution_options(populate_existing=True)
        return (await db.execute(stmt)).scalar_one_or_none()

    async def members(self, db: AsyncSession, team_id: int) -> list[PayGroupBuyMember]:
        stmt = select(PayGroupBuyMember).where(PayGroupBuyMember.team_id == team_id).order_by(PayGroupBuyMember.id)
        return list((await db.scalars(stmt)).all())

    async def paid_members(self, db: AsyncSession, team_ids: list[int]) -> list[PayGroupBuyMember]:
        """多个团的已付款成员，用于展示头像与人数。"""
        if not team_ids:
            return []
        stmt = (
            select(PayGroupBuyMember)
            .where(PayGroupBuyMember.team_id.in_(team_ids), PayGroupBuyMember.status == 'paid')
            .order_by(PayGroupBuyMember.paid_at, PayGroupBuyMember.id)
        )
        return list((await db.scalars(stmt)).all())

    async def open_teams(self, db: AsyncSession, *, now: datetime, limit: int) -> list[PayGroupBuyTeam]:
        """可参与的进行中团：已开团、未满、没有待付款占位，且活动在售。"""
        paid_count = (
            select(func.count())
            .select_from(PayGroupBuyMember)
            .where(PayGroupBuyMember.team_id == self.model.id, PayGroupBuyMember.status == 'paid')
            .scalar_subquery()
        )
        pending_count = (
            select(func.count())
            .select_from(PayGroupBuyMember)
            .where(
                PayGroupBuyMember.team_id == self.model.id,
                PayGroupBuyMember.status == 'reserved',
                PayGroupBuyMember.reserved_until > now,
            )
            .scalar_subquery()
        )
        stmt = (
            select(self.model)
            .join(PayGroupBuyActivity, PayGroupBuyActivity.id == self.model.activity_id)
            .where(
                self.model.status == 'forming',
                self.model.deadline.is_not(None),
                self.model.deadline > now,
                paid_count < self.model.people,
                pending_count == 0,
                PayGroupBuyActivity.status == 'active',
                PayGroupBuyActivity.starts_at <= now,
                PayGroupBuyActivity.ends_at > now,
            )
            .order_by(self.model.deadline, self.model.id)
            .limit(limit)
        )
        return list((await db.scalars(stmt)).all())

    async def avatars(self, db: AsyncSession, user_ids: list[int]) -> dict[int, str]:
        """账号头像映射，只取已配置头像的账号。"""
        if not user_ids:
            return {}
        stmt = select(User.id, User.avatar).where(User.id.in_(user_ids))
        rows = (await db.execute(stmt)).all()
        return {user_id: avatar for user_id, avatar in rows if avatar}

    async def enqueue(
        self,
        db: AsyncSession,
        *,
        key: str,
        kind: str,
        team_id: int,
        order_id: int,
        payload: dict[str, Any] | None = None,
    ) -> None:
        # 与业务事实同一事务提交；不能用提交前发送 Celery 消息代替任务表。
        await db.execute(
            insert(PayGroupBuyTask)
            .values(
                created_time=timezone.now(),
                updated_time=timezone.now(),
                key=key,
                kind=kind,
                team_id=team_id,
                order_id=order_id,
                payload=payload or {},
                status='pending',
                attempts=0,
                available_at=timezone.now(),
            )
            .on_conflict_do_nothing(index_elements=['key'])
        )

    async def claim(self, db: AsyncSession) -> PayGroupBuyTask | None:
        now = timezone.now()
        stmt = (
            select(PayGroupBuyTask)
            .where(
                or_(
                    (PayGroupBuyTask.status == 'pending') & (PayGroupBuyTask.available_at <= now),
                    (PayGroupBuyTask.status == 'running') & (PayGroupBuyTask.lease_until <= now),
                )
            )
            .order_by(PayGroupBuyTask.id)
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        task = (await db.scalars(stmt)).first()
        if task:
            task.status = 'running'
            task.attempts += 1
            task.lease_until = now + timedelta(minutes=5)
            await db.flush()
        return task


group_buy_dao = CRUDGroupBuy(PayGroupBuyTeam)
