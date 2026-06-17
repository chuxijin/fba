#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from collections import defaultdict
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.admin.model.category import Category
from backend.app.question_bank.model.bank import QuestionBank
from backend.app.question_bank.model.chapter import QuestionChapter
from backend.common.cache.redis_cache import RedisCache
from backend.common.cache.serializers import JsonSerializer
from backend.utils.build_tree import traversal_to_tree

GROUP_TREE_CACHE_TTL = 300


all_banks_cache: RedisCache[list[dict[str, Any]]] = RedisCache(
    prefix='qbank:group_tree:all_banks:v1',
    ttl=GROUP_TREE_CACHE_TTL,
    serializer=JsonSerializer(),
    local=True,
    invalidate_pubsub=True,
)

all_chapters_cache: RedisCache[list[dict[str, Any]]] = RedisCache(
    prefix='qbank:group_tree:all_chapters:v1',
    ttl=GROUP_TREE_CACHE_TTL,
    serializer=JsonSerializer(),
    local=True,
    invalidate_pubsub=True,
)

kp_categories_cache: RedisCache[list[dict[str, Any]]] = RedisCache(
    prefix='qbank:group_tree:kp_categories:v2',
    ttl=GROUP_TREE_CACHE_TTL,
    serializer=JsonSerializer(),
    local=True,
    invalidate_pubsub=True,
)


def _value(item: Any, key: str) -> Any:
    """获取对象或字典字段值"""
    if isinstance(item, dict):
        return item.get(key)
    return getattr(item, key, None)


async def _load_all_banks(db: AsyncSession) -> list[dict[str, Any]]:
    """加载全部题库元数据"""

    async def factory() -> list[dict[str, Any]]:
        stmt = select(
            QuestionBank.id,
            QuestionBank.name,
            QuestionBank.parent_id,
        )
        rows = (await db.execute(stmt)).all()
        return [
            {
                'id': row.id,
                'name': row.name,
                'parent_id': row.parent_id,
            }
            for row in rows
        ]

    return await all_banks_cache.get_or_set(factory=factory) or []


async def _load_all_chapters(db: AsyncSession) -> list[dict[str, Any]]:
    """加载全部章节元数据"""

    async def factory() -> list[dict[str, Any]]:
        stmt = select(
            QuestionChapter.id,
            QuestionChapter.bank_id,
            QuestionChapter.parent_id,
            QuestionChapter.name,
            QuestionChapter.level,
            QuestionChapter.sort_order,
        ).order_by(QuestionChapter.level, QuestionChapter.sort_order)
        rows = (await db.execute(stmt)).all()
        return [
            {
                'id': row.id,
                'bank_id': row.bank_id,
                'parent_id': row.parent_id,
                'name': row.name,
                'level': row.level,
                'sort_order': row.sort_order,
            }
            for row in rows
        ]

    return await all_chapters_cache.get_or_set(factory=factory) or []


def _sum_counts(node: dict) -> int:
    """自底向上汇总 count"""
    children = node.get('children', [])
    if children:
        node['count'] = sum(_sum_counts(child) for child in children)
    return node['count']


def _prune_empty(nodes: list[dict]) -> list[dict]:
    """裁剪空分支"""
    result = []
    for node in nodes:
        if node.get('count', 0) == 0:
            continue
        if 'children' in node:
            node['children'] = _prune_empty(node['children'])
        result.append(node)
    return result


def _clean_fields(nodes: list[dict]) -> list[dict]:
    """仅保留前端需要的字段"""
    keep = {'id', 'name', 'count', 'children', 'bank_id'}
    cleaned = []
    for node in nodes:
        item = {key: value for key, value in node.items() if key in keep}
        if 'children' in item:
            item['children'] = _clean_fields(item['children'])
        cleaned.append(item)
    return cleaned


def build_kp_tree(categories: list[Category | dict[str, Any]], count_map: dict[str, int]) -> list[dict]:
    """
    根据知识点分类与计数构建树

    :param categories: 知识点分类列表
    :param count_map: 知识点名称到数量的映射
    :return:
    """
    nodes = [
        {
            'id': _value(category, 'id'),
            'parent_id': _value(category, 'parent_id'),
            'name': _value(category, 'name'),
            'sort': _value(category, 'sort_order') or 0,
            'count': count_map.get(str(_value(category, 'name') or ''), 0),
        }
        for category in categories
    ]

    tree = traversal_to_tree(nodes)
    for root in tree:
        _sum_counts(root)
    tree = _prune_empty(tree)
    return _clean_fields(tree)


def build_bank_tree(
    banks: list[QuestionBank | dict[str, Any]],
    chapters: list[QuestionChapter | dict[str, Any]],
    count_map: dict[tuple[int, int | None], int],
) -> list[dict]:
    """
    根据题库、章节与计数构建树

    :param banks: 题库列表
    :param chapters: 章节列表
    :param count_map: (bank_id, chapter_id) 到数量的映射
    :return:
    """
    chapter_dict = {_value(chapter, 'id'): chapter for chapter in chapters}
    bank_chapter_ids: dict[int, set[int]] = defaultdict(set)
    for bank_id, chapter_id in count_map:
        if chapter_id is not None:
            bank_chapter_ids[bank_id].add(chapter_id)

    result_nodes: list[dict] = []
    for bank in banks:
        bank_id = _value(bank, 'id')
        if bank_id is None:
            continue

        bank_direct_count = count_map.get((bank_id, None), 0)
        chapter_ids = bank_chapter_ids.get(bank_id, set())
        chapter_nodes = []
        for chapter_id in chapter_ids:
            chapter = chapter_dict.get(chapter_id)
            if chapter is None:
                continue

            parent_id = _value(chapter, 'parent_id')
            chapter_nodes.append({
                'id': _value(chapter, 'id'),
                'parent_id': parent_id if parent_id in chapter_ids else None,
                'name': _value(chapter, 'name'),
                'sort': _value(chapter, 'sort_order') or 0,
                'count': count_map.get((bank_id, chapter_id), 0),
                'bank_id': bank_id,
            })

        chapter_tree = traversal_to_tree(chapter_nodes) if chapter_nodes else []
        for root in chapter_tree:
            _sum_counts(root)
        chapter_tree = _prune_empty(chapter_tree)

        chapter_total = sum(node.get('count', 0) for node in chapter_tree)
        bank_total = bank_direct_count + chapter_total

        result_nodes.append({
            'id': bank_id,
            'name': _value(bank, 'name'),
            'count': bank_total,
            'parent_id': _value(bank, 'parent_id'),
            'sort': 0,
            'children': _clean_fields(chapter_tree),
        })

    bank_tree = traversal_to_tree(result_nodes)
    for root in bank_tree:
        _sum_counts(root)
    bank_tree = _prune_empty(bank_tree)
    return _clean_fields(bank_tree)


async def get_descendant_bank_ids(db: AsyncSession, bank_id: int) -> list[int]:
    """
    获取题库及其所有后代题库 ID

    :param db: 数据库会话
    :param bank_id: 题库 ID
    :return:
    """
    all_banks = await _load_all_banks(db)
    children_map: dict[int, list[int]] = defaultdict(list)
    for row in all_banks:
        parent_id = row.get('parent_id')
        if parent_id is not None:
            children_map[int(parent_id)].append(int(row['id']))

    result: list[int] = []
    pending = [bank_id]
    while pending:
        current = pending.pop()
        result.append(current)
        pending.extend(children_map.get(current, []))
    return result


async def load_kp_categories(db: AsyncSession) -> list[Category | dict[str, Any]]:
    """
    加载知识点分类

    :param db: 数据库会话
    :return:
    """

    async def factory() -> list[dict[str, Any]]:
        stmt = (
            select(
                Category.id,
                Category.parent_id,
                Category.name,
                Category.sort_order,
            )
            .where(
                Category.app_code == 'youanshang',
                Category.type == 'knowledge_point',
                Category.status.is_(True),
            )  # noqa: E712
            .order_by(Category.level, Category.sort_order)
        )
        rows = (await db.execute(stmt)).all()
        return [
            {
                'id': row.id,
                'parent_id': row.parent_id,
                'name': row.name,
                'sort_order': row.sort_order,
            }
            for row in rows
        ]

    return await kp_categories_cache.get_or_set(factory=factory) or []


async def load_banks_and_chapters(
    db: AsyncSession, bank_ids: set[int], chapter_ids: set[int] | None = None
) -> tuple[list[QuestionBank | dict[str, Any]], list[QuestionChapter | dict[str, Any]]]:
    """
    加载题库与章节元数据

    :param db: 数据库会话
    :param bank_ids: 题库 ID 集合
    :param chapter_ids: 章节 ID 集合
    :return:
    """
    if not bank_ids:
        return [], []

    requested_bank_ids = set(bank_ids)
    all_banks = await _load_all_banks(db)
    bank_map = {int(row['id']): row for row in all_banks}

    resolved_bank_ids = set(requested_bank_ids)
    pending_bank_ids = list(requested_bank_ids)
    while pending_bank_ids:
        current_bank_id = pending_bank_ids.pop()
        bank_row = bank_map.get(current_bank_id)
        if bank_row is None:
            continue

        parent_id = bank_row.get('parent_id')
        if parent_id and parent_id not in resolved_bank_ids:
            resolved_bank_ids.add(parent_id)
            pending_bank_ids.append(parent_id)

    banks = [bank_map[bank_id] for bank_id in resolved_bank_ids if bank_id in bank_map]

    all_chapters = await _load_all_chapters(db)
    if chapter_ids:
        chapter_map = {int(row['id']): row for row in all_chapters}
        resolved_chapter_ids = set(chapter_ids)
        pending_chapter_ids = list(chapter_ids)
        while pending_chapter_ids:
            current_chapter_id = pending_chapter_ids.pop()
            chapter_row = chapter_map.get(current_chapter_id)
            if chapter_row is None:
                continue

            parent_id = chapter_row.get('parent_id')
            if parent_id and parent_id not in resolved_chapter_ids:
                resolved_chapter_ids.add(parent_id)
                pending_chapter_ids.append(parent_id)

        chapters = [chapter_map[chapter_id] for chapter_id in resolved_chapter_ids if chapter_id in chapter_map]
    else:
        chapters = [row for row in all_chapters if row['bank_id'] in requested_bank_ids]

    return banks, chapters
