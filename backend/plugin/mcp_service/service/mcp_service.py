#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import time
import re
import json
import hashlib
from typing import List
from datetime import datetime
import asyncio
import httpx

import jieba
from sqlalchemy import and_, or_, select
from fastapi import Request

from backend.database.db import async_db_session
from backend.database.redis import redis_client
from backend.app.coulddrive.model.resource import Resource
from backend.plugin.mcp_service.crud.crud_mcp_search_log import mcp_search_log_dao
from backend.plugin.mcp_service.crud.crud_mcp_config import mcp_config_dao
from backend.common.exception import errors
from backend.app.coulddrive.crud.crud_drive_account import drive_account_dao
from backend.app.coulddrive.schema.enum import DriveType
from backend.app.coulddrive.schema.file import ListShareFilesParam, TransferParam, ShareParam
from backend.app.coulddrive.service.yp_service import get_drive_manager
from backend.plugin.mcp_service.schema.mcp_resource import (
    McpSearchParam,
    McpSearchResult,
    McpSearchResponse,
    CreateMcpSearchLogParam
)
from backend.common.log import log


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
        
        # 字段权重配置 - 按需精简并重排权重
        self.field_weights = {
            'resource_intro': 10,   # 资源介绍 - 最重要
            'title': 8,             # 标题
            'resource_type': 6,     # 资源类型
            'content': 5,           # 内容
            'domain': 3,            # 领域
            'subject': 3            # 科目
        }

        # 运行参数
        self.max_query_length: int = 200
        self.max_keywords: int = 8
        self.final_limit: int = 5
        self.candidate_limit: int = 100
        self.cache_ttl_seconds: int = 60
        self.lock_ttl_seconds: int = 5
        self.drive_account_id: int | None = None
        self.target_folder_id: str | None = None

    def _build_cache_key(self, query: str, final_limit: int) -> str:
        """
        生成缓存 key

        :param query: 原始查询字符串
        :param final_limit: 返回条数
        :return:
        """
        normalized = (query or '').strip().lower()
        digest = hashlib.sha1(normalized.encode('utf-8')).hexdigest()
        return f"mcp:search:resp:{digest}:{final_limit}"

    def _build_lock_key(self, query: str, final_limit: int) -> str:
        """生成并发锁 key"""
        normalized = (query or '').strip().lower()
        digest = hashlib.md5(normalized.encode('utf-8')).hexdigest()
        return f"mcp:search:lock:{digest}:{final_limit}"

    async def _save_quark_and_share(
        self,
        account_id: int,
        target_folder_id: str,
        share_url: str,
        ext_note: str | None = None,
    ) -> McpSearchResult | None:
        """
        夸克网盘：将分享链接内容保存到指定目录并创建新的分享

        :param account_id: 网盘账户 ID（`yp_user.id`）
        :param target_folder_id: 目标目录的 fid
        :param share_url: 夸克分享链接（可带密码 | 分隔）
        :return:
        """
        try:
            async with async_db_session() as db:
                account = await drive_account_dao.get(db, account_id)
                if not account or not account.cookies or account.type != DriveType.QUARK_DRIVE.value:
                    return None

            drive_manager = get_drive_manager()

            # 列出分享根目录，提取必要的 stoken/父目录 token 等
            list_params = ListShareFilesParam(
                drive_type=DriveType.QUARK_DRIVE.value,
                source_type='link',
                source_id=share_url,
                file_path='/'
            )
            files = await drive_manager.call_method(
                x_token=account.cookies,
                drive_type=DriveType.QUARK_DRIVE,
                method_name='get_share_list',
                params=list_params,
            )
            if not files:
                return None

            # 构造转存所需扩展参数（不额外创建文件夹，保持原结构）
            stoken = files[0].file_ext.get('stoken', '') if hasattr(files[0], 'file_ext') else ''
            pdir_fid = files[0].file_ext.get('pdir_fid', '0') if hasattr(files[0], 'file_ext') else '0'
            files_ext_info = [
                {
                    'file_id': f.file_id,
                    'file_ext': f.file_ext if hasattr(f, 'file_ext') else {}
                } for f in files
            ]
            file_ids = [f.file_id for f in files]

            transfer_params = TransferParam(
                drive_type=DriveType.QUARK_DRIVE.value,
                source_type='link',
                source_id=share_url,
                source_path='/',
                target_path='/',
                target_id=target_folder_id,
                file_ids=file_ids,
                ext={
                    'stoken': stoken,
                    'pdir_fid': pdir_fid,
                    'files_ext_info': files_ext_info,
                    'to_pdir_fid': target_folder_id,
                    'pdir_save_all': True,
                    'wait_for_completion': True,
                    'max_retries': 12,
                    'retry_interval': 2,
                }
            )

            ok = await drive_manager.call_method(
                x_token=account.cookies,
                drive_type=DriveType.QUARK_DRIVE,
                method_name='transfer',
                params=transfer_params,
            )
            if not ok:
                return None

            # 直接使用 API 层列目录，定位刚保存的文件/目录 fid 列表
            client = drive_manager._get_or_create_client(DriveType.QUARK_DRIVE, account.cookies)
            if not client:
                return None
            api = getattr(client, '_quarkapi', None)
            if not api:
                return None
            listing = await api.list_files(pdir_fid=target_folder_id, page=1, page_size=200)
            items = (listing or {}).get('data', {}).get('list', [])
            # 依据名称匹配刚保存的顶层项目
            want_names = set([getattr(f, 'file_name', '') for f in files])
            to_share_ids: list[str] = []
            for it in items:
                name = str(it.get('file_name', ''))
                if name and name in want_names:
                    to_share_ids.append(str(it.get('fid')))
            if not to_share_ids:
                return None

            # 创建 1 天有效期的分享（不设置密码）
            share_params = ShareParam(
                drive_type=DriveType.QUARK_DRIVE.value,
                file_name='mcp-share',
                file_ids=to_share_ids,
                expired_type=1,
                password=None,
            )
            share_info = await drive_manager.call_method(
                x_token=account.cookies,
                drive_type=DriveType.QUARK_DRIVE,
                method_name='create_share',
                params=share_params,
            )
            if not share_info or not getattr(share_info, 'url', None):
                return None

            # 返回新的分享链接
            remark = getattr(share_info, 'title', 'mcp-share')
            desc = ext_note or "夸克已转存并二次分享(1天有效)"
            return McpSearchResult(remark=remark, description=desc, url=share_info.url)
        except Exception:
            return None

    async def _fallback_external_search(self, query: str) -> List[McpSearchResult]:
        """
        当本地无结果时，调用外部搜索接口进行回退检索

        :param query: 搜索关键词（已按长度截断）
        :return:
        """
        url = "https://resource.yzxj.vip/api/search"
        params = {
            "kw": query,           # 使用用户原始输入
            "cloud_types": "quark",
            "res": "merge",
            "conc": 5,
        }

        results: List[McpSearchResult] = []
        try:
            log.info(f"[MCP] Fallback external search -> url={url} params={params}")
            async with httpx.AsyncClient(timeout=8, verify=False) as client:
                resp = await client.get(url, params=params)
                log.info(f"[MCP] Fallback external search status={resp.status_code}")
                if resp.status_code != 200:
                    return results

                data = resp.json()
                root = data.get("data") or data  # 兼容 {code,message,data} 包裹

                # 优先从 merged_by_type.quark 读取
                merged = root.get("merged_by_type") or {}
                quark_items = merged.get("quark") or []
                log.info(f"[MCP] Fallback merged.quark count={len(quark_items)}")
                # 先收集并按 datetime 降序排序
                ordered_rows: list[tuple[datetime | None, str, str, str, str]] = []
                for item in quark_items:
                    url_val = item.get("url")
                    if not url_val:
                        continue
                    note = item.get("note") or "外部搜索结果"
                    dt_str = item.get("datetime") or ""
                    source = item.get("source") or ""
                    try:
                        dt_parsed = datetime.fromisoformat(dt_str.replace("Z", "+00:00")) if dt_str else None
                    except Exception:
                        dt_parsed = None
                    ordered_rows.append((dt_parsed, note, url_val, dt_str, source))
                ordered_rows.sort(key=lambda x: (x[0] is not None, x[0]), reverse=True)
                for _, note, url_val, dt_str, source in ordered_rows[: self.final_limit]:
                    desc = f"{dt_str} {source}".strip()
                    results.append(McpSearchResult(remark=note, description=desc or note, url=url_val))
                if results:
                    return results

                # 其次回退到 results 链接
                if not results:
                    items = root.get("results") or []
                    log.info(f"[MCP] Fallback results count={len(items)} (raw)")
                    for item in items:
                        links = item.get("links") or []
                        picked_url = None
                        for link in links:
                            if link.get("type") == "quark" and link.get("url"):
                                picked_url = link["url"]
                                break
                        if not picked_url and links:
                            picked_url = links[0].get("url")
                        if not picked_url:
                            continue
                        title = item.get("title") or "外部搜索结果"
                        dt = item.get("datetime") or ""
                        channel = item.get("channel") or ""
                        desc = f"{dt} {channel}".strip()
                        results.append(McpSearchResult(remark=title, description=desc or title, url=picked_url))
                        if len(results) >= self.final_limit:
                            return results
        except Exception as e:
            log.info(f"[MCP] Fallback external search error: {e}")
            return []

        log.info(f"[MCP] Fallback external search return count={len(results)}")
        return results

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
                if len(token) == 1:
                    # 仅保留 ASCII 字母/数字 的单字符，丢弃单字中文（如“传/学”等高频噪声）
                    if re.match(r'[A-Za-z0-9]', token):
                        filtered_tokens.append(token.lower())
                else:
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
        
        # 读取配置覆盖默认参数
        has_config = False
        try:
            async with async_db_session() as db_cfg:
                # 读取名为 resource 的配置（JSON）
                cfg = await mcp_config_dao.get_by_mcp(db_cfg, 'resource')
                if cfg and isinstance(cfg.config, dict):
                    has_config = True
                    self.max_query_length = int(cfg.config.get('max_query_length', self.max_query_length))
                    self.max_keywords = int(cfg.config.get('max_keywords', self.max_keywords))
                    self.final_limit = int(cfg.config.get('final_limit', self.final_limit))
                    self.candidate_limit = int(cfg.config.get('candidate_limit', self.candidate_limit))
                    self.cache_ttl_seconds = int(cfg.config.get('cache_ttl_seconds', self.cache_ttl_seconds))
                    self.lock_ttl_seconds = int(cfg.config.get('lock_ttl_seconds', self.lock_ttl_seconds))
                    self.drive_account_id = cfg.config.get('drive_account_id', self.drive_account_id)
                    self.target_folder_id = cfg.config.get('target_folder_id', self.target_folder_id)
        except Exception:
            pass

        # 入参标准化：去除空格（含全角空格）后再截断
        original_query = search_params.query or ''
        normalized_query = re.sub(r'[\s\u3000]+', '', original_query)
        truncated_query = normalized_query[: self.max_query_length]

        # 分词处理并限制关键词数量
        keywords = self.tokenize(truncated_query)
        if len(keywords) > self.max_keywords:
            keywords = keywords[: self.max_keywords]
        
        if not keywords:
            # 如果没有有效关键词，返回空结果
            return McpSearchResponse(
                query=search_params.query,
                total=0,
                results=[],
                response_time=int((time.time() - start_time) * 1000),
                keywords=[]
            )
        
        # 缓存与并发保护
        cache_key = self._build_cache_key(normalized_query, self.final_limit)
        lock_key = self._build_lock_key(normalized_query, self.final_limit)

        # 命中缓存直接返回
        try:
            cached = await redis_client.get(cache_key)
            if cached:
                data = json.loads(cached)
                response = McpSearchResponse(**data)
                response.response_time = int((time.time() - start_time) * 1000)
                log.info(f"[MCP] Cache hit for query='{normalized_query}' (original='{original_query}')")
                return response
        except Exception:
            # 缓存异常不影响主流程
            pass

        # 获取并发锁；失败则短暂轮询等待缓存出现
        acquired_lock = False
        try:
            acquired_lock = await redis_client.set(lock_key, '1', nx=True, ex=self.lock_ttl_seconds)
        except Exception:
            acquired_lock = False

        if not acquired_lock:
            # 等待已有请求写入缓存
            for _ in range(50):  # ~5s
                try:
                    cached = await redis_client.get(cache_key)
                    if cached:
                        data = json.loads(cached)
                        response = McpSearchResponse(**data)
                        response.response_time = int((time.time() - start_time) * 1000)
                        return response
                except Exception:
                    break
                await asyncio.sleep(0.1)
        
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
            
            # 合并所有关键词条件：要求每个关键词至少命中一个字段
            if search_conditions:
                all_conditions = base_conditions + [and_(*search_conditions)]
            else:
                all_conditions = base_conditions
            
            # 构建查询（扩大候选集，后续在代码内重排取 TopN 再取 Top5）
            stmt = (
                select(Resource)
                .where(and_(*all_conditions))
                .order_by(
                    Resource.view_count.desc(),  # 按浏览量排序
                    Resource.created_time.desc()  # 按创建时间排序
                )
                .limit(self.candidate_limit)
            )
            
            result = await db.execute(stmt)
            resources = result.scalars().all()
            
            # 计算相关度评分并按分数降序重排，最终仅返回Top5
            scored_items = []
            for resource in resources:
                relevance_score = self.calculate_relevance_score(resource, keywords)
                item = McpSearchResult(
                    remark=resource.remark or "无备注",
                    description=resource.description or "无描述",
                    url=resource.url
                )
                scored_items.append((relevance_score, item))

            scored_items.sort(key=lambda x: x[0], reverse=True)
            top_results = [item for _, item in scored_items[: self.final_limit]]
            
            # 若本地无结果：已配置时回退外部查询；未配置则提示
            if not top_results:
                log.info(f"[MCP] Local search empty. has_config={has_config}, query='{normalized_query}', keywords={keywords}")
                if not has_config:
                    raise errors.RequestError(msg='请配置 mcp: resource')
                external_results = await self._fallback_external_search(normalized_query)
                log.info(f"[MCP] External results count={len(external_results)}")
                # 强制转存：仅当配置了账号与目录且转存成功时才返回新分享
                if external_results and self.drive_account_id and self.target_folder_id:
                    # 直接选择按时间已排序后的第一条
                    first_ext = external_results[0]
                    saved = await self._save_quark_and_share(
                        account_id=self.drive_account_id,
                        target_folder_id=self.target_folder_id,
                        share_url=first_ext.url,
                        ext_note=first_ext.remark,
                    )
                    top_results = [saved] if saved else []
                else:
                    top_results = []
            
            # 计算响应时间
            response_time = int((time.time() - start_time) * 1000)
            
            # 记录搜索日志 - 自动触发
            try:
                client_ip = request.client.host if request and request.client else None
                user_agent = request.headers.get('user-agent') if request else None
                
                log_param = CreateMcpSearchLogParam(
                    query=search_params.query,
                    result_count=len(top_results),
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
                total=len(top_results),
                results=top_results,
                response_time=response_time,
                keywords=keywords
            )
            
            # 写入缓存（仅缓存本地结果；外部结果不缓存）
            try:
                if resources:
                    await redis_client.set(
                        cache_key, json.dumps(response.model_dump(), ensure_ascii=False), ex=self.cache_ttl_seconds
                    )
            except Exception:
                pass

            # 释放并发锁
            if acquired_lock:
                try:
                    await redis_client.delete(lock_key)
                except Exception:
                    pass
            
            return response 