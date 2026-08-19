#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ruff: noqa: ANN001, ANN202, RUF029
from types import SimpleNamespace

from backend.app.memory_card.service import card_service as card_module
from backend.app.memory_card.service.card_service import card_service


async def test_get_group_tree_builds_hierarchy(monkeypatch) -> None:
    """分组树按 parent_id 组装为多级结构并统计卡片数。"""
    groups = [
        SimpleNamespace(id=1, deck_id=10, parent_id=None, name='第一章', sort_order=1, status='active'),
        SimpleNamespace(id=2, deck_id=10, parent_id=1, name='第一节', sort_order=1, status='active'),
        SimpleNamespace(id=3, deck_id=10, parent_id=2, name='小节一', sort_order=1, status='active'),
        SimpleNamespace(id=4, deck_id=10, parent_id=None, name='第二章', sort_order=2, status='active'),
    ]

    async def fake_list_by_deck(db, deck_id):
        return groups

    async def fake_count_cards_by_groups(db, group_ids):
        return {gid: gid * 10 for gid in group_ids}

    monkeypatch.setattr(card_module.memory_card_group_dao, 'list_by_deck', fake_list_by_deck)
    monkeypatch.setattr(card_module.memory_card_group_dao, 'count_cards_by_groups', fake_count_cards_by_groups)

    tree = await card_service.get_group_tree(db=None, deck_id=10)

    assert len(tree) == 2
    assert tree[0].name == '第一章'
    assert tree[0].sort_order == 1
    assert tree[0].card_count == 10
    assert len(tree[0].children) == 1
    assert tree[0].children[0].name == '第一节'
    assert tree[0].children[0].children[0].name == '小节一'
    assert tree[1].name == '第二章'
    assert tree[1].card_count == 40


async def test_delete_group_clears_cards_and_deletes_subtree(monkeypatch) -> None:
    """删除分组应把子分组卡片移回根目录并软删除整棵子树。"""
    async def fake_get_by_id(db, pk):
        return SimpleNamespace(id=1, deck_id=10, parent_id=None)

    async def fake_subtree(db, group_id):
        return [1, 2, 3]

    cleared: list[list[int]] = []
    deleted_ids: list[int] = []

    async def fake_clear(db, group_ids):
        cleared.append(list(group_ids))

    async def fake_delete(db, group_id):
        deleted_ids.append(group_id)
        return 1

    monkeypatch.setattr(card_module.memory_card_group_dao, 'get_by_id', fake_get_by_id)
    monkeypatch.setattr(card_module.memory_card_group_dao, 'list_subtree_ids', fake_subtree)
    monkeypatch.setattr(card_module.memory_card_group_dao, 'clear_cards_of_groups', fake_clear)
    monkeypatch.setattr(card_module.memory_card_group_dao, 'delete_model', fake_delete)

    deleted = await card_service.delete_group(db=None, pk=1)

    assert deleted == 3
    assert cleared == [[1, 2, 3]]
    assert deleted_ids == [1, 2, 3]
