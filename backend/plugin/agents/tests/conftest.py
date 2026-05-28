#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import asyncio
import functools

from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any, TypeVar

import pytest

from backend.plugin.agents.schema import GradingState
from backend.plugin.agents.service.common.orchestrator import NodeContext
from backend.plugin.agents.service.common.prompts import PromptLoader
from backend.plugin.agents.service.common.streaming import EventBus
from backend.plugin.agents.tests.fake_llm import FakeLLMClient

T = TypeVar('T')


def async_test(func: Callable[..., Awaitable[T]]) -> Callable[..., T]:
    """把 async 测试函数同步化, 避免依赖 pytest-asyncio"""

    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> T:
        return asyncio.run(func(*args, **kwargs))

    return wrapper


@pytest.fixture
def fake_llm() -> FakeLLMClient:
    """Mock LLM 客户端"""
    return FakeLLMClient()


@pytest.fixture
def event_bus() -> EventBus:
    """独立 EventBus 避免与全局单例冲突"""
    return EventBus()


@pytest.fixture
def shenlun_prompts() -> PromptLoader:
    """真实加载 shenlun prompts (yaml 文件存在)"""
    base = Path(__file__).resolve().parent.parent / 'service' / 'shenlun' / 'prompts'
    return PromptLoader(base_dir=base)


@pytest.fixture
def grading_state() -> GradingState:
    """占位 GradingState (mock 测试不需要真实内容)"""
    return GradingState(
        task_id=1,
        user_id=1,
        provider_id=1,
        primary_model='mock-model',
        question_stem='[占位] 题干',
        question='[占位] 请就当前区域协同发展中的问题与对策, 写一篇议论文, 800-1200 字',
        materials='[占位] 区域协同发展材料……',
        reference_answers=[
            '[占位] 参考答案 1',
            '[占位] 参考答案 2',
            '[占位] 参考答案 3',
        ],
        user_answer_text='[占位] 学生作答 800 字……',
        score_total=40.0,
    )


@pytest.fixture
def node_context(
    grading_state: GradingState,
    fake_llm: FakeLLMClient,
    event_bus: EventBus,
    shenlun_prompts: PromptLoader,
) -> NodeContext:
    """构造完整 NodeContext, db 字段保持 None (mock 阶段节点不调 db)"""
    return NodeContext(
        state=grading_state,
        db=None,
        event_bus=event_bus,
        llm=fake_llm,  # type: ignore[arg-type]
        prompts=shenlun_prompts,
    )


@pytest.fixture
def collected_events(event_bus: EventBus) -> list[dict[str, Any]]:
    """收集 event_bus 推送的事件 (替换 publish 为记录到 list)"""
    collected: list[dict[str, Any]] = []
    original_publish = event_bus.publish

    async def _capture(event: Any) -> None:
        collected.append(event.model_dump(mode='json'))
        await original_publish(event)

    event_bus.publish = _capture  # type: ignore[assignment]
    return collected
