#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试 MCP 搜索接口（本地/远程均可）
"""
import asyncio
import json
import argparse
from urllib.parse import urlsplit
import httpx


class MCPTester:
    """MCP 接口测试器"""

    def __init__(self, base_url: str = "http://127.0.0.1:8000/api/v1/mcp", api_key: str = "mcp_search_2025"):
        """
        初始化测试器

        :param base_url: 搜索接口基础地址（例如 http://127.0.0.1:8000/api/v1/mcp）
        :param api_key: API 密钥
        :return:
        """
        # 统一为以 / 结尾，避免 307 重定向
        self.base_url = base_url.rstrip("/") + "/"
        self.api_key = api_key
        # 搜索接口即为 base_url 本身（POST /api/v1/mcp）
        self.endpoint = self.base_url

    async def test_search_stream(self, query: str = "徐涛", limit: int = 10, timeout: float = 30.0) -> None:
        """
        测试 SSE 流式搜索接口

        :param query: 搜索关键词
        :param limit: 返回条数上限
        :param timeout: 超时时间（秒）
        :return:
        """
        print("🔍 开始测试 MCP 搜索接口...")
        print(f"📍 接口地址: {self.endpoint}")
        print(f"🔑 API 密钥: {self.api_key}")
        print(f"💬 搜索关键词: {query}")
        print("-" * 50)

        search_params = {"query": query, "limit": limit}
        headers = {
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
            "Cache-Control": "no-cache",
        }

        try:
            async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
                print(f"📡 发送请求到: {self.endpoint}?key={self.api_key}")
                print(f"📝 请求参数: {json.dumps(search_params, ensure_ascii=False, indent=2)}")
                print("-" * 50)

                async with client.stream(
                    "POST",
                    self.endpoint,
                    params={"key": self.api_key},
                    json=search_params,
                    headers=headers,
                ) as response:
                    print(f"✅ 响应状态码: {response.status_code}")
                    print(f"📋 响应头: {dict(response.headers)}")
                    print("-" * 50)

                    if response.status_code != 200:
                        error_text = await response.aread()
                        print(f"❌ 请求失败: {error_text.decode()}")
                        return

                    event_count = 0
                    result_count = 0

                    async for line in response.aiter_lines():
                        if not line:
                            continue
                        if line.startswith("data: "):
                            event_count += 1
                            data_content = line[6:]
                            if data_content.startswith("data: "):
                                data_content = data_content[6:]

                            # 打印原始数据片段
                            print(f"📨 SSE 数据: {data_content}")
                            if not data_content.strip():
                                continue

                            try:
                                event_data = json.loads(data_content)
                            except json.JSONDecodeError as e:
                                print(f"⚠️ JSON 解析失败: {e}")
                                print(f"📄 原始数据: {data_content}")
                                continue

                            et = event_data.get("type", "unknown")
                            if et == "start":
                                print(f"🚀 搜索开始: {event_data.get('message', '')}")
                            elif et == "stats":
                                print(f"📊 搜索统计: {json.dumps(event_data, ensure_ascii=False, indent=2)}")
                            elif et == "result":
                                result_count += 1
                                result_data = event_data.get("data", {})
                                print(f"🎯 结果 #{result_count}:")
                                print(f"   📝 备注: {result_data.get('remark', 'N/A')}")
                                print(f"   📄 描述: {result_data.get('description', 'N/A')}")
                                print(f"   🔗 链接: {result_data.get('url', 'N/A')}")
                                print()
                            elif et == "complete":
                                print(f"✅ 搜索完成: {event_data.get('message', '')}")
                                stats = event_data.get("stats", {})
                                print("📈 最终统计:")
                                print(f"   🔢 总结果数: {stats.get('total', 0)}")
                                print(f"   ⏱️ 响应时间: {stats.get('response_time', 0)}ms")
                                print(f"   🔤 关键词: {stats.get('keywords', [])}")
                            elif et == "error":
                                print(f"❌ 搜索错误: {event_data.get('message', '')}")
                                detail = event_data.get('detail')
                                if detail:
                                    print(f"🔍 错误详情: {detail}")
                            else:
                                print(f"❓ 未知事件类型: {et}")
                                print(f"📄 事件数据: {json.dumps(event_data, ensure_ascii=False, indent=2)}")

                            print("-" * 30)

                    print("🏁 测试完成!")
                    print(f"📊 总事件数: {event_count}")
                    print(f"🎯 结果数量: {result_count}")

        except httpx.TimeoutException:
            print("⏰ 请求超时，请检查服务器是否正常运行")
        except httpx.ConnectError:
            print("🔌 连接失败，请检查服务器地址和端口")
        except Exception as e:
            print(f"💥 测试失败: {str(e)}")
            import traceback
            traceback.print_exc()

    async def test_ping(self) -> bool:
        """
        测试服务器连通性

        :return: 
        """
        try:
            parts = urlsplit(self.base_url)
            origin = f"{parts.scheme}://{parts.netloc}"
            docs_url = origin + "/docs"
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(docs_url)
                return resp.status_code == 200
        except Exception:
            return False


async def main() -> None:
    """命令行入口"""
    parser = argparse.ArgumentParser(description="MCP 本地/远程搜索接口测试")
    parser.add_argument("--base-url", type=str, default="http://127.0.0.1:8000/api/v1/mcp", help="接口基础地址")
    parser.add_argument("--key", type=str, default="mcp_search_2025", help="API 密钥")
    parser.add_argument("--query", type=str, default=None, help="搜索关键词（不填则运行时交互输入）")
    parser.add_argument("--limit", type=int, default=10, help="返回数量上限")
    parser.add_argument("--timeout", type=float, default=30.0, help="超时时间（秒）")
    args = parser.parse_args()

    print("🧪 MCP 接口测试工具")
    print("=" * 50)

    tester = MCPTester(base_url=args.base_url, api_key=args.key)

    print("🔍 检查服务器连通性...")
    if await tester.test_ping():
        print("✅ 服务器连通正常")
    else:
        print("❌ 服务器连接失败，继续尝试直接请求接口（可能 docs 被关闭）")

    print()
    # 交互式输入搜索词
    default_query = args.query or "徐涛"
    try:
        user_query = input(f"请输入搜索关键词(回车使用默认: {default_query}): ").strip()
    except Exception:
        user_query = ""
    final_query = user_query or default_query

    await tester.test_search_stream(query=final_query, limit=args.limit, timeout=args.timeout)


if __name__ == "__main__":
    asyncio.run(main())