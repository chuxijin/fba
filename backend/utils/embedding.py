#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from openai import AsyncOpenAI

from backend.core.conf import settings

# 懒初始化客户端
_client: AsyncOpenAI | None = None


def _get_client() -> AsyncOpenAI:
    """获取 OpenAI 客户端单例"""
    global _client
    if _client is None:
        base_url = settings.OPENAI_API_BASE
        if base_url and not base_url.endswith('/v1'):
            base_url = f'{base_url}/v1'
        _client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY, base_url=base_url)
    return _client


async def embed(text: str, *, model: str | None = None) -> list[float]:
    """
    将文本转换为向量

    :param text: 要向量化的文本
    :param model: 模型名称，默认使用配置中的模型
    :return:
    """
    client = _get_client()
    model = model or settings.OPENAI_EMBEDDING_MODEL
    response = await client.embeddings.create(input=text, model=model)
    return response.data[0].embedding


async def batch_embed(texts: list[str], *, model: str | None = None, batch_size: int = 100) -> list[list[float]]:
    """
    批量将文本转换为向量

    :param texts: 要向量化的文本列表
    :param model: 模型名称，默认使用配置中的模型
    :param batch_size: 每批次处理的文本数量
    :return:
    """
    if not texts:
        return []

    client = _get_client()
    model = model or settings.OPENAI_EMBEDDING_MODEL
    results: list[list[float]] = []

    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        response = await client.embeddings.create(input=batch, model=model)
        results.extend([item.embedding for item in response.data])

    return results
