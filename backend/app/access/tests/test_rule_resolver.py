#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from backend.app.access.constants import ResourceType
from backend.app.access.crud.crud_rule import CRUDResourceRule, RuleScope


def _scope_map(scopes: list[RuleScope]) -> dict[tuple[str, bool], tuple[int, ...]]:
    """
    将范围列表整理成 (资源类型, 是否要求可继承) -> 资源 ID 的映射

    :param scopes: 规则归属范围
    :return:
    """
    return {(scope.resource_type, scope.require_inherit): scope.resource_ids for scope in scopes}


def test_bank_without_hierarchy_only_reads_own_rules() -> None:
    """题库不在任何父题库/合集下时, 只认自己的规则"""
    scopes = CRUDResourceRule.build_qbank_scopes(
        resource_id=61,
        v1_distances={61: 0},
        collection_distances={},
    )

    assert _scope_map(scopes) == {(ResourceType.QBANK, False): (61,)}


def test_v2_only_bank_still_reads_own_rules() -> None:
    """题库只存在于 V2 时(V1 链为空), 自身规则依然生效"""
    scopes = CRUDResourceRule.build_qbank_scopes(
        resource_id=1,
        v1_distances={},
        collection_distances={},
    )

    assert _scope_map(scopes) == {(ResourceType.QBANK, False): (1,)}


def test_collection_rules_cascade_to_bank() -> None:
    """合集及其祖先的规则向下穿透到题库, 且要求 inherit_to_children"""
    scopes = CRUDResourceRule.build_qbank_scopes(
        resource_id=61,
        v1_distances={61: 0},
        collection_distances={60: 1, 2346: 2},
    )

    assert _scope_map(scopes) == {
        (ResourceType.QBANK, False): (61,),
        (ResourceType.QBANK_COLLECTION, True): (60, 2346),
    }


def test_bank_own_rule_coexists_with_collection_rule() -> None:
    """题库自身规则与合集继承规则并存, 自身规则不要求 inherit_to_children"""
    scopes = CRUDResourceRule.build_qbank_scopes(
        resource_id=61,
        v1_distances={61: 0, 60: 1},
        collection_distances={60: 1},
    )
    scope_map = _scope_map(scopes)

    assert scope_map[ResourceType.QBANK, False] == (61,)
    assert scope_map[ResourceType.QBANK, True] == (60,)
    assert scope_map[ResourceType.QBANK_COLLECTION, True] == (60,)


def test_v1_parent_banks_still_inherit() -> None:
    """V1 父题库继承链保持原有行为, 不因接入 V2 而回归"""
    scopes = CRUDResourceRule.build_qbank_scopes(
        resource_id=61,
        v1_distances={61: 0, 60: 1, 2346: 2},
        collection_distances={},
    )

    assert _scope_map(scopes) == {
        (ResourceType.QBANK, False): (61,),
        (ResourceType.QBANK, True): (60, 2346),
    }


def test_collection_resource_reads_self_and_ancestors() -> None:
    """以合集为目标时, 自身规则无条件生效, 祖先规则需可继承"""
    scopes = CRUDResourceRule.build_collection_scopes(
        resource_id=60,
        distances={60: 0, 2346: 1},
    )

    assert _scope_map(scopes) == {
        (ResourceType.QBANK_COLLECTION, False): (60,),
        (ResourceType.QBANK_COLLECTION, True): (2346,),
    }


def test_root_collection_has_no_ancestor_scope() -> None:
    """根合集没有祖先范围"""
    scopes = CRUDResourceRule.build_collection_scopes(resource_id=1, distances={1: 0})

    assert _scope_map(scopes) == {(ResourceType.QBANK_COLLECTION, False): (1,)}


def test_collapse_distances_keeps_shortest_path() -> None:
    """同一节点经多条路径可达时保留最短距离"""
    distances = CRUDResourceRule._collapse_distances([(60, 2), (60, 1), (2346, 3)])

    assert distances == {60: 1, 2346: 3}
