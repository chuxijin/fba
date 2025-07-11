#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import time
import re
from typing import List
from datetime import datetime

import jieba
from sqlalchemy import and_, or_, select
from fastapi import Request

from backend.database.db import async_db_session
from backend.app.coulddrive.model.resource import Resource
from backend.plugin.mcp_service.crud.crud_mcp_search_log import mcp_search_log_dao
from backend.plugin.mcp_service.schema.mcp_resource import (
    McpSearchParam,
    McpSearchResult,
    McpSearchResponse,
    CreateMcpSearchLogParam
)


class McpService:
    """MCP服务业务逻辑类"""

    def __init__(self):
        """初始化搜索引擎"""
        # 停用词列表
        self.stop_words = {
            '的', '了', '在', '是', '我', '有', '和', '就', '不', '人', '都', '一', '一个',
            '上', '也', '很', '到', '说', '要', '去', '你', '会', '着', '没有', '看', '好',
            '自己', '这', '这个', '那', '那个', '什么', '怎么', '为什么', '哪里', '哪个'
        }
        
        # 字段权重配置 - 优化后的权重设置
        self.field_weights = {
            'main_name': 10,        # 主要名字 - 最高权重
            'title': 8,             # 标题
            'remark': 7,            # 备注 - 包含重要资源标识
            'description': 6,       # 描述
            'resource_intro': 5,    # 资源介绍
            'resource_type': 4,     # 资源类型
            'content': 3,           # 内容
            'domain': 2,            # 领域 - 用户较少直接输入
            'subject': 2            # 科目 - 用户较少直接输入
        }

    def tokenize(self, text: str) -> List[str]:
        """
        文本分词处理
        
        :param text: 输入文本
        """
        if not text:
            return []
        
        # 使用jieba进行中文分词
        tokens = list(jieba.cut(text.strip()))
        
        # 过滤处理
        filtered_tokens = []
        for token in tokens:
            # 去除空白和标点符号
            token = re.sub(r'[^\w\u4e00-\u9fff]', '', token)
            # 只过滤停用词，保留有意义的单字符（特别是中文字符）
            if token and token not in self.stop_words:
                # 对于单字符，只保留中文字符和数字字母
                if len(token) == 1:
                    # 保留中文字符、数字、字母
                    if re.match(r'[\u4e00-\u9fff\w]', token):
                        filtered_tokens.append(token.lower())
                else:
                    # 多字符直接保留
                    filtered_tokens.append(token.lower())
        
        return list(set(filtered_tokens))  # 去重

    def calculate_relevance_score(self, resource: Resource, keywords: List[str]) -> float:
        """
        计算资源与关键词的相关度评分

        :param resource: 资源对象
        :param keywords: 关键词列表
        """
        total_score = 0.0
        max_possible_score = sum(self.field_weights.values()) * len(keywords)
        
        for field, weight in self.field_weights.items():
            field_value = getattr(resource, field, '') or ''
            field_value_lower = field_value.lower()
            
            # 计算该字段的匹配分数
            field_matches = 0
            for keyword in keywords:
                if keyword.lower() in field_value_lower:
                    field_matches += 1
            
            # 计算该字段的得分
            if field_matches > 0:
                field_score = (field_matches / len(keywords)) * weight
                total_score += field_score
        
        # 归一化评分到0-1之间
        if max_possible_score > 0:
            normalized_score = total_score / max_possible_score
        else:
            normalized_score = 0.0
        
        return round(normalized_score, 3)

    async def search_resources(
        self, 
        search_params: McpSearchParam, 
        request: Request
    ) -> McpSearchResponse:
        """
        搜索资源 - 核心功能

        :param search_params: 搜索参数
        :param request: FastAPI请求对象
        """
        start_time = time.time()
        
        # 分词处理
        keywords = self.tokenize(search_params.query)
        
        if not keywords:
            # 如果没有有效关键词，返回空结果
            return McpSearchResponse(
                query=search_params.query,
                total=0,
                results=[],
                response_time=int((time.time() - start_time) * 1000),
                keywords=[]
            )
        
        async with async_db_session() as db:
            # 构建搜索条件
            search_conditions = []
            
            # 基础过滤条件
            base_conditions = [
                Resource.status == 1,  # 正常状态
                Resource.is_deleted == False  # 未删除
            ]
            
            # 为每个关键词构建搜索条件
            for keyword in keywords:
                keyword_conditions = []
                for field in self.field_weights.keys():
                    field_attr = getattr(Resource, field)
                    if field_attr is not None:
                        keyword_conditions.append(field_attr.like(f'%{keyword}%'))
                
                if keyword_conditions:
                    search_conditions.append(or_(*keyword_conditions))
            
            # 合并所有条件
            if search_conditions:
                all_conditions = base_conditions + [or_(*search_conditions)]
            else:
                all_conditions = base_conditions
            
            # 构建查询
            stmt = (
                select(Resource)
                .where(and_(*all_conditions))
                .order_by(
                    Resource.view_count.desc(),  # 按浏览量排序
                    Resource.created_time.desc()  # 按创建时间排序
                )
                .limit(search_params.limit)
            )
            
            result = await db.execute(stmt)
            resources = result.scalars().all()
            
            # 计算相关度评分并转换为搜索结果
            scored_results = []
            for resource in resources:
                # 计算相关度评分
                relevance_score = self.calculate_relevance_score(resource, keywords)
                
                # 构建搜索结果 - 返回remark、description和url
                result = McpSearchResult(
                    remark=resource.remark or "无备注",
                    description=resource.description or "无描述",
                    url=resource.url
                )
                scored_results.append(result)
            
            # 按相关度评分排序
            # 由于简化了结果结构，我们在数据库层面已经排序了
            
            # 计算响应时间
            response_time = int((time.time() - start_time) * 1000)
            
            # 记录搜索日志 - 自动触发
            try:
                client_ip = request.client.host if request and request.client else None
                user_agent = request.headers.get('user-agent') if request else None
                
                log_param = CreateMcpSearchLogParam(
                    query=search_params.query,
                    result_count=len(scored_results),
                    response_time=response_time,
                    client_ip=client_ip,
                    user_agent=user_agent
                )
                await mcp_search_log_dao.create(db, log_param)
            except Exception as e:
                # 日志记录失败不影响搜索结果返回
                print(f"搜索日志记录失败: {e}")
            
            # 构建响应
            response = McpSearchResponse(
                query=search_params.query,
                total=len(scored_results),
                results=scored_results,
                response_time=response_time,
                keywords=keywords
            )
            
            return response 