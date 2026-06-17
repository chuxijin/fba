#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Agent 批改 CLI

用法:
  .venv/Scripts/python -m backend.plugin.agents.scripts.grade_one --sample backend/plugin/agents/tests/samples/sample_1.yaml --mode mock
  .venv/Scripts/python -m backend.plugin.agents.scripts.grade_one --sample backend/plugin/agents/tests/samples/sample_1.yaml --mode real

--mode mock: 用 FakeLLMClient 跑流程, 验证数据流通畅 (不调真实 LLM)
--mode real: 调真实 LLM (需要 ai_provider 与 ai_model 在数据库内 status=1)
"""

import argparse
import asyncio
import sys

from pathlib import Path
from typing import Any

import yaml

from backend.plugin.agents.schema import GradingState
from backend.plugin.agents.schema.grading import DEFAULT_AGENT_MODEL_ID, DEFAULT_AGENT_PROVIDER_ID
from backend.plugin.agents.service.common.llm import LLMClient
from backend.plugin.agents.service.common.orchestrator import NodeContext
from backend.plugin.agents.service.common.prompts import PromptLoader
from backend.plugin.agents.service.common.streaming import EventBus
from backend.plugin.agents.service.shenlun import build_pipeline


def _state_from_sample(sample: dict[str, Any]) -> GradingState:
    """从样卷 dict 构造 GradingState"""
    return GradingState(
        task_id=0,
        user_id=int(sample.get('user_id', 1)),
        provider_id=int(sample.get('provider_id', DEFAULT_AGENT_PROVIDER_ID)),
        primary_model=str(sample.get('model_id', DEFAULT_AGENT_MODEL_ID)),
        question_stem=str(sample.get('question_stem', '')),
        question=str(sample['question']),
        materials=str(sample.get('materials', '')),
        reference_answers=list(sample.get('reference_answers', [])),
        user_answer_text=str(sample['user_answer_text']),
        score_total=float(sample.get('score_total', 40.0)),
        question_type=sample.get('question_type'),
    )


def _get_prompts() -> PromptLoader:
    """加载 shenlun prompts 目录"""
    base = Path(__file__).resolve().parent.parent / 'service' / 'shenlun' / 'prompts'
    return PromptLoader(base_dir=base)


async def run_mock(sample: dict[str, Any]) -> GradingState:
    """用 FakeLLMClient 跑 pipeline"""
    from backend.plugin.agents.tests.fake_llm import FakeLLMClient

    state = _state_from_sample(sample)
    ctx = NodeContext(
        state=state,
        db=None,
        event_bus=EventBus(),
        llm=FakeLLMClient(),  # type: ignore[arg-type]
        prompts=_get_prompts(),
    )
    await build_pipeline().run(ctx)
    return state


async def run_real(sample: dict[str, Any]) -> GradingState:
    """用真实 LLM 跑 pipeline, 不入库"""
    from backend.database.db import async_db_session

    state = _state_from_sample(sample)
    async with async_db_session() as db:
        ctx = NodeContext(
            state=state,
            db=db,
            event_bus=EventBus(),
            llm=LLMClient(
                provider_id=int(sample['provider_id']),
                primary_model_id=str(sample['model_id']),
                mini_model_id=sample.get('mini_model_id'),
            ),
            prompts=_get_prompts(),
        )
        await build_pipeline().run(ctx)
    return state


def _print_report(state: GradingState) -> None:
    """打印批改报告"""
    sep = '=' * 70
    print(sep)
    print(f'题型识别: {state.question_type}')
    print(
        f'评分细则: {state.rubric.get("total") if state.rubric else "?"} 分制, '
        f'{len(state.rubric.get("dimensions", [])) if state.rubric else 0} 维度'
    )

    if state.score_card:
        sc = state.score_card
        print(sep)
        print(f'【评分卡】 {sc.score}/{sc.score_total} [{sc.level}/{sc.level_label}]')
        for s in sc.rubric_scores:
            print(f'  {s.name:6} {s.score:4}/{s.max_score:<3} [{s.level}/{s.level_label}]: {s.comment}')
        print(f'\n【总评】 {sc.summary}')
        if sc.system_notes:
            print('\n【系统提示】 (评分被代码层硬规则约束)')
            for note in sc.system_notes:
                print(f'  - {note}')

    if state.key_points:
        kp = state.key_points
        high = sum(1 for p in kp.reference_points if p.consensus_level == 'high')
        med = sum(1 for p in kp.reference_points if p.consensus_level == 'medium')
        print(sep)
        print(
            f'【要点对比】 材料 {len(kp.material_points)} 条 / '
            f'参考 {len(kp.reference_points)} 条 (high {high} + med {med}) / '
            f'考生 {len(kp.answer_points)} 条 / 缺失 {len(kp.missing_points)} 条'
        )
        if kp.missing_points:
            print('  缺失要点:')
            for mp in kp.missing_points:
                print(f'    - [{mp.consensus_level}] {mp.text}')

    if state.issues and state.issues.items:
        print(sep)
        print(f'【问题诊断】 ({len(state.issues.items)} 条)')
        for i in state.issues.items:
            loc = f'@{i.location} ' if i.location else ''
            print(f'  [{i.severity:8}] {i.category:8} {loc}{i.description}')

    if state.suggestions and state.suggestions.items:
        print(sep)
        print(f'【提升建议】 ({len(state.suggestions.items)} 条)')
        for s in state.suggestions.items:
            print(f'  [{s.priority:6}] {s.action}')

    if state.rewritten_text:
        rt = state.rewritten_text
        print(sep)
        print(f'【改写示范】 原文 {len(rt.original)} 字')
        if rt.diff_summary:
            print(f'  改动: {rt.diff_summary}')
        if rt.changes:
            print(f'\n  逐条改动 ({len(rt.changes)} 条):')
            for i, c in enumerate(rt.changes, 1):
                print(f'    {i}. 原文: {c.original}')
                print(f'       改写: {c.revised}')
                print(f'       原因: {c.reason}')
        diff_text = rt.inline_diff if rt.inline_diff else rt.revised
        print('\n  行内对比 (~~删除线~~=删除, **加粗**=新增):')
        print(f'  {diff_text}')

    if state.qc:
        print(sep)
        print(f'【质检】 passed={state.qc.passed} confidence={state.qc.confidence}')
        for n in state.qc.notes:
            print(f'  - {n}')

    print(sep)
    print(f'【执行轨迹】 {len(state.traces)} 个节点')
    total_ms = sum(t.duration_ms for t in state.traces)
    total_tokens_in = sum(t.tokens_in for t in state.traces)
    total_tokens_out = sum(t.tokens_out for t in state.traces)
    for t in state.traces:
        print(f'  {t.duration_ms:6}ms tokens={t.tokens_in:>5}/{t.tokens_out:<5} {t.agent}')
    print(f'  共 {total_ms}ms / 输入 {total_tokens_in} token / 输出 {total_tokens_out} token')


def main() -> None:
    """命令行入口"""
    parser = argparse.ArgumentParser(description='Agent 批改 CLI')
    parser.add_argument('--sample', required=True, help='样卷 yaml 路径')
    parser.add_argument(
        '--mode', choices=['mock', 'real'], default='mock', help='mock 用 FakeLLM 验证数据流, real 调真实 LLM'
    )
    args = parser.parse_args()

    sample_path = Path(args.sample)
    if not sample_path.exists():
        print(f'样卷文件不存在: {sample_path}', file=sys.stderr)
        sys.exit(1)

    sample = yaml.safe_load(sample_path.read_text(encoding='utf-8'))
    if not isinstance(sample, dict):
        print(f'样卷 yaml 根节点必须是 mapping: {sample_path}', file=sys.stderr)
        sys.exit(1)

    # 支持 extends 字段做样卷继承, 只重写差异字段
    if 'extends' in sample:
        parent_path = sample_path.parent / str(sample.pop('extends'))
        if not parent_path.exists():
            print(f'extends 引用的父样卷不存在: {parent_path}', file=sys.stderr)
            sys.exit(1)
        parent = yaml.safe_load(parent_path.read_text(encoding='utf-8'))
        if not isinstance(parent, dict):
            print(f'extends 父样卷 yaml 根节点必须是 mapping: {parent_path}', file=sys.stderr)
            sys.exit(1)
        parent.update(sample)
        sample = parent

    runner = run_mock if args.mode == 'mock' else run_real
    state = asyncio.run(runner(sample))
    _print_report(state)


if __name__ == '__main__':
    main()
