#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import secrets
import time

from typing import Any

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.memory_card.crud.crud_card import (
    memory_card_dao,
    memory_card_deck_dao,
    memory_card_group_dao,
    memory_card_revision_dao,
)
from backend.app.memory_card.enums import MemoryRevisionStatus
from backend.app.memory_card.model.card import MemoryCard, MemoryCardDeck, MemoryCardGroup, MemoryCardRevision
from backend.app.memory_card.schema.card import (
    CreateCardParam,
    CreateDeckParam,
    CreateGroupParam,
    GetCardDetail,
    GetDeckDetail,
    GetGroupDetail,
    UpdateCardParam,
    UpdateDeckParam,
    UpdateGroupParam,
)
from backend.app.memory_card.service.grading_service import content_hash, validate_content
from backend.common.exception import errors
from backend.common.pagination import paging_data
from backend.utils.timezone import timezone


def generate_code(prefix: str = 'MC') -> str:
    """生成稳定业务编码。"""
    return f'{prefix}{int(time.time() * 1000)}{secrets.token_hex(3).upper()}'


class CardService:
    """记忆卡组、卡片与内容版本管理服务类"""

    @staticmethod
    async def _ensure_unique_code(
        *,
        db: AsyncSession,
        code: str,
        check_dao: Any,
        exclude_id: int | None = None,
    ) -> str:
        """校验编码唯一性，冲突则重新生成。"""
        candidate = code
        for _ in range(5):
            existing = await check_dao(db, candidate)
            if existing is None or (exclude_id is not None and existing.id == exclude_id):
                return candidate
            candidate = generate_code()
        raise errors.ConflictError(msg='编码生成失败，请稍后重试')

    # ============ 卡组管理 ============

    @staticmethod
    async def create_deck(
        *,
        db: AsyncSession,
        user_id: int,
        obj: CreateDeckParam,
        scope: str | None = None,
    ) -> GetDeckDetail:
        """创建卡组；管理员创建公共卡组，用户创建私人卡组。"""
        effective_scope = scope or obj.scope
        owner_id = user_id if effective_scope == 'personal' else None
        code = obj.code or generate_code()
        code = await CardService._ensure_unique_code(
            db=db,
            code=code,
            check_dao=memory_card_deck_dao.get_by_code,
        )
        deck = MemoryCardDeck(
            code=code,
            name=obj.name,
            description=obj.description,
            category_id=obj.category_id,
            scope=effective_scope,
            owner_id=owner_id,
            status=obj.status,
            daily_new_limit=obj.daily_new_limit,
            daily_review_limit=obj.daily_review_limit,
            sort_order=obj.sort_order,
            settings=obj.settings,
            created_by=user_id,
        )
        db.add(deck)
        await db.flush()
        await db.refresh(deck)
        return GetDeckDetail(
            **await CardService._deck_detail_payload(db=db, deck=deck),
        )

    @staticmethod
    async def _deck_detail_payload(*, db: AsyncSession, deck: MemoryCardDeck) -> dict[str, Any]:
        card_count = await memory_card_deck_dao.get_card_count(db, deck.id)
        return {
            'id': deck.id,
            'code': deck.code,
            'name': deck.name,
            'description': deck.description,
            'category_id': deck.category_id,
            'scope': deck.scope,
            'owner_id': deck.owner_id,
            'status': deck.status,
            'daily_new_limit': deck.daily_new_limit,
            'daily_review_limit': deck.daily_review_limit,
            'sort_order': deck.sort_order,
            'settings': deck.settings,
            'card_count': card_count,
            'created_time': deck.created_time,
            'updated_time': deck.updated_time,
        }

    @staticmethod
    async def get_deck(*, db: AsyncSession, pk: int) -> MemoryCardDeck:
        deck = await memory_card_deck_dao.get_by_id(db, pk)
        if deck is None:
            raise errors.NotFoundError(msg='卡组不存在')
        return deck

    @staticmethod
    async def get_deck_detail(*, db: AsyncSession, pk: int) -> GetDeckDetail:
        deck = await CardService.get_deck(db=db, pk=pk)
        return GetDeckDetail(**await CardService._deck_detail_payload(db=db, deck=deck))

    @staticmethod
    async def update_deck(*, db: AsyncSession, pk: int, obj: UpdateDeckParam) -> int:
        """更新卡组；仅系统卡组或所有者可操作。"""
        await CardService.get_deck(db=db, pk=pk)
        data = obj.model_dump(exclude_unset=True, exclude_none=True)
        if not data:
            return 0
        return await memory_card_deck_dao.update_model(db, pk, data)

    @staticmethod
    async def delete_deck(*, db: AsyncSession, pk: int) -> int:
        await CardService.get_deck(db=db, pk=pk)
        if await memory_card_deck_dao.get_card_count(db, pk) > 0:
            raise errors.ConflictError(msg='卡组内仍有卡片，请先处理卡片')
        return await memory_card_deck_dao.delete_model(db, pk)

    @staticmethod
    def get_deck_list_select(
        *,
        scope: str | None = None,
        status: str | None = None,
        category_id: int | None = None,
        keyword: str | None = None,
    ) -> Select:
        return memory_card_deck_dao.get_list_select(
            scope=scope,
            status=status,
            category_id=category_id,
            keyword=keyword,
        )

    @staticmethod
    async def page_decks(
        *,
        db: AsyncSession,
        scope: str | None = None,
        status: str | None = None,
        category_id: int | None = None,
        keyword: str | None = None,
    ) -> dict[str, Any]:
        stmt = CardService.get_deck_list_select(
            scope=scope,
            status=status,
            category_id=category_id,
            keyword=keyword,
        )
        return await paging_data(db, stmt)

    # ============ 卡片管理 ============

    @staticmethod
    async def _publish_revision(
        *,
        db: AsyncSession,
        card: MemoryCard,
        content: dict[str, Any],
        user_id: int,
    ) -> MemoryCardRevision:
        """为卡片创建并发布新版本。"""
        validate_content(card_type=card.card_type, response_mode=card.response_mode, content=content)
        revision_no = await memory_card_revision_dao.get_next_revision_no(db, card.id)
        revision = MemoryCardRevision(
            card_id=card.id,
            revision_no=revision_no,
            content=content,
            content_hash=content_hash(content),
            status=MemoryRevisionStatus.published.value,
            published_by=user_id,
            published_time=timezone.now(),
            created_by=user_id,
        )
        db.add(revision)
        await db.flush()
        card.current_revision_id = revision.id
        await db.flush()
        return revision

    @staticmethod
    async def _ensure_group(*, db: AsyncSession, deck_id: int, group_id: int) -> None:
        """校验分组存在且属于指定卡组。"""
        group = await memory_card_group_dao.get_by_id(db, group_id)
        if group is None:
            raise errors.NotFoundError(msg='分组不存在')
        if group.deck_id != deck_id:
            raise errors.RequestError(msg='分组不属于该卡组')

    @staticmethod
    async def create_card(*, db: AsyncSession, user_id: int, obj: CreateCardParam) -> GetCardDetail:
        """创建卡片并发布初始版本。"""
        deck = await CardService.get_deck(db=db, pk=obj.deck_id)
        if obj.group_id is not None:
            await CardService._ensure_group(db=db, deck_id=deck.id, group_id=obj.group_id)
        code = obj.code or generate_code()
        code = await CardService._ensure_unique_code(
            db=db,
            code=code,
            check_dao=memory_card_dao.get_by_code,
        )
        card = MemoryCard(
            deck_id=deck.id,
            code=code,
            title=obj.title,
            group_id=obj.group_id,
            card_type=obj.card_type,
            response_mode=obj.response_mode,
            status=obj.status,
            sort_order=obj.sort_order,
            created_by=user_id,
        )
        db.add(card)
        await db.flush()
        await CardService._publish_revision(db=db, card=card, content=obj.content.model_dump(), user_id=user_id)
        await db.refresh(card)
        return await CardService.get_card_detail(db=db, pk=card.id)

    @staticmethod
    async def get_card(*, db: AsyncSession, pk: int) -> MemoryCard:
        card = await memory_card_dao.get_by_id(db, pk)
        if card is None:
            raise errors.NotFoundError(msg='卡片不存在')
        return card

    @staticmethod
    async def _group_name_map(
        *,
        db: AsyncSession,
        group_ids: set[int],
    ) -> dict[int, str]:
        if not group_ids:
            return {}
        rows = (
            await db.execute(select(MemoryCardGroup.id, MemoryCardGroup.name).where(MemoryCardGroup.id.in_(group_ids)))
        ).all()
        return {int(row[0]): row[1] for row in rows}

    @staticmethod
    async def get_card_detail(*, db: AsyncSession, pk: int) -> GetCardDetail:
        card = await CardService.get_card(db=db, pk=pk)
        revision = None
        if card.current_revision_id is not None:
            revision = await memory_card_revision_dao.get_by_id(db, card.current_revision_id)
        group_name = None
        if card.group_id is not None:
            names = await CardService._group_name_map(db=db, group_ids={card.group_id})
            group_name = names.get(card.group_id)
        return GetCardDetail(
            id=card.id,
            deck_id=card.deck_id,
            group_id=card.group_id,
            group_name=group_name,
            deck_name=None,
            code=card.code,
            title=card.title,
            card_type=card.card_type,
            response_mode=card.response_mode,
            status=card.status,
            sort_order=card.sort_order,
            current_revision_id=card.current_revision_id,
            revision_no=revision.revision_no if revision is not None else None,
            content=revision.content if revision is not None else None,
            created_time=card.created_time,
            updated_time=card.updated_time,
        )

    @staticmethod
    async def update_card(*, db: AsyncSession, pk: int, obj: UpdateCardParam, user_id: int | None = None) -> int:
        """更新卡片；内容变化时发布新版本。"""
        card = await CardService.get_card(db=db, pk=pk)
        raw = obj.model_dump(exclude_unset=True)
        data = {key: value for key, value in raw.items() if value is not None}
        group_provided = 'group_id' in raw
        content_param = data.pop('content', None)
        updater = user_id or card.created_by or 0

        effective_type = data.get('card_type') or card.card_type
        effective_mode = data.get('response_mode') or card.response_mode

        if content_param is not None:
            validate_content(card_type=effective_type, response_mode=effective_mode, content=content_param)
            revision = await CardService._publish_revision(
                db=db,
                card=card,
                content=content_param,
                user_id=updater,
            )
            data['current_revision_id'] = revision.id

        if group_provided:
            data.pop('group_id', None)
            if obj.group_id is not None:
                await CardService._ensure_group(db=db, deck_id=card.deck_id, group_id=obj.group_id)
            data['group_id'] = obj.group_id

        if data:
            await memory_card_dao.update_model(db, pk, data)
        return 1

    # ============ 分组管理 ============

    @staticmethod
    async def create_group(*, db: AsyncSession, user_id: int, obj: CreateGroupParam) -> GetGroupDetail:
        """在卡组下创建分组（章/节等目录）。"""
        await CardService.get_deck(db=db, pk=obj.deck_id)
        if obj.parent_id is not None:
            parent = await memory_card_group_dao.get_by_id(db, obj.parent_id)
            if parent is None:
                raise errors.NotFoundError(msg='父分组不存在')
            if parent.deck_id != obj.deck_id:
                raise errors.RequestError(msg='父分组不属于该卡组')
        group = MemoryCardGroup(
            deck_id=obj.deck_id,
            name=obj.name,
            parent_id=obj.parent_id,
            sort_order=obj.sort_order,
            status=obj.status,
            created_by=user_id,
        )
        db.add(group)
        await db.flush()
        await db.refresh(group)
        return await CardService.get_group_detail(db=db, pk=group.id)

    @staticmethod
    async def get_group_detail(*, db: AsyncSession, pk: int) -> GetGroupDetail:
        group = await memory_card_group_dao.get_by_id(db, pk)
        if group is None:
            raise errors.NotFoundError(msg='分组不存在')
        count_map = await memory_card_group_dao.count_cards_by_groups(db, [group.id])
        return GetGroupDetail(
            id=group.id,
            deck_id=group.deck_id,
            parent_id=group.parent_id,
            name=group.name,
            sort_order=group.sort_order,
            status=group.status,
            card_count=count_map.get(group.id, 0),
        )

    @staticmethod
    async def get_group_tree(*, db: AsyncSession, deck_id: int) -> list[GetGroupDetail]:
        """获取卡组的分组树（含各分组直接卡片数）。"""
        groups = await memory_card_group_dao.list_by_deck(db, deck_id)
        count_map = await memory_card_group_dao.count_cards_by_groups(db, [g.id for g in groups])
        by_id: dict[int, GetGroupDetail] = {}
        for group in groups:
            by_id[group.id] = GetGroupDetail(
                id=group.id,
                deck_id=group.deck_id,
                parent_id=group.parent_id,
                name=group.name,
                sort_order=group.sort_order,
                status=group.status,
                card_count=count_map.get(group.id, 0),
            )
        roots: list[GetGroupDetail] = []
        for node in by_id.values():
            if node.parent_id is not None and node.parent_id in by_id:
                by_id[node.parent_id].children.append(node)
            else:
                roots.append(node)
        roots.sort(key=lambda node: (node.sort_order, node.id))
        return roots

    @staticmethod
    async def update_group(*, db: AsyncSession, pk: int, obj: UpdateGroupParam) -> int:
        """更新分组；支持改名、移动父级、调整排序与状态。"""
        group = await memory_card_group_dao.get_by_id(db, pk)
        if group is None:
            raise errors.NotFoundError(msg='分组不存在')
        raw = obj.model_dump(exclude_unset=True)
        data = {key: value for key, value in raw.items() if value is not None}
        parent_provided = 'parent_id' in raw
        data.pop('parent_id', None)

        if parent_provided:
            if obj.parent_id is not None:
                if obj.parent_id == group.id:
                    raise errors.RequestError(msg='不能把分组移动到自己下面')
                subtree = await memory_card_group_dao.list_subtree_ids(db, group.id)
                if obj.parent_id in subtree:
                    raise errors.RequestError(msg='不能把分组移动到自己的子分组下')
                parent = await memory_card_group_dao.get_by_id(db, obj.parent_id)
                if parent is None:
                    raise errors.NotFoundError(msg='父分组不存在')
                if parent.deck_id != group.deck_id:
                    raise errors.RequestError(msg='父分组不属于该卡组')
            data['parent_id'] = obj.parent_id

        if not data:
            return 0
        return await memory_card_group_dao.update_model(db, pk, data)

    @staticmethod
    async def delete_group(*, db: AsyncSession, pk: int) -> int:
        """删除分组及其子分组，组内卡片移回卡组根目录。"""
        group = await memory_card_group_dao.get_by_id(db, pk)
        if group is None:
            raise errors.NotFoundError(msg='分组不存在')
        subtree = await memory_card_group_dao.list_subtree_ids(db, group.id)
        await memory_card_group_dao.clear_cards_of_groups(db, subtree)
        deleted = 0
        for group_id in subtree:
            deleted += await memory_card_group_dao.delete_model(db, group_id)
        return deleted

    @staticmethod
    async def delete_card(*, db: AsyncSession, pk: int) -> int:
        await CardService.get_card(db=db, pk=pk)
        return await memory_card_dao.delete_model(db, pk)

    @staticmethod
    def get_card_list_select(
        *,
        deck_id: int | None = None,
        group_id: int | None = None,
        status: str | None = None,
        keyword: str | None = None,
    ) -> Select:
        return memory_card_dao.get_list_select(
            deck_id=deck_id,
            group_id=group_id,
            status=status,
            keyword=keyword,
        )

    @staticmethod
    async def page_cards(
        *,
        db: AsyncSession,
        deck_id: int | None = None,
        group_id: int | None = None,
        status: str | None = None,
        keyword: str | None = None,
    ) -> dict[str, Any]:
        stmt = CardService.get_card_list_select(
            deck_id=deck_id,
            group_id=group_id,
            status=status,
            keyword=keyword,
        )
        page_data = await paging_data(db, stmt)
        card_ids = [int(item['id']) for item in page_data['items']]
        revision_map = await memory_card_revision_dao.get_revision_no_map(db, card_ids)
        deck_ids = sorted({int(item['deck_id']) for item in page_data['items']})
        deck_names: dict[int, str] = {}
        if deck_ids:
            rows = (
                await db.execute(select(MemoryCardDeck.id, MemoryCardDeck.name).where(MemoryCardDeck.id.in_(deck_ids)))
            ).all()
            deck_names = {int(row[0]): row[1] for row in rows}
        group_ids = {int(item['group_id']) for item in page_data['items'] if item.get('group_id')}
        group_names = await CardService._group_name_map(db=db, group_ids=group_ids)
        for item in page_data['items']:
            item['revision_no'] = revision_map.get(int(item['id']))
            item['deck_name'] = deck_names.get(int(item['deck_id']))
            item['group_name'] = group_names.get(int(item['group_id'])) if item.get('group_id') else None
        return page_data


card_service: CardService = CardService()
