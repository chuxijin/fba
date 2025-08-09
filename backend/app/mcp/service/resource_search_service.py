#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio
import hashlib
import json
import re
import time
from typing import Any, List

import jieba
from fastapi import Request
from mcp.server.fastmcp import FastMCP
from sqlalchemy import and_, or_, select

from backend.app.coulddrive.model.resource import Resource
 
from backend.app.mcp.schema.resource import CreateMcpSearchLogParam
from backend.app.mcp.crud.crud_search_log import mcp_search_log_dao
from backend.app.mcp.crud.crud_config import mcp_config_dao
from backend.app.coulddrive.schema.enum import DriveType
from backend.app.coulddrive.service.yp_service import get_drive_manager
from backend.app.coulddrive.schema.file import ListShareFilesParam, TransferParam, ShareParam
from backend.app.coulddrive.crud.crud_drive_account import drive_account_dao
from backend.database.db import async_db_session
from backend.database.redis import redis_client


def register_resource_search_tools(mcp: FastMCP) -> None:
    """在 FastMCP 上注册资源搜索工具（本地 DB + 缓存 + 简单权重评分）"""

    field_weights: dict[str, int] = {
        "resource_intro": 10,
        "title": 8,
        "resource_type": 6,
        "content": 5,
        "domain": 3,
        "subject": 3,
    }

    stop_words: set[str] = {
        "的",
        "了",
        "在",
        "是",
        "我",
        "有",
        "和",
        "就",
        "不",
        "人",
        "都",
        "一",
        "一个",
        "上",
        "也",
        "很",
        "到",
        "说",
        "要",
        "去",
        "你",
        "会",
        "着",
        "没有",
        "看",
        "好",
        "自己",
        "这",
        "这个",
        "那",
        "那个",
        "什么",
        "怎么",
        "为什么",
        "哪里",
        "哪个",
    }

    def tokenize(text: str) -> list[str]:
        """
        文本分词处理

        :param text: 输入文本
        :return:
        """
        if not text:
            return []

        raw = text.strip()
        # 规则短语提取：优先抽取 “有没有X资源/有没有X/找X资源/搜索X资源/关于X的资源/哪里有X资源” 中的 X
        phrase = None
        patterns = [
            r"有没有(?P<x>.+?)的?资源",
            r"找(?P<x>.+?)的?资源",
            r"搜索(?P<x>.+?)的?资源",
            r"关于(?P<x>.+?)的?资源",
            r"哪里有(?P<x>.+?)的?资源",
        ]
        for p in patterns:
            m = re.search(p, raw)
            if m and m.group("x"):
                phrase = m.group("x")
                break

        tokens = list(jieba.cut(phrase or raw))
        filtered: list[str] = []
        for token in tokens:
            token = re.sub(r"[^\w\u4e00-\u9fff]", "", token)
            if not token or token in stop_words:
                continue
            if len(token) == 1:
                if re.match(r"[A-Za-z0-9]", token):
                    filtered.append(token.lower())
            else:
                filtered.append(token.lower())
        kws = list(set(filtered))
        # 若识别到短语，且分词后被过度拆分，兜底将短语整体加入关键词，增强匹配
        if phrase:
            ph = re.sub(r"[\s\u3000]+", "", phrase).lower()
            if ph and ph not in kws:
                kws.insert(0, ph)
        return kws

    def build_cache_key(query: str, final_limit: int) -> str:
        normalized = (query or "").strip().lower()
        digest = hashlib.sha1(normalized.encode("utf-8")).hexdigest()
        return f"mcp:search:resp:{digest}:{final_limit}"

    def build_lock_key(query: str, final_limit: int) -> str:
        normalized = (query or "").strip().lower()
        digest = hashlib.md5(normalized.encode("utf-8")).hexdigest()
        return f"mcp:search:lock:{digest}:{final_limit}"

    def calc_score(resource: Resource, keywords: list[str]) -> float:
        total_score = 0.0
        max_possible = sum(field_weights.values()) * max(len(keywords), 1)
        for field, weight in field_weights.items():
            value = getattr(resource, field, "") or ""
            value_l = value.lower()
            field_hits = 0
            for kw in keywords:
                if kw in value_l:
                    field_hits += 1
            if field_hits:
                total_score += (field_hits / len(keywords)) * weight
        return round(total_score / max_possible if max_possible else 0.0, 3)

    async def _fallback_external_search(query: str, final_limit: int) -> List[dict[str, Any]]:
        """当本地无结果时回退外部搜索，返回精简结果列表"""
        import httpx
        from datetime import datetime

        url = "https://resource.yzxj.vip/api/search"
        params = {"kw": query, "cloud_types": "quark", "res": "merge", "conc": 5}
        results: list[dict[str, Any]] = []
        try:
            async with httpx.AsyncClient(timeout=8, verify=False) as client:
                resp = await client.get(url, params=params)
                if resp.status_code != 200:
                    return results
                data = resp.json()
                root = data.get("data") or data
                merged = root.get("merged_by_type") or {}
                quark_items = merged.get("quark") or []
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
                for _, note, url_val, dt_str, source in ordered_rows[: final_limit]:
                    desc = f"{dt_str} {source}".strip()
                    results.append({"remark": note, "description": desc or note, "url": url_val})
                if results:
                    return results

                items = root.get("results") or []
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
                    results.append({"remark": title, "description": desc or title, "url": picked_url})
                    if len(results) >= final_limit:
                        return results
        except Exception as e:
            print(f"[MCP] Fallback external search error: {e}")
            return []
        return results

    async def _save_quark_and_share(account_id: int, target_folder_id: str, share_url: str, ext_note: str | None = None) -> dict[str, Any] | None:
        """夸克转存并二次分享，返回新的分享链接简表"""
        try:
            async with async_db_session() as db:
                account = await drive_account_dao.get(db, account_id)
                if not account or not account.cookies or account.type != DriveType.QUARK_DRIVE.value:
                    return None
            drive_manager = get_drive_manager()
            list_params = ListShareFilesParam(
                drive_type=DriveType.QUARK_DRIVE.value,
                source_type="link",
                source_id=share_url,
                file_path="/",
            )
            files = await drive_manager.call_method(
                x_token=account.cookies,
                drive_type=DriveType.QUARK_DRIVE,
                method_name="get_share_list",
                params=list_params,
            )
            if not files:
                return None
            stoken = files[0].file_ext.get("stoken", "") if hasattr(files[0], "file_ext") else ""
            pdir_fid = files[0].file_ext.get("pdir_fid", "0") if hasattr(files[0], "file_ext") else "0"
            files_ext_info = [{"file_id": f.file_id, "file_ext": f.file_ext if hasattr(f, "file_ext") else {}} for f in files]
            file_ids = [f.file_id for f in files]
            transfer_params = TransferParam(
                drive_type=DriveType.QUARK_DRIVE.value,
                source_type="link",
                source_id=share_url,
                source_path="/",
                target_path="/",
                target_id=target_folder_id,
                file_ids=file_ids,
                ext={
                    "stoken": stoken,
                    "pdir_fid": pdir_fid,
                    "files_ext_info": files_ext_info,
                    "to_pdir_fid": target_folder_id,
                    "pdir_save_all": True,
                    "wait_for_completion": True,
                    "max_retries": 12,
                    "retry_interval": 2,
                },
            )
            ok = await drive_manager.call_method(
                x_token=account.cookies,
                drive_type=DriveType.QUARK_DRIVE,
                method_name="transfer",
                params=transfer_params,
            )
            if not ok:
                return None
            client = drive_manager._get_or_create_client(DriveType.QUARK_DRIVE, account.cookies)
            if not client:
                return None
            api = getattr(client, "_quarkapi", None)
            if not api:
                return None
            listing = await api.list_files(pdir_fid=target_folder_id, page=1, page_size=200)
            items = (listing or {}).get("data", {}).get("list", [])
            want_names = set([getattr(f, "file_name", "") for f in files])
            to_share_ids: list[str] = []
            for it in items:
                name = str(it.get("file_name", ""))
                if name and name in want_names:
                    to_share_ids.append(str(it.get("fid")))
            if not to_share_ids:
                return None
            share_params = ShareParam(
                drive_type=DriveType.QUARK_DRIVE.value,
                file_name="mcp-share",
                file_ids=to_share_ids,
                expired_type=1,
                password=None,
            )
            share_info = await drive_manager.call_method(
                x_token=account.cookies,
                drive_type=DriveType.QUARK_DRIVE,
                method_name="create_share",
                params=share_params,
            )
            if not share_info or not getattr(share_info, "url", None):
                return None
            remark = getattr(share_info, "title", "mcp-share")
            desc = ext_note or "夸克已转存并二次分享(1天有效)"
            return {"remark": remark, "description": desc, "url": share_info.url}
        except Exception:
            return None

    @mcp.tool()
    async def search_resources(query: str, limit: int = 5) -> list[dict[str, Any]]:
        """
        搜索资源库（基于 yp_resource）

        使用建议（供 LLM 调用方参考）：
        - 先从用户问题中抽取最核心的检索短语作为 query（去掉“有没有/资源/哪里有/找/搜索/关于/的”等冗词）。
        - 示例：
          * 用户问“有没有 洛洛历险记 的资源？” → query="洛洛历险记"
          * 用户问“徐涛核心考研资料” → query="徐涛 核心考研"
        - 本地有结果：仅返回本地前 N 条（受 limit 限制，不补齐）。
        - 本地无结果：仅当配置齐全且转存分享成功时，返回最新的一条分享，否则返回空。

        :param query: 核心检索短语（后端会做分词与去噪，且包含规则短语兜底）
        :param limit: 返回条数（默认 5, 1-50）
        :return:
        """
        start = time.time()
        limit = max(1, min(50, int(limit)))
        normalized_query = re.sub(r"[\s\u3000]+", "", (query or ""))[:200]
        keywords = tokenize(normalized_query)
        if not keywords:
            return []

        cache_key = build_cache_key(normalized_query, limit)
        lock_key = build_lock_key(normalized_query, limit)

        try:
            cached = await redis_client.get(cache_key)
            if cached:
                rows = json.loads(cached)
                return rows
        except Exception:
            pass

        acquired_lock = False
        try:
            acquired_lock = await redis_client.set(lock_key, "1", nx=True, ex=5)
        except Exception:
            acquired_lock = False

        if not acquired_lock:
            for _ in range(50):
                try:
                    cached = await redis_client.get(cache_key)
                    if cached:
                        return json.loads(cached)
                except Exception:
                    break
                await asyncio.sleep(0.1)

        # 读取动态配置
        drive_account_id = None
        target_folder_id = None
        try:
            async with async_db_session() as db_cfg:
                cfg = await mcp_config_dao.get_by_mcp(db_cfg, "resource")
                if cfg and isinstance(cfg.config, dict):
                    drive_account_id = cfg.config.get("drive_account_id")
                    target_folder_id = cfg.config.get("target_folder_id")
        except Exception:
            pass

        async with async_db_session() as db:
            conditions: list[Any] = [Resource.status == 1, Resource.is_deleted == False]  # noqa: E712
            per_kw_conditions: list[Any] = []
            for kw in keywords:
                c: list[Any] = []
                for field in field_weights.keys():
                    c.append(getattr(Resource, field).like(f"%{kw}%"))
                per_kw_conditions.append(or_(*c))

            if per_kw_conditions:
                where_all = and_(*conditions, and_(*per_kw_conditions))
            else:
                where_all = and_(*conditions)

            stmt = (
                select(Resource)
                .where(where_all)
                .order_by(Resource.view_count.desc(), Resource.created_time.desc())
                .limit(100)
            )
            result = await db.execute(stmt)
            resources = result.scalars().all()

            scored: list[tuple[float, dict[str, Any]]] = []
            for r in resources:
                score = calc_score(r, keywords)
                item = {
                    "remark": r.remark or "无备注",
                    "description": r.description or "无描述",
                    "url": r.url,
                }
                scored.append((score, item))
            scored.sort(key=lambda x: x[0], reverse=True)
            top_rows = [item for _, item in scored[:limit]]

            # 本地为空：仅在配置齐全且成功“转存分享”时，返回最新一条分享；否则不返回外部结果
            if not top_rows:
                ext_rows = await _fallback_external_search(normalized_query, limit)
                if ext_rows and drive_account_id and target_folder_id:
                    first = ext_rows[0]
                    saved = await _save_quark_and_share(
                        account_id=int(drive_account_id),
                        target_folder_id=str(target_folder_id),
                        share_url=first["url"],
                        ext_note=first["remark"],
                    )
                    top_rows = [saved] if saved else []
                else:
                    top_rows = []

        try:
            if resources:
                await redis_client.set(cache_key, json.dumps(top_rows, ensure_ascii=False), ex=60)
        except Exception:
            pass
        finally:
            if acquired_lock:
                try:
                    await redis_client.delete(lock_key)
                except Exception:
                    pass

        # 记录搜索日志
        try:
            response_ms = int((time.time() - start) * 1000)
            client_ip = None
            user_agent = None
            # 这里没有 FastAPI 的 Request 对象，日志仅记录基础字段
            log_param = CreateMcpSearchLogParam(
                query=query,
                result_count=len(top_rows),
                response_time=response_ms,
                client_ip=client_ip,
                user_agent=user_agent,
            )
            async with async_db_session() as db:
                await mcp_search_log_dao.create(db, log_param)
        except Exception as e:
            print(f"[MCP] write search log failed: {e}")

        print(
            "[MCP] search_resources query='{}' keywords={} cost={}ms return={}",
            normalized_query,
            keywords,
            int((time.time() - start) * 1000),
            len(top_rows),
        )
        return top_rows


