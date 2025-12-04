#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio
from typing import Any

from openai import AsyncOpenAI

from backend.common.log import log
from backend.core.conf import settings


class VectorService:
    """向量化服务"""

    def __init__(self):
        """初始化向量化服务"""
        self.client = AsyncOpenAI(
            api_key=settings.OPENAI_API_KEY,
            base_url=settings.OPENAI_API_BASE,
        )
        self.model = settings.OPENAI_EMBEDDING_MODEL
        self.dimension = 1536  # text-embedding-3-small 的维度

    async def encode(self, text: str) -> list[float]:
        """
        将单个文本转换为向量

        :param text: 要向量化的文本
        :return: 1536 维的向量列表
        """
        if not text or not text.strip():
            log.warning("尝试向量化空文本，返回零向量")
            return [0.0] * self.dimension

        try:
            response = await self.client.embeddings.create(
                model=self.model,
                input=text,
            )

            # 检查响应类型，处理不同格式的 API 返回
            if isinstance(response, str):
                log.error(f"API 返回了字符串而非对象: {response[:200]}")
                raise ValueError(f"向量化 API 返回格式错误: {response[:100]}")

            # 标准 OpenAI API 响应格式
            if hasattr(response, 'data') and response.data:
                embedding = response.data[0].embedding
                log.debug(f"成功向量化文本 (长度: {len(text)}): {text[:50]}...")
                return embedding
            else:
                log.error(f"响应对象缺少 data 属性: {type(response)}")
                raise ValueError("向量化 API 返回的响应格式不正确")

        except AttributeError as e:
            log.error(f"向量化失败 - API 响应格式错误: {e}, 文本: {text[:100]}")
            log.error(f"请检查 OPENAI_API_BASE 配置是否正确: {settings.OPENAI_API_BASE}")
            raise ValueError(f"向量化服务配置错误，API 返回格式不兼容。请检查 API 端点配置。") from e
        except Exception as e:
            log.error(f"向量化失败: {e}, 文本: {text[:100]}")
            raise

    async def batch_encode(self, texts: list[str], batch_size: int = 100) -> list[list[float]]:
        """
        批量将文本转换为向量

        :param texts: 要向量化的文本列表
        :param batch_size: 每批次处理的文本数量
        :return: 向量列表
        """
        if not texts:
            return []

        # 过滤空文本
        valid_texts = [text.strip() if text else "" for text in texts]

        results = []
        total = len(valid_texts)

        for i in range(0, total, batch_size):
            batch = valid_texts[i : i + batch_size]
            try:
                response = await self.client.embeddings.create(
                    model=self.model,
                    input=batch,
                )

                batch_embeddings = [item.embedding for item in response.data]
                results.extend(batch_embeddings)

                log.info(f"批量向量化进度: {min(i + batch_size, total)}/{total}")

            except Exception as e:
                log.error(f"批量向量化失败 (批次 {i // batch_size + 1}): {e}")
                # 失败的批次使用零向量
                results.extend([[0.0] * self.dimension] * len(batch))

        return results

    async def encode_resource(self, resource_data: dict[str, Any]) -> list[float]:
        """
        将资源数据转换为向量

        :param resource_data: 资源数据字典
        :return: 向量
        """
        # 只使用核心内容字段（按优先级排序）
        text_parts = []

        # 1. 资源介绍（最重要，包含详细描述）
        resource_intro = (resource_data.get("resource_intro") or "").strip()
        if resource_intro:
            text_parts.append(resource_intro)

        # 2. 描述（次要，补充说明）
        description = (resource_data.get("description") or "").strip()
        if description:
            text_parts.append(description)

        # 组合所有文本
        combined_text = "\n".join(text_parts)

        if not combined_text:
            log.warning(f"资源 {resource_data.get('id')} 没有可向量化的文本内容")
            return [0.0] * self.dimension

        return await self.encode(combined_text)


# 全局向量服务实例
_vector_service: VectorService | None = None


def get_vector_service() -> VectorService:
    """获取向量服务单例"""
    global _vector_service
    if _vector_service is None:
        _vector_service = VectorService()
    return _vector_service
