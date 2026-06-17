#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import asyncio
import json
import re
import time

from typing import Any, TypeVar

import httpx
from pydantic import BaseModel, Field
from pydantic_ai import Agent
from pydantic_ai.settings import ModelSettings
from sqlalchemy.ext.asyncio import AsyncSession

from backend.common.exception import errors
from backend.common.log import log
from backend.database.db import async_db_session
from backend.plugin.agents.service.common.llm.roles import NodeRole
from backend.plugin.ai.crud.crud_model import ai_model_dao
from backend.plugin.ai.crud.crud_provider import ai_provider_dao
from backend.plugin.ai.schema.chat import AIChat, AIChatMessage
from backend.plugin.ai.service.chat_service import ai_chat_service
from backend.plugin.ai.utils.model_control import get_pydantic_model

T = TypeVar('T', bound=BaseModel)

_NETWORK_ERRORS = (
    httpx.TimeoutException,
    httpx.ConnectError,
    httpx.RemoteProtocolError,
    ConnectionError,
    TimeoutError,
)

_MAX_RETRIES = 3
_RETRY_BASE_DELAY = 2.0


class LLMCallStats(BaseModel):
    """LLM 调用统计"""

    model: str = Field(description='调用的模型 ID')
    tokens_in: int = Field(default=0, description='输入 token')
    tokens_out: int = Field(default=0, description='输出 token')
    duration_ms: int = Field(default=0, description='耗时毫秒')


class LLMClient:
    """LLM 客户端"""

    def __init__(
        self,
        *,
        provider_id: int,
        primary_model_id: str,
        mini_model_id: str | None = None,
    ) -> None:
        self.provider_id = provider_id
        self.primary_model_id = primary_model_id
        self.mini_model_id = mini_model_id or primary_model_id

    @staticmethod
    async def _call_with_retry(
        func: Any,
        *args: Any,
        max_retries: int = _MAX_RETRIES,
        **kwargs: Any,
    ) -> Any:
        """
        带指数退避的网络重试包装

        :param func: 要执行的异步函数
        :param max_retries: 最大重试次数
        :return:
        """
        last_error: Exception | None = None
        for attempt in range(max_retries):
            try:
                return await func(*args, **kwargs)
            except _NETWORK_ERRORS as exc:
                last_error = exc
                if attempt < max_retries - 1:
                    delay = _RETRY_BASE_DELAY * (2**attempt)
                    log.warning(f'LLM 网络异常 (attempt {attempt + 1}/{max_retries}), {delay}s 后重试: {exc!s}')
                    await asyncio.sleep(delay)
        raise last_error  # type: ignore[misc]

    def resolve_model(self, role: NodeRole) -> str:
        """
        根据角色解析实际模型 ID

        :param role: 节点角色
        :return:
        """
        if role == NodeRole.mini:
            return self.mini_model_id
        return self.primary_model_id

    async def invoke_structured(
        self,
        db: AsyncSession | None,
        *,
        role: NodeRole,
        system_prompt: str,
        user_prompt: str,
        output_type: type[T],
        temperature: float = 0.2,
        max_tokens: int = 4000,
        timeout: float = 300,
        output_retries: int = 2,
    ) -> tuple[T, LLMCallStats]:
        """
        调用 Pydantic AI Agent 返回强类型 Pydantic 对象, 校验失败自动重试

        :param db: 已忽略, LLM client 内部开独立 session
        :param role: 节点角色
        :param system_prompt: 系统提示词
        :param user_prompt: 用户提示词
        :param output_type: Pydantic BaseModel 子类
        :param temperature: 温度
        :param max_tokens: 最大输出 token
        :param timeout: 超时秒
        :param output_retries: 输出校验失败时的重试次数
        :return:
        """
        _ = db
        model_id = self.resolve_model(role)

        async with async_db_session() as own_db:
            provider = await ai_provider_dao.get(own_db, self.provider_id)
            if not provider or not provider.status:
                raise errors.NotFoundError(msg='AI 供应商不存在或已停用')
            model_record = await ai_model_dao.get_by_model_and_provider(own_db, model_id, self.provider_id)
            if not model_record or not model_record.status:
                raise errors.NotFoundError(msg=f'AI 模型 {model_id} 不存在或已停用')

        pydantic_model = get_pydantic_model(
            provider_type=provider.type,
            model_name=model_id,
            api_key=provider.api_key,
            base_url=provider.api_host,
            model_settings=ModelSettings(
                temperature=temperature,
                max_tokens=max_tokens,
                timeout=timeout,
            ),
        )

        agent: Agent[None, T] = Agent(
            model=pydantic_model,
            output_type=output_type,
            output_retries=output_retries,
            system_prompt=system_prompt,
        )

        started = time.perf_counter()
        try:
            result = await self._call_with_retry(agent.run, user_prompt)
        except _NETWORK_ERRORS as e:
            raise errors.GatewayError(msg=f'LLM 网络异常 ({output_type.__name__}), 请稍后重试: {e!s}') from e
        except Exception as e:
            raise errors.ServerError(msg=f'LLM 调用失败 ({output_type.__name__}): {e!s}') from e
        duration_ms = int((time.perf_counter() - started) * 1000)

        tokens_in, tokens_out = self._extract_usage(result)
        stats = LLMCallStats(
            model=model_id,
            tokens_in=tokens_in or self._approx_tokens(system_prompt + user_prompt),
            tokens_out=tokens_out or 0,
            duration_ms=duration_ms,
        )
        return result.output, stats

    async def invoke_json(
        self,
        db: AsyncSession | None,
        *,
        role: NodeRole,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.2,
        max_tokens: int = 4000,
        timeout: float = 120,
    ) -> tuple[dict[str, Any], LLMCallStats]:
        """
        旧式 dict 返回 (兼容 fallback, 新节点应优先用 invoke_structured)

        :param db: 已忽略
        :param role: 节点角色
        :param system_prompt: 系统提示词
        :param user_prompt: 用户提示词
        :param temperature: 温度
        :param max_tokens: 最大输出 token
        :param timeout: 超时秒
        :return:
        """
        _ = db
        model_id = self.resolve_model(role)
        chat = AIChat(
            provider_id=self.provider_id,
            model_id=model_id,
            messages=[
                AIChatMessage(role='system', content=system_prompt),
                AIChatMessage(role='user', content=user_prompt),
            ],
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=timeout,
            extra_body={'response_format': {'type': 'json_object'}},
        )
        started = time.perf_counter()

        async def _do_json_call() -> dict[str, Any]:
            async with async_db_session() as own_db:
                return await ai_chat_service.raw_chat(db=own_db, chat=chat, stream=True)

        try:
            response = await self._call_with_retry(_do_json_call)
        except _NETWORK_ERRORS as e:
            raise errors.GatewayError(msg=f'LLM 网络异常, 请稍后重试: {e!s}') from e
        duration_ms = int((time.perf_counter() - started) * 1000)
        content = response.get('content') or '{}'
        data = self._parse_json_object(content)
        stats = LLMCallStats(
            model=model_id,
            tokens_in=self._approx_tokens(system_prompt) + self._approx_tokens(user_prompt),
            tokens_out=self._approx_tokens(content),
            duration_ms=duration_ms,
        )
        return data, stats

    async def invoke_text(
        self,
        db: AsyncSession | None,
        *,
        role: NodeRole,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.6,
        max_tokens: int = 4000,
        timeout: float = 120,
    ) -> tuple[str, LLMCallStats]:
        """
        调用 LLM 返回纯文本

        :param db: 已忽略
        :param role: 节点角色
        :param system_prompt: 系统提示词
        :param user_prompt: 用户提示词
        :param temperature: 温度
        :param max_tokens: 最大输出 token
        :param timeout: 超时秒
        :return:
        """
        _ = db
        model_id = self.resolve_model(role)
        chat = AIChat(
            provider_id=self.provider_id,
            model_id=model_id,
            messages=[
                AIChatMessage(role='system', content=system_prompt),
                AIChatMessage(role='user', content=user_prompt),
            ],
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=timeout,
        )
        started = time.perf_counter()

        async def _do_text_call() -> dict[str, Any]:
            async with async_db_session() as own_db:
                return await ai_chat_service.raw_chat(db=own_db, chat=chat, stream=True)

        try:
            response = await self._call_with_retry(_do_text_call)
        except _NETWORK_ERRORS as e:
            raise errors.GatewayError(msg=f'LLM 网络异常, 请稍后重试: {e!s}') from e
        duration_ms = int((time.perf_counter() - started) * 1000)
        text = response.get('content') or ''
        stats = LLMCallStats(
            model=model_id,
            tokens_in=self._approx_tokens(system_prompt) + self._approx_tokens(user_prompt),
            tokens_out=self._approx_tokens(text),
            duration_ms=duration_ms,
        )
        return text, stats

    @staticmethod
    def _extract_usage(result: Any) -> tuple[int, int]:
        """
        尽量从 pydantic_ai RunResult 拿 token usage, 拿不到返回 (0, 0)

        :param result: AgentRunResult
        :return:
        """
        try:
            usage = result.usage()
            tokens_in = getattr(usage, 'input_tokens', None) or getattr(usage, 'request_tokens', None) or 0
            tokens_out = getattr(usage, 'output_tokens', None) or getattr(usage, 'response_tokens', None) or 0
            return int(tokens_in), int(tokens_out)
        except Exception:
            return 0, 0

    @staticmethod
    def _parse_json_object(content: str) -> dict[str, Any]:
        """
        解析 JSON 对象, 容忍 ``` 代码块包装

        :param content: 模型输出
        :return:
        """
        text = content.strip()
        if text.startswith('```'):
            matched = re.search(r'```(?:json)?\s*(.*?)\s*```', text, re.S)
            if matched:
                text = matched.group(1)
        try:
            data = json.loads(text.strip())
        except json.JSONDecodeError as e:
            raise errors.ServerError(msg=f'LLM 返回的 JSON 解析失败: {e!s}') from e
        if not isinstance(data, dict):
            raise errors.ServerError(msg=f'LLM 返回不是 JSON 对象: {type(data).__name__}')
        return data

    @staticmethod
    def _approx_tokens(text: str) -> int:
        """
        粗略估算 token 数

        :param text: 文本
        :return:
        """
        if not text:
            return 0
        return len(text) // 3
