#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json
import asyncio
from typing import AsyncGenerator

from fastapi import APIRouter, Request, Query, HTTPException
from sse_starlette import EventSourceResponse

from backend.plugin.mcp_service.schema.mcp_resource import McpSearchParam
from backend.plugin.mcp_service.service.mcp_service import McpService

router = APIRouter()

# 创建服务实例
mcp_service = McpService()

# 验证密钥（建议从配置文件或环境变量读取）
VALID_API_KEY = "mcp_search_2025"


def verify_api_key(key: str | None) -> bool:
    """
    验证API密钥
    
    :param key: 传入的密钥
    :return: 验证结果
    """
    return key == VALID_API_KEY


async def search_stream_generator(search_params: McpSearchParam, request: Request) -> AsyncGenerator[str, None]:
    """
    SSE搜索结果流式生成器
    """
    try:
        # 发送开始事件
        yield json.dumps({'type': 'start', 'message': '开始搜索...'}, ensure_ascii=False)
        
        # 执行搜索
        result = await mcp_service.search_resources(search_params, request)
        
        # 发送搜索统计信息
        yield json.dumps({
            'type': 'stats', 
            'total': result.total, 
            'response_time': result.response_time, 
            'keywords': result.keywords
        }, ensure_ascii=False)
        
        # 逐个发送搜索结果
        for i, search_result in enumerate(result.results):
            await asyncio.sleep(0.1)  # 模拟流式传输延迟
            yield json.dumps({
                'type': 'result', 
                'index': i, 
                'data': search_result.model_dump()
            }, ensure_ascii=False)
        
        # 发送完成事件
        yield json.dumps({'type': 'complete', 'message': '搜索完成'}, ensure_ascii=False)
        
    except Exception as e:
        # 发送错误事件
        yield json.dumps({'type': 'error', 'message': str(e)}, ensure_ascii=False)


@router.post(
    '',
    summary='搜索资源'
)
async def search_resources(
    search_params: McpSearchParam,
    request: Request,
    key: str = Query(..., description="API访问密钥")
):
    """
    SSE流式搜索yp_resource表中的资源
    
    需要提供有效的API密钥才能访问
    
    返回Server-Sent Events格式的流式数据：
    - start: 搜索开始
    - stats: 搜索统计信息  
    - result: 单个搜索结果
    - complete: 搜索完成
    - error: 错误信息
    
    每个结果包含: remark、description和url
    
    支持以下字段的智能搜索：
    - 主要名字（权重最高：10）
    - 标题（权重：8）
    - 领域、科目（权重：6）
    - 资源类型（权重：5）
    - 描述、资源介绍（权重：4）
    - 内容（权重：3）
    - 备注（权重最低：2）
    
    使用中文分词 + 权重评分算法，按浏览量和创建时间排序
    """
    # 验证API密钥
    if not verify_api_key(key):
        raise HTTPException(
            status_code=401,
            detail="无效的API密钥，请提供正确的key参数"
        )
    
    return EventSourceResponse(
        search_stream_generator(search_params, request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "*"
        }
    ) 