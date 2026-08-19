#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.memory_card.crud.crud_card import (
    memory_card_dao,
    memory_card_deck_dao,
    memory_card_group_dao,
    memory_card_review_log_dao,
    memory_card_revision_dao,
    memory_card_subscription_dao,
    memory_card_user_state_dao,
)
from backend.app.memory_card.enums import MemoryDeckScope, MemorySubscriptionStatus
from backend.app.memory_card.model.card import (
    MemoryCard,
    MemoryCardDeck,
    MemoryCardGroup,
    MemoryCardReviewLog,
    MemoryCardRevision,
    MemoryCardSubscription,
    MemoryCardUserState,
)
from backend.app.memory_card.schema.card import (
    CreateCardParam,
    CreateDeckParam,
    CreateGroupParam,
    GetCardDetail,
    GetDeckDetail,
    GetGroupDetail,
    GetReviewLogItem,
    MemoryContentParam,
    UpdateGroupParam,
)
from backend.app.memory_card.schema.study import (
    CheckBlankResult,
    CheckMemoryCardParam,
    CheckMemoryCardResult,
    GetMemoryCurve,
    GetMemoryDeckItem,
    GetMemoryForecast,
    GetMemoryOverview,
    GetStudyQueue,
    GetStudyQueueItem,
    StudyContent,
    SubmitMemoryReviewParam,
    SubmitMemoryReviewResult,
)
from backend.app.memory_card.service.card_service import CardService
from backend.app.memory_card.service.grading_service import (
    build_study_content,
    derive_available_modes,
    extract_points,
    grade_answer,
    recommend_rating,
    render_material,
)
from backend.app.sensitive_word.service.sensitive_word_service import HitInfo, sensitive_word_service
from backend.common.exception import errors
from backend.common.fsrs import ReviewForecast, fsrs_engine
from backend.common.pagination import paging_data
from backend.utils.timezone import timezone

DEFAULT_DAILY_NEW_LIMIT = 20
DEFAULT_DAILY_REVIEW_LIMIT = 200


class StudyService:
    """记忆卡学习服务类"""

    # ============ 卡组订阅与个人卡组 ============

    @staticmethod
    async def list_decks(*, db: AsyncSession, user_id: int, category_id: int | None = None) -> list[GetMemoryDeckItem]:
        """获取用户可学习与可订阅的卡组列表（可按领域分类过滤）。"""
        subscribed = await memory_card_deck_dao.get_subscribed_deck_ids(db, user_id)
        stmt = select(MemoryCardDeck).where(
            MemoryCardDeck.deleted == 0,
            MemoryCardDeck.status == 'active',
            (
                (MemoryCardDeck.scope == MemoryDeckScope.system.value)
                | (
                    (MemoryCardDeck.scope == MemoryDeckScope.personal.value)
                    & (MemoryCardDeck.owner_id == user_id)
                )
            ),
        )
        if category_id is not None:
            stmt = stmt.where(MemoryCardDeck.category_id == category_id)
        decks = list((await db.execute(stmt)).scalars().all())
        items: list[GetMemoryDeckItem] = []
        for deck in decks:
            card_count = await memory_card_deck_dao.get_card_count(db, deck.id)
            items.append(
                GetMemoryDeckItem(
                    id=deck.id,
                    name=deck.name,
                    description=deck.description,
                    scope=deck.scope,
                    status=deck.status,
                    card_count=card_count,
                    subscribed=deck.id in subscribed,
                    daily_new_limit=deck.daily_new_limit,
                    daily_review_limit=deck.daily_review_limit,
                )
            )
        return items

    @staticmethod
    async def subscribe_deck(*, db: AsyncSession, user_id: int, deck_id: int) -> None:
        """订阅公共卡组。"""
        deck = await memory_card_deck_dao.get_by_id(db, deck_id)
        if deck is None or deck.deleted != 0:
            raise errors.NotFoundError(msg='卡组不存在')
        if deck.scope != MemoryDeckScope.system.value:
            raise errors.RequestError(msg='只能订阅公共卡组')
        if deck.status != 'active':
            raise errors.RequestError(msg='卡组未上架，无法订阅')
        subscription = await memory_card_subscription_dao.get_by_user_and_deck(
            db,
            user_id=user_id,
            deck_id=deck_id,
            for_update=True,
        )
        if subscription is None:
            subscription = MemoryCardSubscription(
                user_id=user_id,
                deck_id=deck_id,
                status=MemorySubscriptionStatus.active.value,
            )
            db.add(subscription)
        else:
            subscription.status = MemorySubscriptionStatus.active.value
        await db.flush()

    @staticmethod
    async def unsubscribe_deck(*, db: AsyncSession, user_id: int, deck_id: int) -> None:
        """取消订阅公共卡组。"""
        subscription = await memory_card_subscription_dao.get_by_user_and_deck(
            db,
            user_id=user_id,
            deck_id=deck_id,
            for_update=True,
        )
        if subscription is None:
            return
        subscription.status = MemorySubscriptionStatus.paused.value
        await db.flush()

    @staticmethod
    async def create_personal_deck(*, db: AsyncSession, user_id: int, obj: CreateDeckParam) -> GetDeckDetail:
        """用户创建私人卡组（自动脱敏并记录命中日志）。"""
        name_result = await sensitive_word_service.sanitize(db, obj.name)
        desc_result = await sensitive_word_service.sanitize(db, obj.description or '')
        hits = [*name_result.hits, *desc_result.hits]
        sanitized = CreateDeckParam(
            name=name_result.clean_text,
            code=obj.code,
            description=desc_result.clean_text or None,
            category_id=obj.category_id,
            scope=obj.scope,
            status=obj.status,
            daily_new_limit=obj.daily_new_limit,
            daily_review_limit=obj.daily_review_limit,
            sort_order=obj.sort_order,
            settings=obj.settings,
        )
        deck = await CardService.create_deck(db=db, user_id=user_id, obj=sanitized, scope='personal')
        if hits:
            await sensitive_word_service.log_hits(
                db=db,
                user_id=user_id,
                hits=hits,
                target_type='memory_deck',
                target_id=deck.id,
                snippet=sanitized.name[:120],
            )
        return deck

    @staticmethod
    async def create_personal_card(*, db: AsyncSession, user_id: int, obj: CreateCardParam) -> GetCardDetail:
        """用户创建私人卡组下的卡片（自动脱敏并记录命中日志）。"""
        deck = await memory_card_deck_dao.get_by_id(db, obj.deck_id)
        if deck is None:
            raise errors.NotFoundError(msg='卡组不存在')
        if deck.scope != MemoryDeckScope.personal.value or deck.owner_id != user_id:
            raise errors.ForbiddenError(msg='无权在该卡组下创建卡片')
        sanitized, hits = await StudyService._sanitize_card_param(db=db, obj=obj)
        detail = await CardService.create_card(db=db, user_id=user_id, obj=sanitized)
        if hits:
            await sensitive_word_service.log_hits(
                db=db,
                user_id=user_id,
                hits=hits,
                target_type='memory_card',
                target_id=detail.id,
                snippet=sanitized.title[:120],
            )
        return detail

    # ============ 私人分组管理 ============

    @staticmethod
    async def _sanitize_card_param(
        *,
        db: AsyncSession,
        obj: CreateCardParam,
    ) -> tuple[CreateCardParam, list[HitInfo]]:
        """对卡片标题与内容做敏感词脱敏，返回新参数与命中明细。"""
        title_result = await sensitive_word_service.sanitize(db, obj.title)
        content, content_hits = await sensitive_word_service.sanitize_collect(db, obj.content.model_dump())
        hits = [*title_result.hits, *content_hits]
        param = CreateCardParam(
            deck_id=obj.deck_id,
            group_id=obj.group_id,
            code=obj.code,
            title=title_result.clean_text,
            card_type=obj.card_type,
            response_mode=obj.response_mode,
            status=obj.status,
            sort_order=obj.sort_order,
            content=MemoryContentParam(**content),
        )
        return param, hits

    @staticmethod
    async def _load_owned_personal_deck(*, db: AsyncSession, user_id: int, deck_id: int) -> MemoryCardDeck:
        deck = await memory_card_deck_dao.get_by_id(db, deck_id)
        if deck is None:
            raise errors.NotFoundError(msg='卡组不存在')
        if deck.scope != MemoryDeckScope.personal.value or deck.owner_id != user_id:
            raise errors.ForbiddenError(msg='无权操作该卡组')
        return deck

    @staticmethod
    async def _load_owned_personal_group(*, db: AsyncSession, user_id: int, group_id: int) -> MemoryCardGroup:
        group = await memory_card_group_dao.get_by_id(db, group_id)
        if group is None:
            raise errors.NotFoundError(msg='分组不存在')
        await StudyService._load_owned_personal_deck(db=db, user_id=user_id, deck_id=group.deck_id)
        return group

    @staticmethod
    async def get_personal_group_tree(*, db: AsyncSession, user_id: int, deck_id: int) -> list[GetGroupDetail]:
        """获取用户私人卡组的分组树。"""
        await StudyService._load_owned_personal_deck(db=db, user_id=user_id, deck_id=deck_id)
        return await CardService.get_group_tree(db=db, deck_id=deck_id)

    @staticmethod
    async def _load_accessible_deck(*, db: AsyncSession, user_id: int, deck_id: int) -> MemoryCardDeck:
        """校验卡组可访问（已订阅公共卡组或自己的私人卡组），返回卡组。"""
        deck = await memory_card_deck_dao.get_by_id(db, deck_id)
        if deck is None:
            raise errors.NotFoundError(msg='卡组不存在')
        accessible = await StudyService._accessible_deck_ids(db=db, user_id=user_id)
        if deck.id not in accessible:
            raise errors.ForbiddenError(msg='无权学习该卡组')
        return deck

    @staticmethod
    async def get_deck_group_tree(*, db: AsyncSession, user_id: int, deck_id: int) -> list[GetGroupDetail]:
        """获取可访问卡组的分组树（公共或私人）。"""
        await StudyService._load_accessible_deck(db=db, user_id=user_id, deck_id=deck_id)
        return await CardService.get_group_tree(db=db, deck_id=deck_id)

    @staticmethod
    async def create_personal_group(
        *,
        db: AsyncSession,
        user_id: int,
        deck_id: int,
        obj: CreateGroupParam,
    ) -> GetGroupDetail:
        """在用户私人卡组下创建分组（自动脱敏并记录命中日志）。"""
        await StudyService._load_owned_personal_deck(db=db, user_id=user_id, deck_id=deck_id)
        name_result = await sensitive_word_service.sanitize(db, obj.name)
        param = CreateGroupParam(
            deck_id=deck_id,
            parent_id=obj.parent_id,
            name=name_result.clean_text,
            sort_order=obj.sort_order,
            status=obj.status,
        )
        group = await CardService.create_group(db=db, user_id=user_id, obj=param)
        if name_result.hits:
            await sensitive_word_service.log_hits(
                db=db,
                user_id=user_id,
                hits=name_result.hits,
                target_type='memory_group',
                target_id=group.id,
                snippet=name_result.clean_text[:120],
            )
        return group

    @staticmethod
    async def update_personal_group(
        *,
        db: AsyncSession,
        user_id: int,
        group_id: int,
        obj: UpdateGroupParam,
    ) -> int:
        """更新用户私人分组。"""
        await StudyService._load_owned_personal_group(db=db, user_id=user_id, group_id=group_id)
        return await CardService.update_group(db=db, pk=group_id, obj=obj)

    @staticmethod
    async def delete_personal_group(*, db: AsyncSession, user_id: int, group_id: int) -> int:
        """删除用户私人分组及其子分组。"""
        await StudyService._load_owned_personal_group(db=db, user_id=user_id, group_id=group_id)
        return await CardService.delete_group(db=db, pk=group_id)

    # ============ 个人卡片 ============

    @staticmethod
    async def list_my_cards(*, db: AsyncSession, user_id: int) -> list[dict[str, Any]]:
        """获取用户私人卡组下的全部卡片。"""
        stmt = (
            select(MemoryCard, MemoryCardDeck.name)
            .join(MemoryCardDeck, MemoryCardDeck.id == MemoryCard.deck_id)
            .where(
                MemoryCardDeck.scope == MemoryDeckScope.personal.value,
                MemoryCardDeck.owner_id == user_id,
                MemoryCard.deleted == 0,
            )
            .order_by(
                MemoryCard.deck_id.asc(),
                MemoryCard.group_id.asc(),
                MemoryCard.sort_order.asc(),
                MemoryCard.id.desc(),
            )
        )
        rows = (await db.execute(stmt)).all()
        group_ids = {card.group_id for card, _ in rows if card.group_id is not None}
        group_names: dict[int, str] = {}
        if group_ids:
            group_rows = (
                await db.execute(
                    select(MemoryCardGroup.id, MemoryCardGroup.name).where(MemoryCardGroup.id.in_(group_ids))
                )
            ).all()
            group_names = {int(row[0]): row[1] for row in group_rows}
        result: list[dict[str, Any]] = []
        for card, deck_name in rows:
            revision_no = None
            if card.current_revision_id is not None:
                revision = await memory_card_revision_dao.get_by_id(db, card.current_revision_id)
                revision_no = revision.revision_no if revision is not None else None
            result.append(
                {
                    'id': card.id,
                    'deck_id': card.deck_id,
                    'deck_name': deck_name,
                    'group_id': card.group_id,
                    'group_name': group_names.get(card.group_id) if card.group_id is not None else None,
                    'code': card.code,
                    'title': card.title,
                    'card_type': card.card_type,
                    'response_mode': card.response_mode,
                    'status': card.status,
                    'revision_no': revision_no,
                    'created_time': card.created_time,
                }
            )
        return result

    @staticmethod
    async def _load_owned_personal_card(*, db: AsyncSession, user_id: int, card_id: int) -> MemoryCard:
        """加载用户自己的私人卡片。"""
        card = await memory_card_dao.get_by_id(db, card_id)
        if card is None:
            raise errors.NotFoundError(msg='卡片不存在')
        deck = await memory_card_deck_dao.get_by_id(db, card.deck_id)
        if deck is None:
            raise errors.NotFoundError(msg='卡组不存在')
        if deck.scope != MemoryDeckScope.personal.value or deck.owner_id != user_id:
            raise errors.ForbiddenError(msg='无权操作该卡片')
        return card

    @staticmethod
    async def load_card_detail(*, db: AsyncSession, user_id: int, card_id: int) -> GetCardDetail:
        """获取用户自己的私人卡片详情（含内容）。"""
        await StudyService._load_owned_personal_card(db=db, user_id=user_id, card_id=card_id)
        return await CardService.get_card_detail(db=db, pk=card_id)

    @staticmethod
    async def update_personal_card(
        *,
        db: AsyncSession,
        user_id: int,
        card_id: int,
        obj: CreateCardParam,
    ) -> GetCardDetail:
        """更新用户自己的私人卡片，内容变化发布新版本（自动脱敏并记录命中日志）。"""
        await StudyService._load_owned_personal_card(db=db, user_id=user_id, card_id=card_id)
        from backend.app.memory_card.schema.card import UpdateCardParam

        sanitized, hits = await StudyService._sanitize_card_param(db=db, obj=obj)
        update_obj = UpdateCardParam(
            title=sanitized.title,
            group_id=sanitized.group_id,
            card_type=sanitized.card_type,
            response_mode=sanitized.response_mode,
            status=sanitized.status,
            sort_order=sanitized.sort_order,
            content=sanitized.content,
        )
        await CardService.update_card(db=db, pk=card_id, obj=update_obj, user_id=user_id)
        if hits:
            await sensitive_word_service.log_hits(
                db=db,
                user_id=user_id,
                hits=hits,
                target_type='memory_card',
                target_id=card_id,
                snippet=sanitized.title[:120],
            )
        return await CardService.get_card_detail(db=db, pk=card_id)

    @staticmethod
    async def delete_personal_card(*, db: AsyncSession, user_id: int, card_id: int) -> None:
        """删除用户自己的私人卡片。"""
        await StudyService._load_owned_personal_card(db=db, user_id=user_id, card_id=card_id)
        await CardService.delete_card(db=db, pk=card_id)

    # ============ 学习队列 ============

    @staticmethod
    async def _accessible_deck_ids(*, db: AsyncSession, user_id: int, category_id: int | None = None) -> set[int]:
        ids = await memory_card_deck_dao.list_accessible_deck_ids(db, user_id, category_id)
        return set(ids)

    @staticmethod
    async def _load_accessible_card(*, db: AsyncSession, user_id: int, card_id: int) -> MemoryCard:
        card = await memory_card_dao.get_by_id(db, card_id)
        if card is None:
            raise errors.NotFoundError(msg='卡片不存在')
        accessible = await StudyService._accessible_deck_ids(db=db, user_id=user_id)
        if card.deck_id not in accessible:
            raise errors.ForbiddenError(msg='无权学习该卡片')
        if card.status != 'active':
            raise errors.RequestError(msg='卡片未上架')
        return card

    @staticmethod
    async def _build_queue_item(
        *,
        db: AsyncSession,
        card: MemoryCard,
        user_state: MemoryCardUserState | None,
        is_new: bool,
    ) -> GetStudyQueueItem | None:
        revision = await memory_card_revision_dao.get_current(db, card.id)
        if revision is None:
            return None
        deck_name = None
        deck = await memory_card_deck_dao.get_by_id(db, card.deck_id)
        if deck is not None:
            deck_name = deck.name
        available_modes = derive_available_modes(revision.content)
        if not available_modes:
            return None
        default_mode = card.response_mode if card.response_mode in available_modes else available_modes[0]
        play_contents = {
            mode: StudyContent(**build_study_content(content=revision.content, mode=mode))
            for mode in available_modes
        }
        content = play_contents[default_mode]
        retrievability = fsrs_engine.retrievability(user_state) if user_state is not None else 0.0
        return GetStudyQueueItem(
            card_id=card.id,
            deck_id=card.deck_id,
            deck_name=deck_name,
            title=card.title,
            card_type=card.card_type,
            response_mode=card.response_mode,
            default_mode=default_mode,
            available_modes=available_modes,
            content=content,
            play_contents=play_contents,
            is_new=is_new,
            state=user_state.state if user_state is not None else 0,
            stability=user_state.stability if user_state is not None else None,
            difficulty=user_state.difficulty if user_state is not None else None,
            retrievability=retrievability,
            due=user_state.due if user_state is not None else None,
        )

    @staticmethod
    async def get_queue(  # noqa: C901
        *,
        db: AsyncSession,
        user_id: int,
        mode: str = 'all',
        limit: int = 50,
        category_id: int | None = None,
        deck_id: int | None = None,
        group_id: int | None = None,
    ) -> GetStudyQueue:
        """组装学习队列：到期优先，再补新卡。可按卡组/章节范围过滤。"""
        now = timezone.now()
        accessible = set(await StudyService._accessible_deck_ids(db=db, user_id=user_id, category_id=category_id))
        allowed_card_ids: set[int] | None = None

        if deck_id is not None:
            if deck_id not in accessible:
                raise errors.ForbiddenError(msg='无权学习该卡组')
            accessible = {deck_id}
            if group_id is not None:
                group = await memory_card_group_dao.get_by_id(db, group_id)
                if group is None or group.deck_id != deck_id:
                    raise errors.NotFoundError(msg='分组不存在')
                subtree = await memory_card_group_dao.list_subtree_ids(db, group_id)
                stmt = select(MemoryCard.id).where(
                    MemoryCard.deck_id == deck_id,
                    MemoryCard.group_id.in_(subtree),
                    MemoryCard.status == 'active',
                    MemoryCard.deleted == 0,
                )
                allowed_card_ids = set((await db.execute(stmt)).scalars().all())
            else:
                stmt = select(MemoryCard.id).where(
                    MemoryCard.deck_id == deck_id,
                    MemoryCard.status == 'active',
                    MemoryCard.deleted == 0,
                )
                allowed_card_ids = set((await db.execute(stmt)).scalars().all())
            if not allowed_card_ids:
                return GetStudyQueue(cards=[], due_count=0, new_count=0, total=0)

        items: list[GetStudyQueueItem] = []
        due_count = 0
        new_count = 0

        review_limit = limit if mode in ('all', 'review') else 0
        if mode in ('all', 'review'):
            due_states = await memory_card_user_state_dao.get_due_cards(
                db,
                user_id,
                now,
                review_limit or 200,
                category_id,
            )
            for state in due_states:
                if allowed_card_ids is not None and state.card_id not in allowed_card_ids:
                    continue
                card = await memory_card_dao.get_by_id(db, state.card_id)
                if card is None or card.deck_id not in accessible or card.status != 'active':
                    continue
                item = await StudyService._build_queue_item(db=db, card=card, user_state=state, is_new=False)
                if item is not None:
                    items.append(item)
                    due_count += 1
                    if len(items) >= (limit or 200):
                        break

        new_target = 0
        if mode in ('all', 'learn'):
            today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            learned_today = await memory_card_user_state_dao.count_created_since(db, user_id, today_start)
            deck_ids = sorted(accessible)
            deck_limit_total = 0
            if deck_ids:
                stmt = select(MemoryCardDeck.daily_new_limit).where(MemoryCardDeck.id.in_(deck_ids))
                deck_limit_total = sum(int(v or 0) for v in (await db.execute(stmt)).scalars().all())
            target = deck_limit_total or DEFAULT_DAILY_NEW_LIMIT
            new_target = max(0, target - learned_today)

        if new_target > 0:
            cards = await memory_card_dao.list_active_cards_by_decks(db, sorted(accessible))
            if allowed_card_ids is not None:
                cards = [c for c in cards if c.id in allowed_card_ids]
            learned_ids = await memory_card_user_state_dao.get_learned_card_ids(db, user_id)
            new_cards = [c for c in cards if c.id not in learned_ids]
            remaining = max(0, (limit or 200) - len(items))
            for card in new_cards[: min(new_target, remaining)]:
                item = await StudyService._build_queue_item(db=db, card=card, user_state=None, is_new=True)
                if item is not None:
                    items.append(item)
                    new_count += 1

        return GetStudyQueue(
            cards=items,
            due_count=due_count,
            new_count=new_count,
            total=len(items),
        )

    @staticmethod
    async def overview(*, db: AsyncSession, user_id: int, category_id: int | None = None) -> GetMemoryOverview:
        """学习概览统计。"""
        now = timezone.now()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        accessible = await StudyService._accessible_deck_ids(db=db, user_id=user_id, category_id=category_id)

        due_count = await memory_card_user_state_dao.get_due_count(db, user_id, now, category_id)
        today_new = await memory_card_user_state_dao.count_created_since(db, user_id, today_start)
        today_reviewed = await memory_card_review_log_dao.count_reviewed_since(db, user_id, today_start)
        state_counts = await memory_card_user_state_dao.count_by_state(db, user_id)
        total_learning = state_counts.get(1, 0) + state_counts.get(3, 0)
        total_reviewing = state_counts.get(2, 0)
        total_cards = sum(state_counts.values())

        deck_ids = sorted(accessible)
        deck_limit_total = 0
        if deck_ids:
            stmt = select(MemoryCardDeck.daily_new_limit).where(MemoryCardDeck.id.in_(deck_ids))
            deck_limit_total = sum(int(v or 0) for v in (await db.execute(stmt)).scalars().all())
        new_target = deck_limit_total or DEFAULT_DAILY_NEW_LIMIT
        new_available = max(0, new_target - today_new)

        forecast = await StudyService._due_forecast(db=db, user_id=user_id, days=7, now=now, category_id=category_id)
        decks = await StudyService.list_decks(db=db, user_id=user_id, category_id=category_id)

        return GetMemoryOverview(
            due_count=due_count,
            new_count=new_available,
            today_new=today_new,
            today_reviewed=today_reviewed,
            total_learning=total_learning,
            total_reviewing=total_reviewing,
            total_cards=total_cards,
            forecast=forecast,
            decks=decks,
        )

    @staticmethod
    async def _due_forecast(
        *,
        db: AsyncSession,
        user_id: int,
        days: int,
        now: datetime,
        category_id: int | None = None,
    ) -> list[dict[str, Any]]:
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=days)
        rows = await memory_card_user_state_dao.get_due_forecast(db, user_id, start, end, category_id)
        bucket: dict[str, int] = {}
        for due, count in rows:
            day = due.date().isoformat()
            bucket[day] = bucket.get(day, 0) + count
        result: list[dict[str, Any]] = []
        for d in range(days):
            day = (start + timedelta(days=d)).date().isoformat()
            result.append({'date': day, 'count': bucket.get(day, 0)})
        return result

    @staticmethod
    async def stats_forecast(
        *,
        db: AsyncSession,
        user_id: int,
        days: int = 30,
        category_id: int | None = None,
    ) -> GetMemoryForecast:
        now = timezone.now()
        return GetMemoryForecast(
            days=await StudyService._due_forecast(db=db, user_id=user_id, days=days, now=now, category_id=category_id)
        )

    # ============ 判定 ============

    @staticmethod
    async def _current_revision(*, db: AsyncSession, card: MemoryCard) -> MemoryCardRevision:
        revision = await memory_card_revision_dao.get_current(db, card.id)
        if revision is None:
            raise errors.ServerError(msg='卡片缺少已发布内容')
        return revision

    @staticmethod
    async def check(
        *,
        db: AsyncSession,
        user_id: int,
        card_id: int,
        obj: CheckMemoryCardParam,
    ) -> CheckMemoryCardResult:
        """判定作答并揭晓，不推进记忆状态。"""
        card = await StudyService._load_accessible_card(db=db, user_id=user_id, card_id=card_id)
        revision = await StudyService._current_revision(db=db, card=card)
        points = extract_points(revision.content)
        available_modes = derive_available_modes(revision.content)
        if obj.play_mode not in available_modes:
            raise errors.RequestError(msg=f'当前素材不支持学习玩法：{obj.play_mode}')

        if obj.play_mode == 'reveal' or obj.revealed:
            check_result = 'undetermined'
            blank_results: list[CheckBlankResult] = [
                CheckBlankResult(
                    blank_id=str(point.get('id') or ''),
                    user_answer=None,
                    correct=None,
                    correct_answer=point.get('correct'),
                )
                for point in points
            ]
        else:
            check_result, raw_results = grade_answer(
                mode=obj.play_mode,
                response=obj.response_data,
                points=points,
            )
            blank_results = [
                CheckBlankResult(
                    blank_id=item['blank_id'],
                    user_answer=item['user_answer'],
                    correct=item['correct'],
                    correct_answer=item['correct_answer'],
                )
                for item in raw_results
            ]

        hints: list[dict[str, Any]] = []
        for point in points:
            hint = point.get('hint')
            if hint:
                hints.append({'blank_id': point.get('id'), 'hint': hint})

        user_state = await memory_card_user_state_dao.get_by_user_and_card(db, user_id=user_id, card_id=card_id)
        forecast: dict[str, datetime | None] | None = None
        if user_state is not None:
            f = fsrs_engine.forecast(user_state)
            forecast = f.model_dump(mode='json')
        else:
            forecast = {
                'again': None,
                'hard': None,
                'good': None,
                'easy': None,
            }

        return CheckMemoryCardResult(
            card_id=card.id,
            check_result=check_result,
            blanks=blank_results,
            correct_template=render_material(revision.content),
            hints=hints,
            forecast=forecast,
            recommended_rating=recommend_rating(check_result=check_result, revealed=obj.revealed),
        )

    # ============ 评分调度 ============

    @staticmethod
    async def review(
        *,
        db: AsyncSession,
        user_id: int,
        obj: SubmitMemoryReviewParam,
    ) -> SubmitMemoryReviewResult:
        """提交评分并执行 FSRS 调度（幂等）。"""
        card = await StudyService._load_accessible_card(db=db, user_id=user_id, card_id=obj.card_id)
        revision = await StudyService._current_revision(db=db, card=card)
        now = timezone.now()

        existing = await memory_card_review_log_dao.get_by_idempotency(db, user_id, obj.idempotency_key)
        if existing is not None:
            return SubmitMemoryReviewResult(
                review_log_id=existing.id,
                card_id=existing.card_id,
                next_due=existing.next_due,
                new_state=existing.next_state,
                stability=existing.next_stability,
                difficulty=existing.next_difficulty,
            )

        user_state = await memory_card_user_state_dao.get_by_user_and_card(
            db,
            user_id=user_id,
            card_id=card.id,
            for_update=True,
        )
        prev_state = user_state.state if user_state is not None else 0
        prev_due = user_state.due if user_state is not None else None
        prev_stability = user_state.stability if user_state is not None else None
        prev_difficulty = user_state.difficulty if user_state is not None else None

        if user_state is None:
            defaults = fsrs_engine.new_card_defaults(now)
            user_state = MemoryCardUserState(
                user_id=user_id,
                card_id=card.id,
                status='active',
                state=defaults['state'],
                step=defaults['step'],
                due=defaults['due'],
                learned_revision_id=revision.id,
            )
            db.add(user_state)
            await db.flush()
        else:
            if user_state.learned_revision_id != revision.id:
                # 内容已发布新版本，重置记忆状态重新学习
                user_state.state = 0
                user_state.step = 0
                user_state.stability = None
                user_state.difficulty = None
                user_state.due = now
                user_state.last_review = None
                user_state.learned_revision_id = revision.id
            user_state.status = 'active'

        update_data, _result = fsrs_engine.schedule(user_state, obj.rating, now=now)
        prev_state = user_state.state
        prev_due = user_state.due
        prev_stability = user_state.stability
        prev_difficulty = user_state.difficulty

        user_state.state = update_data['state']
        user_state.step = update_data['step']
        user_state.stability = update_data['stability']
        user_state.difficulty = update_data['difficulty']
        user_state.due = update_data['due']
        user_state.last_review = update_data['last_review']
        user_state.learned_revision_id = revision.id
        user_state.review_count += 1
        if obj.rating == 1:
            user_state.lapse_count += 1
        user_state.last_rating = obj.rating
        await db.flush()

        log = MemoryCardReviewLog(
            user_id=user_id,
            card_id=card.id,
            revision_id=revision.id,
            idempotency_key=obj.idempotency_key,
            session_key=obj.session_key,
            rating=obj.rating,
            check_result=obj.check_result,
            response_data=obj.response_data,
            revealed=obj.revealed,
            duration_ms=obj.duration_ms,
            prev_state=prev_state,
            next_state=user_state.state,
            prev_due=prev_due,
            next_due=user_state.due,
            prev_stability=prev_stability,
            next_stability=user_state.stability,
            prev_difficulty=prev_difficulty,
            next_difficulty=user_state.difficulty,
            reviewed_at=now,
        )
        db.add(log)
        await db.flush()

        return SubmitMemoryReviewResult(
            review_log_id=log.id,
            card_id=card.id,
            next_due=user_state.due,
            new_state=user_state.state,
            stability=user_state.stability,
            difficulty=user_state.difficulty,
        )

    @staticmethod
    async def forecast(*, db: AsyncSession, user_id: int, card_id: int) -> ReviewForecast:
        """预览单卡各评分下次复习时间。"""
        await StudyService._load_accessible_card(db=db, user_id=user_id, card_id=card_id)
        user_state = await memory_card_user_state_dao.get_by_user_and_card(db, user_id=user_id, card_id=card_id)
        if user_state is None:
            raise errors.NotFoundError(msg='尚未学习该卡片')
        return fsrs_engine.forecast(user_state)

    @staticmethod
    async def curve(*, db: AsyncSession, user_id: int, card_id: int, days: int = 30) -> GetMemoryCurve:
        """单卡记忆曲线采样。"""
        card = await StudyService._load_accessible_card(db=db, user_id=user_id, card_id=card_id)
        user_state = await memory_card_user_state_dao.get_by_user_and_card(db, user_id=user_id, card_id=card_id)
        points: list[dict[str, Any]] = []
        if user_state is not None:
            points = fsrs_engine.retrievability_curve(user_state, days=days)
        return GetMemoryCurve(
            card_id=card.id,
            title=card.title,
            stability=user_state.stability if user_state is not None else None,
            difficulty=user_state.difficulty if user_state is not None else None,
            retrievability=fsrs_engine.retrievability(user_state) if user_state is not None else 0.0,
            due=user_state.due if user_state is not None else None,
            points=points,
        )

    # ============ 复习日志 ============

    @staticmethod
    def review_log_list_select(
        *,
        user_id: int | None = None,
        card_id: int | None = None,
        rating: int | None = None,
    ) -> Any:
        return memory_card_review_log_dao.get_list_select(user_id=user_id, card_id=card_id, rating=rating)

    @staticmethod
    async def page_review_logs(*, db: AsyncSession, stmt: Any) -> dict[str, Any]:
        return await paging_data(db, stmt, schema_cls=GetReviewLogItem)


study_service: StudyService = StudyService()
