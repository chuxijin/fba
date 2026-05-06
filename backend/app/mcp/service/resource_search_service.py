#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import asyncio
import hashlib
import json
import re
import time

from typing import Any, List
from urllib.parse import parse_qs, urlencode, urlparse

import jieba

from mcp.server.fastmcp import FastMCP
from sqlalchemy import and_, or_, select

from backend.app.coulddrive.crud.crud_drive_account import drive_account_dao
from backend.app.coulddrive.model.resource import Resource
from backend.app.coulddrive.schema.enum import DriveType
from backend.app.coulddrive.schema.file import ListFilesParam, ListShareFilesParam, ShareParam, TransferParam
from backend.app.coulddrive.service.coulddrive_service import CouldDriveService
from backend.app.mcp.crud.crud_config import mcp_config_dao
from backend.app.mcp.crud.crud_search_log import mcp_search_log_dao
from backend.app.mcp.schema.resource import CreateMcpSearchLogParam
from backend.app.mcp.service.drive_constants import ALLOWED_PROVIDERS
from backend.database.db import async_db_session
from backend.database.redis import redis_client

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

def tokenize(text: str, stop_words: set[str]) -> list[str]:
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

def build_cache_key(query: str, final_limit: int, cloud_types: str | None) -> str:
    normalized = (query or "").strip().lower()
    cloud_key = (cloud_types or "").strip().lower()
    full_key = f"{normalized}-{cloud_key}-{final_limit}"
    digest = hashlib.sha256(full_key.encode("utf-8")).hexdigest()
    return f"mcp:search:resp:{digest}"

def build_lock_key(query: str, final_limit: int) -> str:
    normalized = (query or "").strip().lower()
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
    return f"mcp:search:lock:{digest}:{final_limit}"

def calc_score(resource: Resource, keywords: list[str], field_weights: dict[str, int]) -> float:
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

async def _fallback_external_search(query: str, final_limit: int, providers: list[str] | None = None) -> List[dict[str, Any]]:
    """当本地无结果时回退外部搜索，返回精简结果列表"""
    from datetime import datetime

    import httpx

    url = "https://resource.yzxj.vip/api/search"
    params = {"kw": query, "res": "merge", "conc": 5}
    if providers:
        params["cloud_types"] = ",".join(providers)
    results: list[dict[str, Any]] = []
    try:
        async with httpx.AsyncClient(timeout=8) as client:
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

            baidu_items = merged.get("baidu") or []
            for item in baidu_items:
                url_val = item.get("url")
                if not url_val:
                    continue
                
                item_remark = item.get("note", "") # 使用 note 字段作为 remark
                item_description = item.get("desc", "")
                item_url = url_val

                # 优先从URL的pwd参数中提取密码
                parsed_url = urlparse(item_url)
                query_params = parse_qs(parsed_url.query)
                extracted_password = None
                if 'pwd' in query_params and query_params['pwd']:
                    extracted_password = query_params['pwd'][0]
                elif item.get("password"): # 否则，使用结果中独立的password字段
                    extracted_password = item.get("password")

                item_to_add = {
                    "remark": item_remark,
                    "description": item_description,
                    "url": item_url,
                }
                if extracted_password:
                    item_to_add["password"] = extracted_password

                results.append(item_to_add)
            if results:
                return results

            items = root.get("results") or []
            for item in items:
                links = item.get("links") or []
                picked_url = None
                picked_password = None
                for link in links:
                    if link.get("type") == "quark" and link.get("url"):
                        picked_url = link["url"]
                        break
                    if link.get("type") == "baidu" and link.get("url"):
                        picked_url = link["url"]
                        picked_password = link.get("password")
                        break
                if not picked_url and links:
                    picked_url = links[0].get("url")
                    picked_password = links[0].get("password")
                if not picked_url:
                    continue
                title = item.get("title") or "外部搜索结果"
                dt = item.get("datetime") or ""
                channel = item.get("channel") or ""
                desc = f"{dt} {channel}".strip()
                item = {"remark": title, "description": desc or title, "url": picked_url}
                if picked_password:
                    item["password"] = picked_password
                results.append(item)
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
        list_params = ListShareFilesParam(
            drive_type=DriveType.QUARK_DRIVE.value,
            source_type="link",
            source_id=share_url,
            file_path="/",
        )
        service = CouldDriveService(auth_data=account.cookies, drive_type=DriveType.QUARK_DRIVE)
        files = await service.get_share_list(params=list_params)
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
        ok = await service.transfer_files(params=transfer_params)
        if not ok:
            return None
        client = service._client
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
        share_info = await service.create_share(params=share_params)
        if not share_info or not getattr(share_info, "url", None):
            return None
        remark = getattr(share_info, "title", "mcp-share")
        desc = ext_note or "夸克已转存并二次分享(1天有效)"
        return {"remark": remark, "description": desc, "url": share_info.url}
    except Exception:
        return None

async def _save_baidu_and_share(account_id: int, target_folder_path: str, share_url: str, password: str | None = None, ext_note: str | None = None, query: str | None = None) -> dict[str, Any] | None:
    """百度转存并二次分享，返回新的分享链接简表"""
    try:
        async with async_db_session() as db:
            account = await drive_account_dao.get(db, account_id)
            if not account or not account.cookies or account.type != DriveType.BAIDU_DRIVE.value:
                return None

        service = CouldDriveService(auth_data=account.cookies, drive_type=DriveType.BAIDU_DRIVE)

        # 预处理 share_url，移除其中的 pwd 参数，确保只通过 `password` 显式传递密码
        parsed_url = urlparse(share_url)
        query_params = parse_qs(parsed_url.query)
        if 'pwd' in query_params:
            del query_params['pwd']
        clean_query = urlencode(query_params, doseq=True)
        clean_share_url = parsed_url._replace(query=clean_query).geturl()

        print(f"[MCP] Cleaned share URL: {clean_share_url}")

        # 1. 获取分享文件列表
        list_params = ListShareFilesParam(
            drive_type=DriveType.BAIDU_DRIVE.value,
            source_type="link",
            source_id=clean_share_url, # 使用清理后的URL
            file_path="/",
        )
        # 移除 list_params.ext = {"password": password}，因为 ListShareFilesParam 没有 ext 字段

        files = await service.get_share_list(params=list_params, password=password)
        if not files:
            print("[MCP] Baidu share list empty or failed to retrieve.")
            return None

        # 提取转存所需信息，百度网盘的分享转存需要 from_uk, msg_id, fs_ids
        # 这些信息通常在 get_share_list 返回的 BaseFileInfo 对象的 file_ext 中
        first_file = files[0]
        from_uk = first_file.file_ext.get("from_uk")
        msg_id = first_file.file_ext.get("msg_id")
        # 提取所有顶层文件的 fs_id 用于转存
        fs_ids = [f.file_id for f in files]

        if not fs_ids:
            print(f"[MCP] Baidu share info incomplete: from_uk={from_uk}, msg_id={msg_id}, fs_ids={fs_ids}")
            return None

        # 2. 执行转存操作
        # 对于链接分享转存，不需要 from_uk, msg_id 参数
        transfer_params = TransferParam(
            drive_type=DriveType.BAIDU_DRIVE.value,
            source_type="link",
            source_id=share_url,  # 对于链接分享，source_id 就是链接本身
            source_path="/",  # 通常是根路径
            target_path=target_folder_path, # Corrected from target_folder_id
            file_ids=fs_ids,
            ext={}
        )

        print(f"[MCP] Initiating Baidu transfer to {target_folder_path} for fs_ids: {fs_ids}")
        try:
            await service.transfer_files(params=transfer_params)
        except Exception as e:
            print(f"[MCP] Baidu transfer failed: {e}")
            return None

        # 3. 获取转存后的文件 ID （由于百度API的限制，转存不直接返回新文件ID）
        # 因此，需要列出目标文件夹的内容，并根据文件名匹配来找到刚刚转存成功的文件
        list_target_params = ListFilesParam( # Corrected from ListShareFilesParam
            drive_type=DriveType.BAIDU_DRIVE.value,
            file_path=target_folder_path, # Corrected from target_folder_id
        )
        transferred_files_in_target = await service.get_disk_list(params=list_target_params)

        if not transferred_files_in_target:
            print("[MCP] Failed to list transferred files in target folder.")
            return None

        # 匹配文件名，找到对应的 fs_id
        # 注意：这是一个简化的匹配，如果原始分享包含多个同名文件或目录，可能需要更健壮的匹配逻辑
        original_file_names = {f.file_name for f in files}
        to_share_fs_ids: list[str] = []
        for tf in transferred_files_in_target:
            if tf.file_name in original_file_names and tf.file_id:
                to_share_fs_ids.append(tf.file_id)
        
        if not to_share_fs_ids:
            print("[MCP] No transferred files found for re-sharing.")
            return None
        
        # 4. 创建新的分享链接
        # 百度分享需要文件 fs_id 列表，且系统生成的提取码固定为 "zyas"
        share_params = ShareParam(
            drive_type=DriveType.BAIDU_DRIVE.value,
            file_name=f"mcp-baidu-share-{int(time.time())}", # 自动生成文件名
            file_ids=to_share_fs_ids,
            expired_type=1, # 默认 1 天有效期
            password="zyas", # 系统生成的百度分享提取码固定为 "zyas"
        )
        share_info = await service.create_share(params=share_params)

        if not share_info or not getattr(share_info, "url", None):
            print("[MCP] Baidu create share failed.")
            return None

        remark_to_return = query or getattr(share_info, "title", "mcp-baidu-share") # 将 remark 设置为搜索query
        desc_to_return = ext_note or "百度已转存并二次分享(1天有效，密码: zyas)"
        return {"remark": remark_to_return, "description": desc_to_return, "url": share_info.url}
    except Exception as e:
        print(f"[MCP] Baidu save and share failed: {e}")
        return None

async def _load_drive_config(provider: str) -> tuple[int | None, str | None]:
    """
    读取指定网盘的账号与文件夹配置（JSON 模式）
    
    注意: folder_id 对于百度网盘，实际存储的是目标文件夹的完整路径 (e.g., "/我的资源/保存目录")，而不是一个 ID。

    :param provider: 网盘类型标识
    :return:
    """
    account_id: int | None = None
    folder_id: str | None = None
    config_field = f"{provider}_config"
    try:
        async with async_db_session() as db_cfg:
            cfg = await mcp_config_dao.get_by_mcp_and_field(db_cfg, "resource", config_field)
            data = (cfg.value or {}) if cfg else {}
            if isinstance(data, dict):
                acc_raw = data.get("account_id")
                fid_raw = data.get("folder_id")
                if acc_raw is not None:
                    try:
                        account_id = int(str(acc_raw).strip())
                    except Exception:
                        account_id = None
                if fid_raw is not None:
                    folder_id = str(fid_raw).strip()
    except Exception as e:
        print(f"[MCP] load drive config failed: provider={provider} err={e}")
    return account_id, folder_id

async def _save_not_implemented(account_id: int, folder_id: str, share_url: str, ext_note: str | None) -> dict[str, Any] | None:
    """占位：未实现的网盘类型"""
    return None

SAVE_SHARE_HANDLERS = {p: _save_not_implemented for p in ALLOWED_PROVIDERS}
SAVE_SHARE_HANDLERS.update({
    "quark": _save_quark_and_share,
    "baidu": _save_baidu_and_share,
})

async def _save_share(provider: str, account_id: int, folder_id: str, share_url: str, ext_note: str | None, password: str | None = None, query: str | None = None) -> dict[str, Any] | None:
    """
    根据网盘类型分发转存分享

    :param provider: 网盘类型标识
    :param account_id: 账户 ID
    :param folder_id: 目标文件夹 ID
    :param share_url: 外部分享链接
    :param ext_note: 备注
    :param password: 分享密码 (可选)
    :return:
    """
    handler = SAVE_SHARE_HANDLERS.get(provider, _save_not_implemented)
    # 只有在处理百度网盘时才传递 password
    if provider == "baidu":
        return await handler(account_id, folder_id, share_url, password, ext_note, query)
    return await handler(account_id, folder_id, share_url, ext_note)


async def perform_resource_search(query: str, limit: int = 5, cloud_types: str | None = None, enable_external_search: bool = True) -> list[dict[str, Any]]:
    """
    执行资源搜索的核心逻辑

    :param query: 核心检索短语
    :param limit: 返回条数
    :param cloud_types: 逗号分隔的网盘类型
    :param enable_external_search: 是否启用外部搜索
    :return:
    """
    start = time.time()
    limit = max(1, min(50, int(limit)))
    normalized_query = re.sub(r"[\s\u3000]+", "", (query or ""))[:200]
    keywords = tokenize(normalized_query, stop_words)
    if not keywords:
        return []

    cache_key = build_cache_key(normalized_query, limit, cloud_types)
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

    # 读取动态配置（JSON 结构，字段如 quark_config/baidu_config/...）
    # 此处不需要再从 config DB 读取 quark_config，因为 _load_drive_config 会在 _save_share 内部调用
    # 百度和夸克的配置会在 _save_share 被调用时根据 provider 自动加载
    
    async with async_db_session() as db:
        conditions: list[Any] = [Resource.status == 1, Resource.is_deleted == False]  # noqa: E712

        if cloud_types:
            allowed_drive_types = []
            # 将传入的 cloud_types 字符串（如 "baidu,quark"）转换为 DriveType 枚举值
            # 并只保留有效的网盘类型
            for ct_str in [s.strip() for s in cloud_types.split(",") if s.strip()]:
                try:
                    # DriveType 枚举值是 "BaiduDrive", "QuarkDrive" 等
                    # 尝试从字符串直接获取枚举值，忽略大小写，并处理可能的别名
                    # 例如："baidu" -> DriveType.BAIDU_DRIVE
                    # 或者 "quark" -> DriveType.QUARK_DRIVE
                    # 这里需要一个从字符串到枚举值的映射
                    if ct_str.lower() == "baidu":
                        allowed_drive_types.append(DriveType.BAIDU_DRIVE.value)
                    elif ct_str.lower() == "quark":
                        allowed_drive_types.append(DriveType.QUARK_DRIVE.value)
                    # 可以根据需要添加其他网盘类型的映射
                except Exception:
                    # 如果转换失败，说明是不支持的类型，忽略
                    print(f"[MCP] Warning: Unsupported cloud_type '{ct_str}' in local search filter.")
                    continue

            # 如果指定了 cloud_types，但没有有效的网盘类型被解析出来，则直接返回空列表
            if not allowed_drive_types and cloud_types:
                return []
            
            conditions.append(Resource.url_type.in_(allowed_drive_types))

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
            score = calc_score(r, keywords, field_weights)
            item = {
                "remark": r.remark or "无备注",
                "description": r.description or "无描述",
                "url": r.url,
            }
            # 如果是百度网盘且有提取码，则拼接提取码到 URL
            if r.url_type == DriveType.BAIDU_DRIVE.value and r.extract_code:
                parsed_url = urlparse(item["url"])
                query_params = parse_qs(parsed_url.query)
                query_params["pwd"] = [r.extract_code] # 将提取码作为 pwd 参数添加
                new_query = urlencode(query_params, doseq=True)
                item["url"] = parsed_url._replace(query=new_query).geturl()

            scored.append((score, item))
        scored.sort(key=lambda x: x[0], reverse=True)
        top_rows = [item for _, item in scored[:limit]]

        # 本地为空：仅在配置齐全且成功“转存分享”时，返回最新一条分享；否则不返回外部结果
        if not top_rows and enable_external_search:
            providers_to_try: list[str]
            if cloud_types:
                # 分割并清理输入的云类型字符串
                cleaned_cloud_types = [s.strip() for s in cloud_types.split(",") if s.strip()]
                # 过滤出允许的提供商
                providers_to_try = [p for p in cleaned_cloud_types if p in ALLOWED_PROVIDERS]
                if not providers_to_try:
                    # 如果用户指定了云类型但没有一个是允许的，则尝试百度和夸克
                    providers_to_try = ["baidu", "quark"]
            else:
                # 如果没有指定云类型，默认尝试百度和夸克
                providers_to_try = ["baidu", "quark"]

            saved_row: dict[str, Any] | None = None
            for provider in providers_to_try:
                ext_rows = await _fallback_external_search(normalized_query, 1, providers=[provider])

                if not ext_rows:
                    continue
                account_id, folder_id = await _load_drive_config(provider)
                if not account_id or not folder_id:
                    print(f"[MCP] Config incomplete for {provider}: account_id={account_id}, folder_id={folder_id}")
                    continue
                first = ext_rows[0]
                saved_row = await _save_share(
                    provider=provider,
                    account_id=account_id,
                    folder_id=folder_id,
                    share_url=first.get("url", ""),
                    ext_note=first.get("remark"),
                    password=first.get("password"),
                    query=normalized_query, # 新增：传递搜索query
                )
                if saved_row:
                    break
            top_rows = [saved_row] if saved_row else []

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

    return top_rows


def register_resource_search_tools(mcp: FastMCP) -> None:
    """在 FastMCP 上注册资源搜索工具（本地 DB + 缓存 + 简单权重评分）"""

    # 将一些内部函数移到 register_resource_search_tools 外部，以便 perform_resource_search 可以直接访问它们
    # 确保这些函数能够访问到外部作用域的变量 (field_weights, stop_words)
    # 或者将这些变量作为参数传递给它们

    # 将一些内部函数移到 register_resource_search_tools 外部，以便 perform_resource_search 可以直接访问它们
    # 确保这些函数能够访问到外部作用域的变量 (field_weights, stop_words)
    # 或者将这些变量作为参数传递给它们


    @mcp.tool()
    async def search_resources(query: str, limit: int = 5, cloud_types: str = None, enable_external_search: bool = True) -> list[dict[str, Any]]:
        """
        搜索资源库

        使用建议（供 LLM 调用方参考）：
        - 先从用户问题中抽取最核心的检索短语作为 query（去掉“有没有/资源/哪里有/找/搜索/关于/的”等冗词）。
        - 示例：
          * 用户问“有没有 XX 的资源？” → query="XX"
          * 用户问“XX 资源” → query="XX"
        - 本地有结果：仅返回本地前 N 条（受 limit 限制，不补齐）。
        - 本地无结果：仅当配置齐全且转存分享成功时，返回最新的一条分享，否则返回空。

        :param query: 核心检索短语（后端会做分词与去噪，且包含规则短语兜底）
        :param limit: 返回条数（默认 5, 1-50）
        :param cloud_types: 逗号分隔的网盘类型（如 "quark,baidu,aliyun,123"），当前仅 quark
        :param enable_external_search: 是否在本地无结果时启用外部搜索（默认 True）
        :return:
        """
        return await perform_resource_search(query, limit, cloud_types, enable_external_search)
