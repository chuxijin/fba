#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
import httpx
import pytest

from backend.plugin.ai.model import AIProvider
from backend.plugin.ai.schema.image import AIImageGenerateParam
from backend.plugin.ai.service.image_service import ImageService
from backend.common.exception.errors import RequestError


def create_mock_provider(pid: int, name: str, host: str, key: str = "sk-test"):
    p = MagicMock(spec=AIProvider)
    p.id = pid
    p.name = name
    p.api_host = host
    p.api_key = key
    p.status = 1
    return p


async def test_failover_mechanism():
    """测试多中转站自动故障转移（Failover）"""
    image_service = ImageService()

    provider_primary = create_mock_provider(1, "中转站A-故障节点", "https://api.hub-a.com")
    provider_backup = create_mock_provider(2, "中转站B-备用节点", "https://api.hub-b.com")

    # Mock 数据库查询返回两个供应商
    mock_db = MagicMock()
    mock_execute_res = MagicMock()
    mock_execute_res.scalars.return_value.all.return_value = [provider_primary, provider_backup]
    mock_db.execute = AsyncMock(return_value=mock_execute_res)

    # 模拟 HTTP 请求：中转站 A 报 500 内部错误，中转站 B 正常响应图片
    async def mock_post(url, headers=None, json=None, timeout=None):
        if "hub-a.com" in url:
            # 模拟节点 A 报错
            resp = MagicMock(spec=httpx.Response)
            resp.status_code = 500
            resp.raise_for_status.side_effect = httpx.HTTPStatusError(
                "Internal Server Error", request=MagicMock(), response=resp
            )
            return resp
        elif "hub-b.com" in url:
            # 模拟节点 B 成功
            resp = MagicMock(spec=httpx.Response)
            resp.status_code = 200
            resp.raise_for_status = MagicMock()
            resp.json.return_value = {
                "created": 1725330000,
                "data": [
                    {
                        "url": "https://img.cdn.com/generated-artwork.png",
                        "revised_prompt": "An artistic landscape photo"
                    }
                ]
            }
            return resp
        raise RuntimeError(f"Unexpected url: {url}")

    with patch("httpx.AsyncClient.post", side_effect=mock_post):
        param = AIImageGenerateParam(prompt="测试生图提示词", model="dall-e-3")
        res = await image_service.generate(db=mock_db, param=param)

        print("\n=== 故障转移测试结果 ===")
        print("实际生效中转站 ID:", res.provider_id)
        print("实际生效中转站名称:", res.provider_name)
        print("生成图片链接:", res.images[0].url)
        print("生图耗时:", res.elapsed_seconds, "秒")

        # 断言：中转站 A 失败后，无缝切到了备选中转站 B 出图成功
        assert res.provider_id == 2
        assert res.provider_name == "中转站B-备用节点"
        assert res.images[0].url == "https://img.cdn.com/generated-artwork.png"


async def test_all_providers_failed():
    """测试所有中转站均异常时的容灾断言"""
    image_service = ImageService()
    p1 = create_mock_provider(1, "中转站1", "https://api.node1.com")
    p2 = create_mock_provider(2, "中转站2", "https://api.node2.com")

    mock_db = MagicMock()
    mock_execute_res = MagicMock()
    mock_execute_res.scalars.return_value.all.return_value = [p1, p2]
    mock_db.execute = AsyncMock(return_value=mock_execute_res)

    async def mock_post_all_fail(url, headers=None, json=None, timeout=None):
        raise httpx.ConnectError("Connection refused by gateway")

    with patch("httpx.AsyncClient.post", side_effect=mock_post_all_fail):
        param = AIImageGenerateParam(prompt="测试", model="dall-e-3")
        try:
            await image_service.generate(db=mock_db, param=param)
            assert False, "Should have raised RequestError"
        except RequestError as e:
            print("\n全节点宕机预期报错:", e.msg)
            assert "所有 AI 生图中转站均调用失败" in e.msg


if __name__ == "__main__":
    asyncio.run(test_failover_mechanism())
    asyncio.run(test_all_providers_failed())
    print("\nALL IMAGE FAILOVER TESTS PASSED!")