#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Any

import pytest

from backend.plugin.agents.schema import (
    AgentType,
    ConsensusLevel,
    EventType,
    GradeLevel,
    SectionName,
)
from backend.plugin.agents.service.common.orchestrator import NodeContext
from backend.plugin.agents.service.shenlun import build_pipeline
from backend.plugin.agents.service.shenlun.nodes.rubric_loader import load_rubric
from backend.plugin.agents.service.shenlun.nodes.scorer import _compute_cap_factor
from backend.plugin.agents.tests.conftest import async_test
from backend.plugin.agents.tests.fake_llm import FakeLLMClient


@async_test
async def test_pipeline_runs_all_12_nodes(
    node_context: NodeContext,
    fake_llm: FakeLLMClient,
) -> None:
    """端到端跑完 12 节点, 验证每个节点都被调用且角色路由正确"""
    pipeline = build_pipeline()
    await pipeline.run(node_context)

    called_nodes = [c['node'] for c in fake_llm.calls]
    expected = {
        'classifier',
        'material_parser',
        'reference_analyzer',
        'answer_analyzer',
        'point_matcher',
        'structure_analyzer',
        'scorer',
        'diagnoser',
        'suggester',
        'rewriter',
        'reviewer',
    }
    assert set(called_nodes) == expected, f'缺失或多余节点调用: {set(called_nodes) ^ expected}'

    role_by_node = {c['node']: c['role'] for c in fake_llm.calls}
    assert role_by_node['classifier'] == 'mini'
    assert role_by_node['structure_analyzer'] == 'mini'
    assert role_by_node['scorer'] == 'primary'
    assert role_by_node['rewriter'] == 'primary'

    state = node_context.state
    assert len(state.traces) == 12, f'期望 12 traces, 实际 {len(state.traces)}'


@async_test
async def test_pipeline_produces_complete_agent_report(node_context: NodeContext) -> None:
    """端到端跑完后所有 section 字段应该齐全"""
    await build_pipeline().run(node_context)
    state = node_context.state

    assert state.question_type == '大作文'
    assert state.rubric is not None
    assert len(state.rubric['dimensions']) == 5

    assert state.score_card is not None
    assert 0 <= state.score_card.score <= state.score_card.score_total
    assert state.score_card.score_total == 40.0
    assert state.score_card.level in (GradeLevel.a, GradeLevel.b, GradeLevel.c, GradeLevel.d)
    assert state.score_card.level_label
    assert len(state.score_card.rubric_scores) == 5

    assert state.key_points is not None
    assert len(state.key_points.material_points) == 3
    assert len(state.key_points.reference_points) == 4
    assert len(state.key_points.answer_points) == 2

    high_count = sum(1 for p in state.key_points.reference_points if p.consensus_level == ConsensusLevel.high)
    assert high_count == 2, f'期望 2 条 high consensus, 实际 {high_count}'

    assert len(state.key_points.missing_points) == 2

    matched_in_refs = sum(1 for p in state.key_points.reference_points if p.matched_user_text)
    assert matched_in_refs == 2, '应有 2 条参考要点被回填 matched_user_text'

    assert state.issues is not None and len(state.issues.items) == 3
    assert state.suggestions is not None and len(state.suggestions.items) == 3
    assert state.rewritten_text is not None and state.rewritten_text.revised.startswith('mock 改写')
    assert state.qc is not None and state.qc.passed is True


@async_test
async def test_pipeline_sse_emits_section_ready_events(
    node_context: NodeContext,
    collected_events: list[dict[str, Any]],
) -> None:
    """SSE 应推送 6 个 section_ready + completed 事件"""
    await build_pipeline().run(node_context)

    section_ready_events = [e for e in collected_events if e['event_type'] == EventType.section_ready.value]
    section_names = [e['section_name'] for e in section_ready_events]

    expected_sections = {
        SectionName.key_points.value,
        SectionName.score_card.value,
        SectionName.issues.value,
        SectionName.suggestions.value,
        SectionName.rewritten_text.value,
        SectionName.qc.value,
    }
    assert set(section_names) == expected_sections, f'缺失或多余 section 推送: {set(section_names) ^ expected_sections}'

    last_event = collected_events[-1]
    assert last_event['event_type'] == EventType.completed.value
    assert last_event['progress'] == 1.0


@async_test
async def test_pipeline_extras_carries_structure_data(node_context: NodeContext) -> None:
    """structure_analyzer 应把结果存到 state.extras['structure']"""
    await build_pipeline().run(node_context)
    structure = node_context.state.extras.get('structure')
    assert structure is not None, 'structure_analyzer 应填入 state.extras'
    assert structure['structure_type'] == '总分总'
    assert structure['has_intro'] is True


@async_test
async def test_parallel_group_race_free(node_context: NodeContext) -> None:
    """ParallelGroup 内三节点并行修改 key_points 不同字段, 不丢数据"""
    await build_pipeline().run(node_context)
    kp = node_context.state.key_points
    assert kp is not None
    assert len(kp.material_points) == 3, '材料要点不应被并发覆盖'
    assert len(kp.reference_points) == 4, '参考要点不应被并发覆盖'
    assert len(kp.answer_points) >= 2, '考生要点不应被并发覆盖'


def test_pipeline_agent_type_is_shenlun() -> None:
    """build_pipeline 应构建 shenlun agent"""
    pipeline = build_pipeline()
    assert pipeline.agent_type == AgentType.shenlun


@async_test
async def test_pipeline_accepts_checkpoint_callback(node_context: NodeContext) -> None:
    """build_pipeline 应支持持久化 checkpoint 回调"""
    checkpoints: list[tuple[str, float]] = []

    async def _checkpoint(stage: str, progress: float, snapshot: dict[str, Any]) -> None:
        checkpoints.append((stage, progress))
        assert 'traces' in snapshot

    await build_pipeline(on_checkpoint=_checkpoint).run(node_context)
    assert checkpoints
    assert checkpoints[-1][0] == 'review'


@async_test
async def test_rubric_loader_uses_yaml_total_when_score_total_missing(
    node_context: NodeContext,
) -> None:
    """未传 score_total 时应使用题型 YAML 原始满分"""
    node_context.state.question_type = '归纳概括'
    node_context.state.score_total = None

    await load_rubric(node_context)

    assert node_context.state.rubric is not None
    assert node_context.state.rubric['total'] == 10
    assert node_context.state.score_total == 10
    assert sum(item['max_score'] for item in node_context.state.rubric['dimensions']) == 10


@async_test
async def test_rubric_loader_scales_dimensions_when_score_total_override(
    node_context: NodeContext,
) -> None:
    """传入自定义 score_total 时应等比缩放维度满分"""
    node_context.state.question_type = '归纳概括'
    node_context.state.score_total = 20

    await load_rubric(node_context)

    assert node_context.state.rubric is not None
    assert node_context.state.rubric['total'] == 20
    assert sum(item['max_score'] for item in node_context.state.rubric['dimensions']) == 20


def test_empty_materials_do_not_trigger_material_citation_cap() -> None:
    """材料为空时不应因为无材料引用触发 50% 硬上限"""
    cap_factor, cap_reason = _compute_cap_factor(
        user_text='这是一段正常作答内容，围绕题目展开分析并提出对策。',
        materials='',
        question='请结合实际作答。',
        missing_high_count=0,
    )

    assert cap_factor == 1.0
    assert cap_reason == ''


@pytest.mark.parametrize(
    'node_name, expected_role',
    [
        ['classifier', 'mini'],
        ['structure_analyzer', 'mini'],
        ['material_parser', 'primary'],
        ['scorer', 'primary'],
        ['rewriter', 'primary'],
        ['reviewer', 'primary'],
    ],
)
@async_test
async def test_node_role_assignment(
    node_context: NodeContext,
    fake_llm: FakeLLMClient,
    node_name: str,
    expected_role: str,
) -> None:
    """关键节点的模型角色映射应符合预期"""
    await build_pipeline().run(node_context)
    role = next(c['role'] for c in fake_llm.calls if c['node'] == node_name)
    assert role == expected_role, f'{node_name} 应使用 {expected_role}, 实际 {role}'
