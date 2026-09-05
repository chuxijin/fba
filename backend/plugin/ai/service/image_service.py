#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import time
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.common.exception import errors
from backend.common.log import log
from backend.plugin.ai.model import AIModel, AIProvider
from backend.plugin.ai.schema.image import (
    AIImageGenerateParam,
    AIImageGenerateResult,
    AIImageItem,
)


class ImageService:
    """AI 生图服务（支持多中转站地址高可用与自动故障转移 Failover）"""

    @staticmethod
    def _normalize_image_url(api_host: str) -> str:
        """规范化中转站生图请求端点"""
        host = api_host.rstrip('/')
        if host.endswith('/v1'):
            return f'{host}/images/generations'
        return f'{host}/v1/images/generations'

    async def get_candidate_providers(
        self,
        db: AsyncSession,
        preferred_provider_id: int | None = None,
        model_id: str | None = None,
    ) -> list[AIProvider]:
        """获取真正支持生图的供应商（锁定智画创或配置了对应生图模型的专属节点）"""
        # 1. 若显式指定 provider_id，则直接使用该节点
        if preferred_provider_id:
            stmt = select(AIProvider).where(AIProvider.id == preferred_provider_id, AIProvider.status == 1)
            res = await db.execute(stmt)
            p = res.scalar_one_or_none()
            if p:
                return [p]

        # 2. 根据模型名称精准匹配配置了该模型的供应商（例如 gpt-image-2 仅智画创具备）
        if model_id:
            stmt = (
                select(AIProvider)
                .join(AIModel, AIModel.provider_id == AIProvider.id)
                .where(
                    AIProvider.status == 1,
                    AIModel.status == 1,
                    AIModel.model_id == model_id,
                )
                .order_by(AIProvider.id.desc())
            )
            res = await db.execute(stmt)
            matched = list(res.scalars().all())
            if matched:
                return matched

        # 3. 兜底：锁定智画创
        stmt = (
            select(AIProvider)
            .where(
                AIProvider.status == 1,
                (AIProvider.name.like('%智画创%') | AIProvider.api_host.like('%wisart%'))
            )
        )
        res = await db.execute(stmt)
        matched = list(res.scalars().all())
        if matched:
            return matched

        raise errors.NotFoundError(msg='未找到可用的生图供应商（智画创），请检查后台供应商配置')

    async def generate(
        self,
        *,
        db: AsyncSession,
        param: AIImageGenerateParam,
    ) -> AIImageGenerateResult:
        """
        调用大厂/中转站 API 生成图片（具备多节点自动故障转移）

        :param db: 异步数据库会话
        :param param: 生图参数
        :return: 生图结果
        """
        candidates = await self.get_candidate_providers(
            db, preferred_provider_id=param.provider_id, model_id=param.model
        )
        failures: list[dict[str, Any]] = []

        payload: dict[str, Any] = {
            'prompt': param.prompt,
            'model': param.model,
            'n': param.n,
            'size': param.size,
            'response_format': 'url',
        }
        if param.quality:
            payload['quality'] = param.quality
        if param.image_url:
            payload['image_url'] = param.image_url
            payload['image'] = param.image_url

        start_time = time.perf_counter()

        for idx, provider in enumerate(candidates, start=1):
            endpoint = self._normalize_image_url(provider.api_host)
            headers = {
                'Authorization': f'Bearer {provider.api_key}',
                'Content-Type': 'application/json',
            }

            log.info(
                f'[ImageService] 正在尝试通过中转站 [{idx}/{len(candidates)}] '
                f'{provider.name} (Host: {provider.api_host}, Model: {param.model}) 生图...'
            )

            try:
                async with httpx.AsyncClient(timeout=param.timeout) as client:
                    response = await client.post(endpoint, headers=headers, json=payload)
                    response.raise_for_status()
                    resp_json = response.json()

                    data_list = resp_json.get('data') or []
                    if not data_list:
                        raise ValueError(f'供应商返回数据格式异常，缺少 data 字段: {resp_json}')

                    items: list[AIImageItem] = []
                    for item in data_list:
                        img_url = item.get('url')
                        if not img_url and item.get('b64_json'):
                            img_url = f'data:image/png;base64,{item["b64_json"]}'
                        if img_url:
                            items.append(
                                AIImageItem(
                                    url=img_url,
                                    revised_prompt=item.get('revised_prompt'),
                                )
                            )

                    if not items:
                        raise ValueError(f'未从响应中解析到有效的图片 URL: {resp_json}')

                    elapsed = round(time.perf_counter() - start_time, 2)
                    log.info(
                        f'[ImageService] 中转站 {provider.name} 生图成功！耗时: {elapsed}s，产出 {len(items)} 张图片'
                    )

                    return AIImageGenerateResult(
                        images=items,
                        provider_id=provider.id,
                        provider_name=provider.name,
                        model=param.model,
                        elapsed_seconds=elapsed,
                    )

            except Exception as e:
                err_msg = str(e)
                log.warning(
                    f'[ImageService] 中转站 {provider.name}({provider.api_host}) 调用失败: {err_msg}。'
                    '正在自动故障转移（Failover）至下一个备选节点...'
                )
                failures.append({
                    'provider_id': provider.id,
                    'provider_name': provider.name,
                    'api_host': provider.api_host,
                    'error': err_msg,
                })

        # 若全部中转站均尝试失败
        elapsed_total = round(time.perf_counter() - start_time, 2)
        log.error(f'[ImageService] 所有候选中转站 ({len(candidates)} 个) 均生图失败，总耗时: {elapsed_total}s')
        raise errors.RequestError(
            msg=f'所有 AI 生图中转站均调用失败，已尝试 {len(candidates)} 个节点。详情: {failures}'
        )


image_service: ImageService = ImageService()