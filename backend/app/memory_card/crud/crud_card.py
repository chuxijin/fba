#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.memory_card.model.card import (
    MemoryCard,
    MemoryCardDeck,
    MemoryCardGroup,
    MemoryCardReviewLog,
    MemoryCardRevision,
    MemoryCardSubscription,
    MemoryCardUserState,
)


class CRUDMemoryCardGroup(CRUDPlus[MemoryCardGroup]):
    """记忆卡分组数据库操作类"""

    async def get_by_id(self, db: AsyncSession, pk: int) -> MemoryCardGroup | None:
        stmt = select(self.model).where(self.model.id == pk, self.model.deleted == 0)
        return (await db.execute(stmt)).scalars().first()

    async def list_by_deck(self, db: AsyncSession, deck_id: int) -> list[MemoryCardGroup]:
        stmt = (
            select(MemoryCardGroup)
            .where(MemoryCardGroup.deck_id == deck_id, MemoryCardGroup.deleted == 0)
            .order_by(MemoryCardGroup.parent_id.asc(), MemoryCardGroup.sort_order.asc(), MemoryCardGroup.id.asc())
        )
        return list((await db.execute(stmt)).scalars().all())

    async def list_subtree_ids(self, db: AsyncSession, group_id: int) -> list[int]:
        """递归获取分组及其全部后代分组 ID。"""
        all_groups = await self.list_all_groups(db)
        result: list[int] = []
        stack = [group_id]
        while stack:
            current = stack.pop()
            result.append(current)
            stack.extend(
                group.id
                for group in all_groups
                if group.parent_id == current and group.deleted == 0
            )
        return result

    async def list_all_groups(self, db: AsyncSession) -> list[MemoryCardGroup]:
        stmt = select(MemoryCardGroup).where(MemoryCardGroup.deleted == 0)
        return list((await db.execute(stmt)).scalars().all())

    async def count_cards_by_groups(self, db: AsyncSession, group_ids: Sequence[int]) -> dict[int, int]:
        if not group_ids:
            return {}
        stmt = (
            select(MemoryCard.group_id, func.count())
            .where(MemoryCard.group_id.in_(group_ids), MemoryCard.deleted == 0)
            .group_by(MemoryCard.group_id)
        )
        result = await db.execute(stmt)
        return {int(group_id): int(count) for group_id, count in result.all()}

    async def clear_cards_of_groups(self, db: AsyncSession, group_ids: Sequence[int]) -> None:
        """把指定分组下的卡片移回卡组根目录。"""
        if not group_ids:
            return
        stmt = (
            MemoryCard.__table__.update()
            .where(MemoryCard.group_id.in_(group_ids), MemoryCard.deleted == 0)
            .values(group_id=None)
        )
        await db.execute(stmt)


class CRUDMemoryCardDeck(CRUDPlus[MemoryCardDeck]):
    """记忆卡组数据库操作类"""

    async def get_by_code(self, db: AsyncSession, code: str) -> MemoryCardDeck | None:
        return await self.select_model_by_column(db, code=code)

    async def get_by_id(self, db: AsyncSession, pk: int) -> MemoryCardDeck | None:
        stmt = select(self.model).where(self.model.id == pk, self.model.deleted == 0)
        return (await db.execute(stmt)).scalars().first()

    async def get_card_count(self, db: AsyncSession, deck_id: int) -> int:
        stmt = select(func.count()).where(MemoryCard.deck_id == deck_id, MemoryCard.deleted == 0)
        return int(await db.scalar(stmt) or 0)

    def get_list_select(
        self,
        *,
        scope: str | None = None,
        status: str | None = None,
        owner_id: int | None = None,
        category_id: int | None = None,
        keyword: str | None = None,
    ) -> Select:
        stmt = select(MemoryCardDeck).where(MemoryCardDeck.deleted == 0)
        if scope is not None:
            stmt = stmt.where(MemoryCardDeck.scope == scope)
        if status is not None:
            stmt = stmt.where(MemoryCardDeck.status == status)
        if owner_id is not None:
            stmt = stmt.where(MemoryCardDeck.owner_id == owner_id)
        if category_id is not None:
            stmt = stmt.where(MemoryCardDeck.category_id == category_id)
        if keyword:
            like = f'%{keyword}%'
            stmt = stmt.where(MemoryCardDeck.name.like(like) | MemoryCardDeck.code.like(like))
        return stmt.order_by(MemoryCardDeck.sort_order.asc(), MemoryCardDeck.id.desc())

    async def get_subscribed_deck_ids(self, db: AsyncSession, user_id: int) -> set[int]:
        stmt = select(MemoryCardSubscription.deck_id).where(
            MemoryCardSubscription.user_id == user_id,
            MemoryCardSubscription.status == 'active',
            MemoryCardSubscription.deleted == 0,
        )
        result = await db.execute(stmt)
        return set(result.scalars().all())

    async def list_accessible_deck_ids(
        self,
        db: AsyncSession,
        user_id: int,
        category_id: int | None = None,
    ) -> list[int]:
        """当前用户可学习的卡组：已订阅的公共卡组 + 自己的私人卡组（可按领域分类过滤）"""
        subscribed = await self.get_subscribed_deck_ids(db, user_id)
        stmt = select(MemoryCardDeck.id).where(
            MemoryCardDeck.deleted == 0,
            MemoryCardDeck.status == 'active',
            MemoryCardDeck.scope == 'system',
            MemoryCardDeck.id.in_(subscribed),
        )
        if category_id is not None:
            stmt = stmt.where(MemoryCardDeck.category_id == category_id)
        system_ids = set((await db.execute(stmt)).scalars().all())
        stmt2 = select(MemoryCardDeck.id).where(
            MemoryCardDeck.deleted == 0,
            MemoryCardDeck.status == 'active',
            MemoryCardDeck.scope == 'personal',
            MemoryCardDeck.owner_id == user_id,
        )
        if category_id is not None:
            stmt2 = stmt2.where(MemoryCardDeck.category_id == category_id)
        personal_ids = set((await db.execute(stmt2)).scalars().all())
        return sorted(system_ids | personal_ids)


class CRUDMemoryCard(CRUDPlus[MemoryCard]):
    """记忆卡数据库操作类"""

    async def get_by_code(self, db: AsyncSession, code: str) -> MemoryCard | None:
        return await self.select_model_by_column(db, code=code)

    async def get_by_id(self, db: AsyncSession, pk: int) -> MemoryCard | None:
        stmt = select(self.model).where(self.model.id == pk, self.model.deleted == 0)
        return (await db.execute(stmt)).scalars().first()

    async def list_by_deck(self, db: AsyncSession, deck_id: int) -> list[MemoryCard]:
        stmt = select(MemoryCard).where(MemoryCard.deck_id == deck_id, MemoryCard.deleted == 0)
        return list((await db.execute(stmt)).scalars().all())

    async def list_active_cards_by_decks(self, db: AsyncSession, deck_ids: Sequence[int]) -> list[MemoryCard]:
        if not deck_ids:
            return []
        stmt = select(MemoryCard).where(
            MemoryCard.deck_id.in_(deck_ids),
            MemoryCard.status == 'active',
            MemoryCard.deleted == 0,
        )
        return list((await db.execute(stmt)).scalars().all())

    def get_list_select(
        self,
        *,
        deck_id: int | None = None,
        group_id: int | None = None,
        status: str | None = None,
        keyword: str | None = None,
    ) -> Select:
        stmt = select(MemoryCard).where(MemoryCard.deleted == 0)
        if deck_id is not None:
            stmt = stmt.where(MemoryCard.deck_id == deck_id)
        if group_id is not None:
            stmt = stmt.where(MemoryCard.group_id == group_id)
        if status is not None:
            stmt = stmt.where(MemoryCard.status == status)
        if keyword:
            like = f'%{keyword}%'
            stmt = stmt.where(MemoryCard.title.like(like) | MemoryCard.code.like(like))
        return stmt.order_by(
            MemoryCard.deck_id.asc(),
            MemoryCard.group_id.asc(),
            MemoryCard.sort_order.asc(),
            MemoryCard.id.desc(),
        )


class CRUDMemoryCardRevision(CRUDPlus[MemoryCardRevision]):
    """记忆卡版本数据库操作类"""

    async def get_next_revision_no(self, db: AsyncSession, card_id: int) -> int:
        result = await db.execute(
            select(func.coalesce(func.max(MemoryCardRevision.revision_no), 0)).where(
                MemoryCardRevision.card_id == card_id,
                MemoryCardRevision.deleted == 0,
            )
        )
        return int(result.scalar() or 0) + 1

    async def get_current(self, db: AsyncSession, card_id: int) -> MemoryCardRevision | None:
        stmt = (
            select(MemoryCardRevision)
            .where(
                MemoryCardRevision.card_id == card_id,
                MemoryCardRevision.status == 'published',
                MemoryCardRevision.deleted == 0,
            )
            .order_by(MemoryCardRevision.revision_no.desc())
            .limit(1)
        )
        return (await db.execute(stmt)).scalars().first()

    async def get_by_id(self, db: AsyncSession, pk: int) -> MemoryCardRevision | None:
        stmt = select(self.model).where(self.model.id == pk, self.model.deleted == 0)
        return (await db.execute(stmt)).scalars().first()

    async def get_revision_no_map(self, db: AsyncSession, card_ids: Sequence[int]) -> dict[int, int]:
        """批量获取卡片当前发布版本号。"""
        if not card_ids:
            return {}
        stmt = (
            select(MemoryCardRevision.card_id, func.max(MemoryCardRevision.revision_no))
            .where(
                MemoryCardRevision.card_id.in_(card_ids),
                MemoryCardRevision.status == 'published',
                MemoryCardRevision.deleted == 0,
            )
            .group_by(MemoryCardRevision.card_id)
        )
        result = await db.execute(stmt)
        return {int(card_id): int(revision_no) for card_id, revision_no in result.all()}


class CRUDMemoryCardSubscription(CRUDPlus[MemoryCardSubscription]):
    """用户卡组订阅数据库操作类"""

    async def get_by_user_and_deck(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        deck_id: int,
        for_update: bool = False,
    ) -> MemoryCardSubscription | None:
        stmt = select(MemoryCardSubscription).where(
            MemoryCardSubscription.user_id == user_id,
            MemoryCardSubscription.deck_id == deck_id,
            MemoryCardSubscription.deleted == 0,
        )
        if for_update:
            stmt = stmt.with_for_update()
        return (await db.execute(stmt)).scalars().first()


class CRUDMemoryCardUserState(CRUDPlus[MemoryCardUserState]):
    """用户卡片记忆状态数据库操作类"""

    async def get_by_user_and_card(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        card_id: int,
        for_update: bool = False,
    ) -> MemoryCardUserState | None:
        stmt = select(MemoryCardUserState).where(
            MemoryCardUserState.user_id == user_id,
            MemoryCardUserState.card_id == card_id,
            MemoryCardUserState.deleted == 0,
        )
        if for_update:
            stmt = stmt.with_for_update()
        return (await db.execute(stmt)).scalars().first()

    async def get_due_cards(
        self,
        db: AsyncSession,
        user_id: int,
        now: datetime,
        limit: int,
        category_id: int | None = None,
    ) -> list[MemoryCardUserState]:
        stmt = (
            select(MemoryCardUserState)
            .where(
                MemoryCardUserState.user_id == user_id,
                MemoryCardUserState.status == 'active',
                MemoryCardUserState.due <= now,
            )
            .order_by(MemoryCardUserState.due.asc())
            .limit(limit)
        )
        if category_id is not None:
            stmt = stmt.join(MemoryCard, MemoryCard.id == MemoryCardUserState.card_id).join(
                MemoryCardDeck,
                MemoryCardDeck.id == MemoryCard.deck_id,
            ).where(MemoryCardDeck.category_id == category_id)
        return list((await db.execute(stmt)).scalars().all())

    async def get_due_count(
        self,
        db: AsyncSession,
        user_id: int,
        now: datetime,
        category_id: int | None = None,
    ) -> int:
        stmt = select(func.count()).where(
            MemoryCardUserState.user_id == user_id,
            MemoryCardUserState.status == 'active',
            MemoryCardUserState.due <= now,
        )
        if category_id is not None:
            stmt = stmt.select_from(MemoryCardUserState).join(
                MemoryCard, MemoryCard.id == MemoryCardUserState.card_id
            ).join(
                MemoryCardDeck,
                MemoryCardDeck.id == MemoryCard.deck_id,
            ).where(MemoryCardDeck.category_id == category_id)
        return int(await db.scalar(stmt) or 0)

    async def get_learned_card_ids(self, db: AsyncSession, user_id: int) -> set[int]:
        stmt = select(MemoryCardUserState.card_id).where(MemoryCardUserState.user_id == user_id)
        result = await db.execute(stmt)
        return set(result.scalars().all())

    async def count_created_since(self, db: AsyncSession, user_id: int, since: datetime) -> int:
        stmt = select(func.count()).where(
            MemoryCardUserState.user_id == user_id,
            MemoryCardUserState.created_time >= since,
        )
        return int(await db.scalar(stmt) or 0)

    async def count_reviewed_since(self, db: AsyncSession, user_id: int, since: datetime) -> int:
        stmt = select(func.count()).where(
            MemoryCardUserState.user_id == user_id,
            MemoryCardUserState.last_review >= since,
        )
        return int(await db.scalar(stmt) or 0)

    async def count_by_state(self, db: AsyncSession, user_id: int) -> dict[int, int]:
        stmt = (
            select(MemoryCardUserState.state, func.count())
            .where(MemoryCardUserState.user_id == user_id)
            .group_by(MemoryCardUserState.state)
        )
        result = await db.execute(stmt)
        return {int(row[0]): int(row[1]) for row in result.all()}

    async def get_due_forecast(
        self,
        db: AsyncSession,
        user_id: int,
        start: datetime,
        end: datetime,
        category_id: int | None = None,
    ) -> list[tuple[datetime, int]]:
        """按天聚合到期卡数（仅取最早一天）"""
        stmt = (
            select(MemoryCardUserState.due, func.count())
            .where(
                MemoryCardUserState.user_id == user_id,
                MemoryCardUserState.status == 'active',
                MemoryCardUserState.due >= start,
                MemoryCardUserState.due < end,
            )
            .group_by(MemoryCardUserState.due)
        )
        if category_id is not None:
            stmt = stmt.select_from(MemoryCardUserState).join(
                MemoryCard, MemoryCard.id == MemoryCardUserState.card_id
            ).join(
                MemoryCardDeck,
                MemoryCardDeck.id == MemoryCard.deck_id,
            ).where(MemoryCardDeck.category_id == category_id)
        result = await db.execute(stmt)
        return [(row[0], int(row[1])) for row in result.all()]

    async def list_reviewed_today(self, db: AsyncSession, user_id: int, since: datetime) -> set[int]:
        stmt = select(MemoryCardUserState.card_id).where(
            MemoryCardUserState.user_id == user_id,
            MemoryCardUserState.last_review >= since,
        )
        result = await db.execute(stmt)
        return set(result.scalars().all())


class CRUDMemoryCardReviewLog(CRUDPlus[MemoryCardReviewLog]):
    """记忆卡复习日志数据库操作类"""

    async def get_by_idempotency(
        self,
        db: AsyncSession,
        user_id: int,
        idempotency_key: str,
    ) -> MemoryCardReviewLog | None:
        return await self.select_model_by_column(db, user_id=user_id, idempotency_key=idempotency_key)

    async def count_reviewed_since(self, db: AsyncSession, user_id: int, since: datetime) -> int:
        stmt = select(func.count()).where(
            MemoryCardReviewLog.user_id == user_id,
            MemoryCardReviewLog.reviewed_at >= since,
        )
        return int(await db.scalar(stmt) or 0)

    def get_list_select(
        self,
        *,
        user_id: int | None = None,
        card_id: int | None = None,
        rating: int | None = None,
    ) -> Select:
        stmt = select(MemoryCardReviewLog).where(MemoryCardReviewLog.deleted == 0)
        if user_id is not None:
            stmt = stmt.where(MemoryCardReviewLog.user_id == user_id)
        if card_id is not None:
            stmt = stmt.where(MemoryCardReviewLog.card_id == card_id)
        if rating is not None:
            stmt = stmt.where(MemoryCardReviewLog.rating == rating)
        return stmt.order_by(MemoryCardReviewLog.reviewed_at.desc(), MemoryCardReviewLog.id.desc())


memory_card_deck_dao: CRUDMemoryCardDeck = CRUDMemoryCardDeck(MemoryCardDeck)
memory_card_group_dao: CRUDMemoryCardGroup = CRUDMemoryCardGroup(MemoryCardGroup)
memory_card_dao: CRUDMemoryCard = CRUDMemoryCard(MemoryCard)
memory_card_revision_dao: CRUDMemoryCardRevision = CRUDMemoryCardRevision(MemoryCardRevision)
memory_card_subscription_dao: CRUDMemoryCardSubscription = CRUDMemoryCardSubscription(MemoryCardSubscription)
memory_card_user_state_dao: CRUDMemoryCardUserState = CRUDMemoryCardUserState(MemoryCardUserState)
memory_card_review_log_dao: CRUDMemoryCardReviewLog = CRUDMemoryCardReviewLog(MemoryCardReviewLog)
