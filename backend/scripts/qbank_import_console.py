#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio
import hashlib
import os
import re
import sys
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import httpx
from sqlalchemy import delete as sa_delete
from sqlalchemy import func, select, text as sa_text, update as sa_update

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.question_bank.crud.crud_question import option_content_dao, question_analysis_dao, question_option_dao
from backend.app.question_bank.model import Question, QuestionBank, QuestionChapter, QuestionMaterial, QuestionPlacement
from backend.app.question_bank.model.question import question_material_relation
from backend.app.question_bank.schema.question import UpsertQuestionAnalysisItem, UpsertQuestionOptionItem
from backend.database.db import async_db_session
from backend.scripts.qbank_image_mirror import QbankImageMirror


class ImportErrorBase(Exception):
    """导入错误。"""


@dataclass
class AreaNode:
    area_id: int
    name: str
    parent_id: int


@dataclass
class RemotePaper:
    paper_id: int
    area_id: int
    area_name: str
    name: str
    qcount: int
    year: int | None


@dataclass
class ImportPaperData:
    paper_id: int
    paper_name: str
    qids: list[int]
    qsort: list[int]
    modules: list[str | None]

@dataclass
class LocalEmptyPaperBank:
    bank_id: int
    paper_id: int
    code: str
    name: str
    placement_count: int
    distinct_question_count: int


@dataclass
class LocalMissingMaterialPaperBank:
    bank_id: int
    paper_id: int
    code: str
    name: str
    placement_count: int
    distinct_question_count: int
    material_count: int

# 这里直接改 Cookie 即可；也支持环境变量 HUATU_COOKIE 覆盖
HUATU_COOKIE = os.getenv("HUATU_COOKIE", """ht_businessUnitId=1; _c_WBKFRo=73LABjrVnFRyotN37t46HWSL2xqHPtneKoespgJB; sensorsdata2015jssdkchannel=%7B%22prop%22%3A%7B%22_sa_channel_landing_url%22%3A%22%22%7D%7D; ahhtip={"prov":"æµ™æ±Ÿ","city":"æ­å·ž","county":"","time":1773227041152}; ahexamtype=ahgwy; Hm_lvt_c5b3a7bc9cfb4e1133c856fee205fabd=1772622241,1772709667; Hm_lpvt_c5b3a7bc9cfb4e1133c856fee205fabd=1772709667; HMACCOUNT=A4C02431E5478C15; PHPSESSID=55b4roi9f9cp0r9sehuhmfj336; Hm_lvt_acd6257d64dd07c2b9bfcb44821207b3=1772761564; UserID=0; UserName=app_ztk1358512080; UserReName=157%2A%2A%2A%2A8743; UserFace=https%3A%2F%2Ftiku.huatu.com%2Fcdn%2Fimages%2Fvhuatu%2Favatars%2Fdefault2.png; synlogin=0; userMobile=15757698743; accountStatus=0; userCode=000ht14718112ae6; ht_token=7edc0947899f4c5e936929cdd11c442f; ht_id=246478648; ht_uname=app_ztk1358512080; ht_qcount=10; ucId=15757698743; jtoken=eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJpYXQiOiIxNzcyNzYxNzA0IiwianRpIjoiTVRjM01qYzJNVGN3TkE9PSIsImV4cCI6IjE3NzUzNTM3MDQiLCJ1bmFtZSI6ImFwcF96dGsxMzU4NTEyMDgwIiwibmljayI6IjE1NyoqKio4NzQzIn0.pfIvY6M5LFHlN8dFwq6tFbgbXTrjjCBjMJZQMwVABKE; ht_catgory=1; ht_sub=1; isUserMemberapp_ztk1358512080=2; sensorsdata2015jssdkcross=%7B%22distinct_id%22%3A%2215757698743%22%2C%22first_id%22%3A%2219cb884dcfb15a9-0ceb7ded9951ae8-4c657b58-2073600-19cb884dcfc218f%22%2C%22props%22%3A%7B%22%24latest_traffic_source_type%22%3A%22%E7%9B%B4%E6%8E%A5%E6%B5%81%E9%87%8F%22%2C%22%24latest_search_keyword%22%3A%22%E6%9C%AA%E5%8F%96%E5%88%B0%E5%80%BC_%E7%9B%B4%E6%8E%A5%E6%89%93%E5%BC%80%22%2C%22%24latest_referrer%22%3A%22%22%2C%22%24latest_landing_page%22%3A%22https%3A%2F%2Fv.huatu.com%2Fmock%2Fpractice%2F%3Fanswerid%3D177276171665337202%22%7D%2C%22identities%22%3A%22eyIkaWRlbnRpdHlfY29va2llX2lkIjoiMTljYjg4NGRjZmIxNWE5LTBjZWI3ZGVkOTk1MWFlOC00YzY1N2I1OC0yMDczNjAwLTE5Y2I4ODRkY2ZjMjE4ZiIsIiRpZGVudGl0eV9sb2dpbl9pZCI6IjE1NzU3Njk4NzQzIn0%3D%22%2C%22history_login_id%22%3A%7B%22name%22%3A%22%24identity_login_id%22%2C%22value%22%3A%2215757698743%22%7D%2C%22%24device_id%22%3A%2219cb884dcfb15a9-0ceb7ded9951ae8-4c657b58-2073600-19cb884dcfc218f%22%7D; ht_auth=d1G2h9pbbbm9sd6fe9yaJep6Z9C2If60Ibj2I604Nej4Qb38OaD1Y504O8C2I2s1Im1vYmlsZSI6IjE1NzU3Njk4NzQzIiwiZW1haWwiOiJhcHBfenRrMTM1ODUxMjA4MCU0MHp0ay5jb20iLCJuYW1lIjoiYXBwX3p0azEzNTg1MTIwODAiLCJuaWNrIjoiMTU3JTJBJTJBJTJBJTJBODc0MyIsInNpZ25hdHVyZSI6IiIsImFyZWEiOiItOSIsInN1YmplY3QiOjAsInN0YXR1cyI6IjIiLCJhdmF0YXIiOiJodHRwcyUzQSUyRiUyRnRpa3UuaHVhdHUuY29tJTJGY2RuJTJGaW1hZ2VzJTJGdmh1YXR1JTJGYXZhdGFycyUyRmRlZmF1bHQyLnBuZyIsInJlZ0Zyb20iOiIxIiwiZGV2aWNlVG9rZW4iOm51bGwsImNyZWF0ZVRpbWUiOiIxNjQxOTEyODYyMDAwIiwidWNlbnRlcklkIjoiMzEyOTg4NzgiLCJwaG9uZUdlbyI6IiVFNiVCNSU5OSVFNiVCMSU5RiVFNyU5QyU4MSVFNSU4RiVCMCVFNSVCNyU5RSVFNSVCOCU4MiIsInBsYW5UaW1lIjoiIiwicHJvZmVzc2lvbiI6IiIsImFwcGx5RGVsZXRlVGltZSI6MCwibmV3VWNJZCI6IjE0NzE4MTEyIiwidXNlckNvZGUiOiIwMDBodDE0NzE4MTEyYWU2Iiwid3hOaWNrIjoiIiwibGFzdExvZ2luVGltZSI6MCwidW5hbWUiOiJhcHBfenRrMTM1ODUxMjA4MCIsInRva2VuIjoiN2VkYzA5NDc4OTlmNGM1ZTkzNjkyOWNkZDExYzQ0MmYiLCJxY291bnQiOiIxMCIsImNhdGdvcnkiOiIxIn0O0O0O; Hm_lvt_f735d6529dbfd84e0e9d68fea4bb90a4=1772848015; Hm_lpvt_f735d6529dbfd84e0e9d68fea4bb90a4=1772848015; u3_fujian=%5B%7B%22title%22%3A%22%E5%8D%8E%E5%9B%BE%E5%9C%A8%E7%BA%BF-%E5%85%AC%E8%81%8C%E6%95%99%E8%82%B2%E7%BD%91%E7%BB%9C%E5%AD%A6%E4%B9%A0%E5%B9%B3%E5%8F%B0%22%2C%22url%22%3A%22https%3A%2F%2Fv.huatu.com%2F%22%7D%5D; acw_tc=7b39f6bc17728519697513674e1b17ce09cf7a6c6afbcddc512ddf7fde6965; Hm_lpvt_acd6257d64dd07c2b9bfcb44821207b3=1772852222""")

LIST_URL = "https://v.huatu.com/tiku/common/getlist"
AREA_URL = "https://v.huatu.com/tiku/common/getarea"
QUESTION_URL = "https://ns.huatu.com/q/v4/questions"

DEFAULT_AREA_IDS = [
    -9,
    1,
    21,
    41,
    225,
    356,
    471,
    586,
    656,
    802,
    823,
    943,
    1045,
    1168,
    1263,
    1374,
    1532,
    1709,
    1826,
    1963,
    1964,
    1988,
    2106,
    2230,
    2257,
    2299,
    2502,
    2600,
    2746,
    2827,
    2945,
    3046,
    3098,
    3125,
    100001,
]

CANONICAL_CHAPTERS = [
    "政治理论",
    "常识判断",
    "言语理解与表达",
    "数量关系",
    "判断推理",
    "资料分析",
]

CHAPTER_ALIASES = {
    "政治": "政治理论",
    "常识": "常识判断",
    "言语理解": "言语理解与表达",
    "言语": "言语理解与表达",
    "数量": "数量关系",
    "判断": "判断推理",
    "资料": "资料分析",
}


def sanitize_cookie(cookie: str) -> str:
    """
    仅保留有效 ASCII Cookie 段。

    :param cookie: 原始 cookie
    :return:
    """
    if not cookie:
        return ""

    segments = [segment.strip() for segment in cookie.split(";")]
    cleaned_segments: list[str] = []
    for segment in segments:
        if not segment:
            continue
        if "=" not in segment:
            continue
        try:
            segment.encode("ascii")
        except UnicodeEncodeError:
            continue
        cleaned_segments.append(segment)

    return "; ".join(cleaned_segments)


def extract_cookie_value(cookie: str, key: str) -> str:
    """
    从 Cookie 提取指定 key 的值。

    :param cookie: 清洗后的 Cookie
    :param key: 键名
    :return:
    """
    prefix = f"{key}="
    for segment in cookie.split(";"):
        item = segment.strip()
        if item.startswith(prefix):
            return item[len(prefix) :]
    return ""


def extract_paper_list(payload: Any) -> list[dict[str, Any]]:
    """
    从接口响应提取试卷列表。

    :param payload: 接口 JSON
    :return:
    """
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]

    if not isinstance(payload, dict):
        raise ImportErrorBase("response payload is not object/list")

    code_value = payload.get("code")
    if code_value not in (None, 1):
        raise ImportErrorBase(f"response code invalid: {code_value}, msg={payload.get('msg')}")

    data = payload.get("data")
    if not isinstance(data, list):
        raise ImportErrorBase("response.data is not list")
    return [item for item in data if isinstance(item, dict)]


def build_huatu_headers(cookie: str) -> dict[str, str]:
    """
    构建华图列表接口请求头。

    :param cookie: 原始 Cookie
    :return:
    """
    headers = {
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Accept-Encoding": "gzip, deflate, br, zstd",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "Connection": "keep-alive",
        "Origin": "https://v.huatu.com",
        "Referer": "https://v.huatu.com/tiku/truelist/1/1",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/145.0.0.0 Safari/537.36 Edg/145.0.0.0"
        ),
        "X-Requested-With": "XMLHttpRequest",
    }
    cookie_header = sanitize_cookie(cookie)
    if not cookie_header:
        return headers

    headers["Cookie"] = cookie_header
    token = extract_cookie_value(cookie_header, "ht_token")
    if token:
        headers["token"] = token
        headers["Access-Token"] = token
    headers["terminal"] = "pc"
    headers["cv"] = "1"
    return headers


async def fetch_huatu_list(
    *,
    url: str,
    cookie: str,
    area: int,
    papertype: str,
) -> dict[str, Any]:
    """
    请求华图试卷列表。

    :param url: 接口地址
    :param cookie: Cookie
    :param area: 区域 ID
    :param papertype: 试卷类型
    :return:
    """
    headers = build_huatu_headers(cookie)
    if cookie:
        cookie_header = sanitize_cookie(cookie)
        if not cookie_header:
            raise ImportErrorBase("cookie has no valid ASCII segments after sanitize")

    form_data = {"area": str(area), "papertype": papertype}
    timeout = httpx.Timeout(timeout=30.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.post(url=url, data=form_data, headers=headers)
        response.raise_for_status()
        try:
            return response.json()
        except ValueError as exc:
            raise ImportErrorBase(f"response is not valid JSON: {response.text[:300]}") from exc


def ask(prompt: str, default: str | None = None) -> str:
    """
    读取输入。

    :param prompt: 提示语
    :param default: 默认值
    :return:
    """
    if default is None:
        value = input(f"{prompt}: ").strip()
    else:
        value = input(f"{prompt} [{default}]: ").strip()
        if not value:
            return default
    return value


def ask_int(prompt: str, default: int | None = None) -> int:
    """
    读取整数输入。

    :param prompt: 提示语
    :param default: 默认值
    :return:
    """
    while True:
        raw = ask(prompt, None if default is None else str(default))
        try:
            return int(raw)
        except ValueError:
            print("请输入整数。")


def ask_float(prompt: str, default: float | None = None) -> float:
    """
    读取浮点数输入。

    :param prompt: 提示语
    :param default: 默认值
    :return:
    """
    while True:
        raw = ask(prompt, None if default is None else str(default))
        try:
            return float(raw)
        except ValueError:
            print("请输入数字。")


def ask_yes_no(prompt: str, default_yes: bool = True) -> bool:
    """
    读取是/否输入。

    :param prompt: 提示语
    :param default_yes: 默认是否
    :return:
    """
    default = "Y/n" if default_yes else "y/N"
    while True:
        raw = input(f"{prompt} [{default}]: ").strip().lower()
        if not raw:
            return default_yes
        if raw in {"y", "yes"}:
            return True
        if raw in {"n", "no"}:
            return False
        print("请输入 y 或 n。")


def parse_index_input(raw: str, max_index: int) -> list[int]:
    """
    解析 1,3,8-10 / all 这类输入。

    :param raw: 用户输入
    :param max_index: 最大序号
    :return:
    """
    text_raw = raw.strip().lower()
    if text_raw in {"all", "a", "*"}:
        return list(range(1, max_index + 1))

    selected: set[int] = set()
    parts = [x.strip() for x in raw.split(",") if x.strip()]
    for part in parts:
        if "-" in part:
            left, right = part.split("-", 1)
            start = int(left.strip())
            end = int(right.strip())
            if start > end:
                start, end = end, start
            for idx in range(start, end + 1):
                if 1 <= idx <= max_index:
                    selected.add(idx)
            continue
        idx = int(part)
        if 1 <= idx <= max_index:
            selected.add(idx)
    return sorted(selected)


def build_import_args(
    *,
    areas: list[int],
    name_regex: str,
    dry_run: bool,
    mirror_images: bool,
    paper_id: int = 0,
    max_papers: int = 0,
    max_questions: int = 0,
    mirror_sample_limit: int = 0,
    mirror_safe_interval: float = 2.5,
) -> SimpleNamespace:
    """
    构建导入参数对象。

    :param areas: 区域 ID 列表
    :param name_regex: 试卷名过滤正则
    :param dry_run: 是否演练模式
    :param paper_id: 指定试卷 ID
    :param max_papers: 最大试卷数
    :param max_questions: 最大题目数
    :param mirror_sample_limit: 镜像前后 URL 样本条数
    :param mirror_safe_interval: 图片下载安全间隔秒数
    :return:
    """
    return SimpleNamespace(
        list_url=LIST_URL,
        question_url=QUESTION_URL,
        cookie=HUATU_COOKIE.strip(),
        areas=",".join(str(x) for x in areas),
        name_regex=name_regex,
        paper_category=1,
        paper_code_prefix="PAPER",
        chapter_bank_code="BANK_XINGCE",
        question_chunk_size=120,
        max_papers=max_papers,
        max_questions=max_questions,
        paper_id=paper_id,
        terminal="3",
        app_type="2",
        request_interval=0.08,
        created_by=1,
        dry_run=dry_run,
        trace_db=False,
        mirror_images=mirror_images,
        mirror_cache_file=str(PROJECT_ROOT / "backend" / "scripts" / "cache" / "qbank_image_cache.json"),
        mirror_timeout=20.0,
        mirror_object_expire_days=None,
        mirror_sample_limit=max(0, mirror_sample_limit),
        mirror_safe_interval=max(0.0, mirror_safe_interval),
        mirror_safe_jitter=min(1.0, max(0.0, mirror_safe_interval * 0.2)),
    )


async def fetch_remote_areas() -> list[AreaNode]:
    """从华图接口获取区域。"""
    headers = build_huatu_headers(HUATU_COOKIE)
    timeout = httpx.Timeout(timeout=30.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.post(url=AREA_URL, data={}, headers=headers)
        response.raise_for_status()
        payload = response.json()

    data = payload.get("data")
    if not isinstance(data, list):
        raise RuntimeError(f"地区接口返回异常: {payload}")

    out: list[AreaNode] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        area_id = item.get("id")
        name = str(item.get("name") or "").strip()
        parent_id = item.get("parentId")
        if not isinstance(area_id, int):
            continue
        if not isinstance(parent_id, int):
            continue
        if not name:
            continue
        out.append(AreaNode(area_id=area_id, name=name, parent_id=parent_id))
    return out


def fallback_areas() -> list[AreaNode]:
    """使用内置区域列表兜底。"""
    return [AreaNode(area_id=x, name=f"地区{x}", parent_id=0) for x in DEFAULT_AREA_IDS]


def choose_areas_by_response(areas: list[AreaNode]) -> list[AreaNode]:
    """
    交互选择区域。

    :param areas: 区域数据
    :return:
    """
    root_areas = [x for x in areas if x.parent_id == 0]
    root_areas = sorted(root_areas, key=lambda x: x.area_id)

    print("\n可选地区：")
    for idx, area in enumerate(root_areas, start=1):
        print(f"{idx:>2}. {area.name} (id={area.area_id})")

    while True:
        raw = ask("请输入地区序号（支持 1,3,8-10；all=全部）", "1")
        try:
            indices = parse_index_input(raw, len(root_areas))
        except Exception:
            print("地区序号格式不正确，请重试。")
            continue
        if not indices:
            print("至少选择一个地区。")
            continue
        selected = [root_areas[i - 1] for i in indices]
        selected_text = ", ".join(f"{x.name}(id={x.area_id})" for x in selected)
        print(f"已选地区：{selected_text}")
        return selected


async def fetch_remote_papers(area_nodes: list[AreaNode], name_regex: str) -> list[RemotePaper]:
    """
    按地区抓取并过滤远程试卷。

    :param area_nodes: 地区列表
    :param name_regex: 名称正则
    :return:
    """
    pattern = re.compile(name_regex)
    paper_map: dict[int, RemotePaper] = {}
    area_name_map = {x.area_id: x.name for x in area_nodes}

    for node in area_nodes:
        payload = await fetch_huatu_list(url=LIST_URL, cookie=HUATU_COOKIE, area=node.area_id, papertype="")
        if isinstance(payload, dict) and payload.get("code") == -1:
            print(f"[扫描] 地区={node.name}(id={node.area_id}) 匹配试卷=0（接口返回暂无数据）")
            continue
        papers = extract_paper_list(payload)
        matched = 0
        for paper in papers:
            pid = paper.get("id")
            if not isinstance(pid, int):
                continue
            name = str(paper.get("name") or "").strip()
            if not name:
                continue
            if not pattern.search(name):
                continue
            if paper.get("catgory") != 1:
                continue
            questions = paper.get("questions")
            qcount = len(questions) if isinstance(questions, list) else int(paper.get("qcount") or 0)
            if qcount <= 0:
                continue

            year: int | None = None
            try:
                candidate_year = int(paper.get("year"))
            except Exception:
                candidate_year = 0
            if 1900 <= candidate_year <= 2100:
                year = candidate_year

            incoming = RemotePaper(
                paper_id=pid,
                area_id=node.area_id,
                area_name=area_name_map.get(node.area_id, str(node.area_id)),
                name=name,
                qcount=qcount,
                year=year,
            )
            current = paper_map.get(pid)
            if current is None or incoming.qcount > current.qcount:
                paper_map[pid] = incoming
            matched += 1
        print(f"[扫描] 地区={node.name}(id={node.area_id}) 匹配试卷={matched}")

    papers = sorted(
        paper_map.values(),
        key=lambda x: ((x.year or 0), x.area_id, x.paper_id),
        reverse=True,
    )
    return papers


def choose_papers_by_response(papers: list[RemotePaper]) -> list[RemotePaper]:
    """
    交互选择试卷。

    :param papers: 远程试卷
    :return:
    """
    if not papers:
        return []

    print(f"\n匹配到试卷 {len(papers)} 条（展示前 80 条）：")
    show_count = min(len(papers), 80)
    for idx in range(show_count):
        paper = papers[idx]
        year_text = str(paper.year) if paper.year is not None else "-"
        print(
            f"{idx + 1:>3}. [{paper.area_name}] year={year_text} q={paper.qcount} "
            f"id={paper.paper_id} {paper.name}"
        )

    if len(papers) > show_count:
        print(f"... 还有 {len(papers) - show_count} 条未显示，可缩小关键词后再选。")

    while True:
        default_select = "1" if len(papers) == 1 else ""
        raw = ask("请输入试卷序号（支持 1,3,8-10；all=全部）", default_select)
        if not raw:
            print("请至少选择一个试卷。")
            continue
        try:
            indices = parse_index_input(raw, len(papers))
        except Exception:
            print("试卷序号格式不正确，请重试。")
            continue
        if not indices:
            print("请至少选择一个有效序号。")
            continue
        selected = [papers[i - 1] for i in indices]
        print(f"已选试卷 {len(selected)} 条。")
        return selected


def split_chunks(items: list[int], size: int) -> list[list[int]]:
    """
    按块分割列表。

    :param items: 原始列表
    :param size: 每块大小
    :return:
    """
    if size <= 0:
        return [items]
    return [items[index : index + size] for index in range(0, len(items), size)]


def to_decimal(value: Any) -> Decimal | None:
    """
    转 Decimal。

    :param value: 原始值
    :return:
    """
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None


def normalize_chapter_name(text_value: str | None) -> str | None:
    """
    标准化章节名。

    :param text_value: 原始章节名
    :return:
    """
    if not text_value:
        return None
    raw = str(text_value).strip()
    if not raw:
        return None
    for name in CANONICAL_CHAPTERS:
        if name in raw:
            return name
    for alias, target in CHAPTER_ALIASES.items():
        if alias in raw:
            return target
    return None


def parse_qids(raw: Any) -> list[int]:
    """
    解析题目 ID 列表。

    :param raw: 原始字段
    :return:
    """
    if not isinstance(raw, list):
        return []
    seen: set[int] = set()
    out: list[int] = []
    for value in raw:
        if not isinstance(value, int):
            continue
        if value in seen:
            continue
        seen.add(value)
        out.append(value)
    return out


def parse_qsort(raw: Any, count: int) -> list[int]:
    """
    解析题号顺序。

    :param raw: 原始字段
    :param count: 题目数
    :return:
    """
    if isinstance(raw, list) and len(raw) == count:
        out: list[int] = []
        for index, value in enumerate(raw, start=1):
            try:
                out.append(int(value))
            except (ValueError, TypeError):
                out.append(index)
        return out
    return list(range(1, count + 1))


def parse_modules(raw: Any, count: int) -> list[str | None]:
    """
    解析模块名称并按题号展开。

    :param raw: modules 原始数据
    :param count: 题目数
    :return:
    """
    out: list[str | None] = [None] * count
    if not isinstance(raw, list):
        return out
    cursor = 0
    for item in raw:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        try:
            qcount = int(item.get("qcount") or 0)
        except (ValueError, TypeError):
            qcount = 0
        if qcount <= 0:
            continue
        end = min(cursor + qcount, count)
        for index in range(cursor, end):
            out[index] = name
        cursor = end
        if cursor >= count:
            break
    return out


def flatten_question_rows(payload: dict[str, Any]) -> dict[int, dict[str, Any]]:
    """
    展平题目响应并合并子题字段。

    :param payload: 题目接口响应
    :return:
    """
    def has_text(value: Any) -> bool:
        return isinstance(value, str) and bool(value.strip())

    def has_material_list(value: Any) -> bool:
        if not isinstance(value, list):
            return False
        for node in value:
            if isinstance(node, str) and node.strip():
                return True
            if isinstance(node, dict):
                for key in ["content", "material", "stem", "text", "body"]:
                    candidate = node.get(key)
                    if isinstance(candidate, str) and candidate.strip():
                        return True
        return False

    def is_empty_value(value: Any) -> bool:
        if value is None:
            return True
        if isinstance(value, str):
            return not value.strip()
        if isinstance(value, (list, dict, tuple, set)):
            return len(value) == 0
        return False

    def merge_row(old_row: dict[str, Any] | None, new_row: dict[str, Any]) -> dict[str, Any]:
        if old_row is None:
            return dict(new_row)
        merged = dict(old_row)
        for key, value in new_row.items():
            if key not in merged or is_empty_value(merged.get(key)):
                merged[key] = value
                continue
            if not is_empty_value(value):
                merged[key] = value
        return merged

    rows: dict[int, dict[str, Any]] = {}
    data = payload.get("data")
    candidates: list[list[Any]] = []
    if isinstance(data, list):
        candidates.append(data)
    elif isinstance(data, dict):
        for value in data.values():
            if isinstance(value, list):
                candidates.append(value)

    for items in candidates:
        for item in items:
            if not isinstance(item, dict):
                continue
            qid = item.get("id")
            if isinstance(qid, int):
                rows[qid] = merge_row(rows.get(qid), item)

            children = item.get("childrens")
            if not isinstance(children, list):
                continue
            for child in children:
                if not isinstance(child, dict):
                    continue
                child_id = child.get("id")
                if not isinstance(child_id, int):
                    continue
                child_payload = dict(child)
                parent_material = item.get("material")
                if has_text(parent_material) and not has_text(child_payload.get("material")):
                    child_payload["material"] = parent_material

                parent_materials = item.get("materials")
                if has_material_list(parent_materials) and not has_material_list(child_payload.get("materials")):
                    child_payload["materials"] = parent_materials

                rows[child_id] = merge_row(rows.get(child_id), child_payload)
    return rows


def parse_answers(item: dict[str, Any], option_count: int) -> tuple[list[str], list[str]]:
    """
    解析答案。

    :param item: 题目数据
    :param option_count: 选项数
    :return:
    """
    raw_values: list[str] = []
    answer_list = item.get("answerList")
    if isinstance(answer_list, list) and answer_list:
        raw_values = [str(x) for x in answer_list if str(x).strip()]
    elif item.get("answer") is not None:
        raw_text = str(item.get("answer")).strip()
        if "," in raw_text:
            raw_values = [x.strip() for x in raw_text.split(",") if x.strip()]
        elif raw_text:
            raw_values = [raw_text]

    codes: list[str] = []
    for raw in raw_values:
        if raw.isdigit():
            num = int(raw)
            if 1 <= num <= 26:
                codes.append(chr(ord("A") + num - 1))
                continue
        upper = raw.upper()
        if len(upper) == 1 and "A" <= upper <= "Z":
            codes.append(upper)
            continue
        if option_count == 2 and raw in ["正确", "对", "TRUE", "T"]:
            codes.append("A")
            continue
        if option_count == 2 and raw in ["错误", "错", "FALSE", "F"]:
            codes.append("B")
    return sorted(set(codes)), raw_values


def map_question_type(item: dict[str, Any], option_count: int, answer_code_count: int) -> str:
    """
    映射题型。

    :param item: 题目数据
    :param option_count: 选项数
    :param answer_code_count: 答案 code 数
    :return:
    """
    teach = str(item.get("teachType") or "").strip()
    if "多选" in teach or "不定项" in teach:
        return "multiple"
    if "判断" in teach:
        return "judgement"
    if "填空" in teach:
        return "fill"
    if "简答" in teach or "论述" in teach:
        return "shortAnswer"
    if "单选" in teach:
        return "single"
    if option_count > 0:
        if answer_code_count > 1:
            return "multiple"
        return "single"
    return "shortAnswer"


def build_analysis_items(item: dict[str, Any], answer_data: dict[str, Any]) -> list[UpsertQuestionAnalysisItem]:
    """
    组装解析版本数据。

    :param item: 题目数据
    :param answer_data: 答案结构
    :return:
    """
    def join_text(text_a: Any, text_b: Any) -> str:
        left = str(text_a or "").strip()
        right = str(text_b or "").strip()
        if left and right:
            return f"{left}\n\n{right}"
        if left:
            return left
        return right

    items: list[UpsertQuestionAnalysisItem] = []
    default_content = join_text(item.get("analysis"), item.get("extend")) or "<p>暂无解析</p>"
    items.append(
        UpsertQuestionAnalysisItem(
            type="official",
            version_no=1,
            is_default=True,
            answer_data=answer_data,
            content=default_content,
            status=10,
        )
    )

    scenes = item.get("multiSceneAnalysis")
    if not isinstance(scenes, list):
        return items

    for scene in scenes:
        if not isinstance(scene, dict):
            continue
        scene_id = scene.get("questionScene")
        if not isinstance(scene_id, int):
            continue
        content = join_text(scene.get("analysis"), scene.get("extend"))
        if not content:
            continue
        version = scene.get("version")
        if not isinstance(version, int) or version <= 0:
            version = 1
        items.append(
            UpsertQuestionAnalysisItem(
                type=f"scene_{scene_id}",
                version_no=version,
                is_default=False,
                answer_data=answer_data,
                content=content,
                status=10,
            )
        )
    return items


def build_option_items(item: dict[str, Any]) -> list[UpsertQuestionOptionItem]:
    """
    组装选项结构。

    :param item: 题目数据
    :return:
    """
    choices = item.get("choices")
    if not isinstance(choices, list):
        return []
    out: list[UpsertQuestionOptionItem] = []
    for index, raw in enumerate(choices):
        content = str(raw or "").strip()
        if not content:
            continue
        out.append(
            UpsertQuestionOptionItem(
                option_code=chr(ord("A") + index),
                content=content,
                sort_order=index,
                is_active=True,
            )
        )
    return out


def normalize_material_content(content: str) -> str:
    """
    标准化材料文本。

    :param content: 原始内容
    :return:
    """
    raw = str(content or "").strip()
    if not raw:
        return ""
    return re.sub(r"\s+", " ", raw)


def build_material_hash(content: str) -> str:
    """
    计算材料哈希。

    :param content: 原始内容
    :return:
    """
    normalized = normalize_material_content(content)
    return hashlib.sha1(normalized.encode("utf-8")).hexdigest()


def extract_material_contents(item: dict[str, Any]) -> list[str]:
    """
    提取材料内容，自动去重。

    :param item: 题目数据
    :return:
    """
    raw_items: list[str] = []

    raw_material = item.get("material")
    if isinstance(raw_material, str) and raw_material.strip():
        raw_items.append(raw_material.strip())

    raw_materials = item.get("materials")
    if isinstance(raw_materials, list):
        for node in raw_materials:
            if isinstance(node, str):
                text_value = node.strip()
                if text_value:
                    raw_items.append(text_value)
                continue
            if not isinstance(node, dict):
                continue
            for key in ["content", "material", "stem", "text", "body"]:
                value = node.get(key)
                if isinstance(value, str) and value.strip():
                    raw_items.append(value.strip())
                    break

    out: list[str] = []
    seen_hash: set[str] = set()
    for content in raw_items:
        material_hash = build_material_hash(content)
        if not material_hash:
            continue
        if material_hash in seen_hash:
            continue
        seen_hash.add(material_hash)
        out.append(content)
    return out


def parse_year(value: Any) -> int | None:
    """
    解析年份。

    :param value: 原始值
    :return:
    """
    try:
        year = int(value)
    except (TypeError, ValueError):
        return None
    if 1900 <= year <= 2100:
        return year
    return None


def build_material_source(item: dict[str, Any], fallback: str) -> str | None:
    """
    解析材料来源。

    :param item: 题目数据
    :param fallback: 兜底来源
    :return:
    """
    source = str(item.get("from") or "").strip()
    if source:
        return source[:255]
    fallback_text = str(fallback or "").strip()
    if fallback_text:
        return fallback_text[:255]
    return None


def pick_chapter_name(item: dict[str, Any], module_name: str | None) -> str | None:
    """
    从模块和知识点推断章节。

    :param item: 题目数据
    :param module_name: 模块名
    :return:
    """
    chapter = normalize_chapter_name(module_name)
    if chapter:
        return chapter

    point_list = item.get("pointList")
    if isinstance(point_list, list):
        for node in point_list:
            if not isinstance(node, dict):
                continue
            names = node.get("pointsName")
            if not isinstance(names, list):
                continue
            for name in names:
                chapter = normalize_chapter_name(str(name))
                if chapter:
                    return chapter

    point_names = item.get("pointsName")
    if isinstance(point_names, list):
        for name in point_names:
            chapter = normalize_chapter_name(str(name))
            if chapter:
                return chapter
    return None


def build_qid_bank_code_map(
    *,
    paper_map: dict[int, ImportPaperData],
    paper_code_prefix: str,
) -> dict[int, str]:
    """
    Build qid to bank code mapping.

    :param paper_map: selected paper map
    :param paper_code_prefix: paper code prefix
    :return:
    """
    qid_bank_map: dict[int, str] = {}
    for pid in sorted(paper_map):
        code = f"{paper_code_prefix.upper()}_{pid}"
        for qid in paper_map[pid].qids:
            if qid not in qid_bank_map:
                qid_bank_map[qid] = code
    return qid_bank_map


def resolve_row_bank_code(
    *,
    row: dict[str, Any],
    qid: int,
    qid_bank_map: dict[int, str],
    default_bank_code: str,
) -> str:
    """
    Resolve bank code for question row.

    :param row: question row payload
    :param qid: question id
    :param qid_bank_map: qid to bank code map
    :param default_bank_code: fallback bank code
    :return:
    """
    direct_code = qid_bank_map.get(qid)
    if direct_code:
        return direct_code

    children = row.get("childrens")
    if isinstance(children, list):
        for child in children:
            if not isinstance(child, dict):
                continue
            child_id = child.get("id")
            if not isinstance(child_id, int):
                continue
            child_code = qid_bank_map.get(child_id)
            if child_code:
                return child_code

    parent_id = row.get("parent")
    if isinstance(parent_id, int) and parent_id > 0:
        parent_code = qid_bank_map.get(parent_id)
        if parent_code:
            return parent_code
    return default_bank_code


def sanitize_field_path(value: str) -> str:
    """
    Build compact field path segment.

    :param value: raw field path
    :return:
    """
    text_value = str(value or "").strip().lower()
    if not text_value:
        return "content"
    safe = re.sub(r"[^a-z0-9_-]+", "_", text_value).strip("_")
    if not safe:
        return "content"
    return safe[:80]


async def mirror_nested_html_value(
    *,
    mirror: QbankImageMirror,
    value: Any,
    bank_code: str,
    question_id: int,
    field_path: str,
) -> tuple[Any, bool]:
    """
    Mirror html images for nested payload value.

    :param mirror: mirror service
    :param value: source value
    :param bank_code: bank code
    :param question_id: question id
    :param field_path: field path marker
    :return:
    """
    if isinstance(value, str):
        if "<img" not in value.lower():
            return value, False
        mirrored = await mirror.mirror_html(
            html=value,
            bank_code=bank_code,
            question_id=question_id,
            field_name=sanitize_field_path(field_path),
        )
        return mirrored, mirrored != value

    if isinstance(value, list):
        changed = False
        result: list[Any] = list(value)
        for index, item in enumerate(value, start=1):
            next_item, item_changed = await mirror_nested_html_value(
                mirror=mirror,
                value=item,
                bank_code=bank_code,
                question_id=question_id,
                field_path=f"{field_path}_{index}",
            )
            if not item_changed:
                continue
            result[index - 1] = next_item
            changed = True
        if changed:
            return result, True
        return value, False

    if isinstance(value, dict):
        changed = False
        result = dict(value)
        for key, item in value.items():
            next_item, item_changed = await mirror_nested_html_value(
                mirror=mirror,
                value=item,
                bank_code=bank_code,
                question_id=question_id,
                field_path=f"{field_path}_{sanitize_field_path(str(key))}",
            )
            if not item_changed:
                continue
            result[key] = next_item
            changed = True
        if changed:
            return result, True
        return value, False

    return value, False


async def mirror_question_rows(
    *,
    args: SimpleNamespace,
    question_rows: dict[int, dict[str, Any]],
    paper_map: dict[int, ImportPaperData],
) -> None:
    """
    Mirror external images in question payload before db import.

    :param args: import args
    :param question_rows: fetched question payload map
    :param paper_map: selected paper map
    :return:
    """
    if not args.mirror_images:
        return
    if args.dry_run:
        print("[MIRROR] dry_run=true, skip external image mirror to avoid OSS side effects")
        return
    if not question_rows:
        return

    qid_bank_map = build_qid_bank_code_map(paper_map=paper_map, paper_code_prefix=args.paper_code_prefix)
    if not qid_bank_map:
        return

    default_bank_code = next(iter(qid_bank_map.values()))
    mirror = QbankImageMirror(
        cache_file=Path(args.mirror_cache_file),
        request_timeout=float(args.mirror_timeout),
        object_expire_days=args.mirror_object_expire_days,
        sample_limit=int(getattr(args, "mirror_sample_limit", 0)),
        safe_interval_seconds=float(getattr(args, "mirror_safe_interval", 2.5)),
        safe_interval_jitter_seconds=float(getattr(args, "mirror_safe_jitter", 0.5)),
    )

    async with async_db_session() as db:
        await mirror.initialize(db)

    print(f"[MIRROR] start rows={len(question_rows)}")
    changed_rows = 0
    total_rows = len(question_rows)
    top_level_fields = ("stem", "analysis", "extend", "material", "choices", "materials", "multiSceneAnalysis")

    for index, qid in enumerate(sorted(question_rows), start=1):
        row = question_rows.get(qid)
        if not isinstance(row, dict):
            continue
        bank_code = resolve_row_bank_code(
            row=row,
            qid=qid,
            qid_bank_map=qid_bank_map,
            default_bank_code=default_bank_code,
        )

        row_changed = False
        for field_name in top_level_fields:
            if field_name not in row:
                continue
            mirrored_value, changed = await mirror_nested_html_value(
                mirror=mirror,
                value=row.get(field_name),
                bank_code=bank_code,
                question_id=qid,
                field_path=field_name,
            )
            if not changed:
                continue
            row[field_name] = mirrored_value
            row_changed = True

        if row_changed:
            changed_rows += 1

        if index % 10 == 0 or index == total_rows:
            print(
                "[MIRROR]"
                f" done={index}/{total_rows}"
                f" changed_rows={changed_rows}"
                f" scanned_images={mirror.stats.scanned_images}"
                f" replaced={mirror.stats.replaced_images}"
                f" uploaded={mirror.stats.uploaded_images}"
                f" cache_hit={mirror.stats.cache_hit}"
                f" failed={mirror.stats.failed_images}"
                f" public={mirror.stats.public_urls}"
                f" signed={mirror.stats.signed_urls}"
                f" unknown={mirror.stats.unknown_urls}"
            )

    mirror.save_cache()
    if mirror.rewrite_samples:
        print(f"[MIRROR_SAMPLE] count={len(mirror.rewrite_samples)}")
        for index, sample in enumerate(mirror.rewrite_samples, start=1):
            print(
                "[MIRROR_SAMPLE]"
                f" #{index}"
                f" field={sample.field_name}"
                f" scope={sample.scope_segment}"
                f" cache={'Y' if sample.from_cache else 'N'}"
            )
            print(f"[MIRROR_SAMPLE]   before={sample.source_url}")
            print(f"[MIRROR_SAMPLE]   after ={sample.mirrored_url}")


async def align_question_id_sequence(db) -> None:
    """
    Align study_question id sequence to current max id.

    :param db: db session
    :return:
    """
    try:
        await db.execute(
            sa_text(
                """
                SELECT setval(
                    pg_get_serial_sequence('study_question', 'id'),
                    GREATEST((SELECT COALESCE(MAX(id), 1) FROM study_question), 1),
                    true
                )
                """
            )
        )
        max_id = await db.scalar(select(func.max(Question.id)))
        print(f"[DB] question_id_seq_aligned max_id={int(max_id or 0)}")
    except Exception as exc:
        print(f"[DB][WARN] align question id sequence failed: {exc}")


async def run_question_import_core(args: SimpleNamespace) -> int:
    """
    执行题目导入核心流程。

    :param args: 导入参数
    :return:
    """
    if not args.cookie:
        raise ImportErrorBase("cookie is empty")

    area_ids = [int(x.strip()) for x in args.areas.split(",") if x.strip()]
    pattern = re.compile(args.name_regex)
    paper_map: dict[int, ImportPaperData] = {}

    for area_id in area_ids:
        payload = await fetch_huatu_list(url=args.list_url, cookie=args.cookie, area=area_id, papertype="")
        if isinstance(payload, dict) and payload.get("code") == -1:
            print(f"[PAPER] area={area_id} source=0 matched=0")
            continue
        papers = extract_paper_list(payload)
        matched = 0
        for paper in papers:
            pid = paper.get("id")
            name = str(paper.get("name") or "").strip()
            if not isinstance(pid, int):
                continue
            if not name:
                continue
            if args.paper_id > 0 and pid != args.paper_id:
                continue
            if args.paper_category is not None and paper.get("catgory") != args.paper_category:
                continue
            if not pattern.search(name):
                continue
            qids = parse_qids(paper.get("questions"))
            if not qids:
                continue
            incoming = ImportPaperData(
                paper_id=pid,
                paper_name=name,
                qids=qids,
                qsort=parse_qsort(paper.get("questionSort"), len(qids)),
                modules=parse_modules(paper.get("modules"), len(qids)),
            )
            existing = paper_map.get(pid)
            if existing is None or len(incoming.qids) > len(existing.qids):
                paper_map[pid] = incoming
            matched += 1
        print(f"[PAPER] area={area_id} source={len(papers)} matched={matched}")
        await asyncio.sleep(max(0.0, args.request_interval))
        if args.paper_id > 0 and args.paper_id in paper_map:
            break

    if not paper_map:
        raise ImportErrorBase("no paper matched")

    selected_preview = sorted(
        [(pid, paper_map[pid].paper_name) for pid in paper_map],
        key=lambda item: item[0],
    )
    for pid, name in selected_preview[:10]:
        print(f"[PAPER_SELECTED] id={pid} name={name}")
    if len(selected_preview) > 10:
        print(f"[PAPER_SELECTED] more={len(selected_preview) - 10}")

    if args.max_papers > 0:
        selected_ids = sorted(paper_map.keys())[: args.max_papers]
        paper_map = {pid: paper_map[pid] for pid in selected_ids}

    all_qids: list[int] = []
    seen_qids: set[int] = set()
    for paper in paper_map.values():
        for qid in paper.qids:
            if qid in seen_qids:
                continue
            seen_qids.add(qid)
            all_qids.append(qid)

    if args.max_questions > 0:
        allowed = set(all_qids[: args.max_questions])
        all_qids = [qid for qid in all_qids if qid in allowed]
        for pid, paper in list(paper_map.items()):
            next_qids: list[int] = []
            next_qsort: list[int] = []
            next_modules: list[str | None] = []
            for index, qid in enumerate(paper.qids):
                if qid not in allowed:
                    continue
                next_qids.append(qid)
                next_qsort.append(paper.qsort[index])
                next_modules.append(paper.modules[index])
            if not next_qids:
                paper_map.pop(pid)
                continue
            paper.qids = next_qids
            paper.qsort = next_qsort
            paper.modules = next_modules

    print(f"[CHECK] papers={len(paper_map)} unique_questions={len(all_qids)}")

    cookie_header = sanitize_cookie(args.cookie)
    token = extract_cookie_value(cookie_header, "ht_token")
    headers = {
        "Accept": "application/json, text/plain, */*",
        "Accept-Encoding": "gzip, deflate, br, zstd",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Connection": "keep-alive",
        "Origin": "https://v.huatu.com",
        "Referer": "https://v.huatu.com/",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-site",
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/145.0.0.0 Safari/537.36 Edg/145.0.0.0"
        ),
        "Cookie": cookie_header,
        "terminal": args.terminal,
    }
    if token:
        headers["token"] = token

    question_rows: dict[int, dict[str, Any]] = {}
    async with httpx.AsyncClient(timeout=httpx.Timeout(45.0)) as client:
        chunks = split_chunks(all_qids, args.question_chunk_size)
        for index, chunk in enumerate(chunks, start=1):
            params = {"ids": ",".join(str(x) for x in chunk), "terminal": args.terminal, "appType": args.app_type}
            last_error: Exception | None = None
            for attempt in range(1, 6):
                try:
                    response = await client.get(args.question_url, params=params, headers=headers)
                    response.raise_for_status()
                    question_rows.update(flatten_question_rows(response.json()))
                    last_error = None
                    break
                except Exception as exc:
                    last_error = exc
                    wait_seconds = min(2.0 * attempt, 10.0)
                    print(
                        "[RETRY]"
                        f" batch={index}/{len(chunks)}"
                        f" attempt={attempt}"
                        f" wait={wait_seconds}s"
                        f" error={exc}"
                    )
                    await asyncio.sleep(wait_seconds)
            if last_error is not None:
                raise last_error
            print(f"[QUESTION_FETCH] batch={index}/{len(chunks)} request={len(chunk)} cumulative={len(question_rows)}")
            await asyncio.sleep(max(0.0, args.request_interval))

    print(f"[CHECK] fetched_questions={len(question_rows)} missing={max(0, len(all_qids) - len(question_rows))}")

    await mirror_question_rows(args=args, question_rows=question_rows, paper_map=paper_map)

    material_field_count = 0
    materials_field_count = 0
    material_qid_sample: list[int] = []
    for row in question_rows.values():
        qid = row.get("id")
        raw_material = row.get("material")
        if isinstance(raw_material, str) and raw_material.strip():
            material_field_count += 1
            if isinstance(qid, int):
                material_qid_sample.append(qid)

        raw_materials = row.get("materials")
        if not isinstance(raw_materials, list):
            continue
        has_materials = False
        for node in raw_materials:
            if isinstance(node, str) and node.strip():
                has_materials = True
                break
            if not isinstance(node, dict):
                continue
            for key in ["content", "material", "stem", "text", "body"]:
                value = node.get(key)
                if isinstance(value, str) and value.strip():
                    has_materials = True
                    break
            if has_materials:
                break
        if has_materials:
            materials_field_count += 1

    print(
        "[CHECK]"
        f" material_field_rows={material_field_count}"
        f" materials_field_rows={materials_field_count}"
    )

    if material_qid_sample:
        all_qid_set = set(all_qids)
        in_scope = [qid for qid in material_qid_sample if qid in all_qid_set]
        out_scope = [qid for qid in material_qid_sample if qid not in all_qid_set]
        print(
            "[CHECK]"
            f" material_qids_sample={material_qid_sample[:15]}"
            f" in_scope={len(in_scope)}"
            f" out_scope={len(out_scope)}"
        )
        for qid in material_qid_sample[:5]:
            row = question_rows.get(qid) or {}
            children = row.get("childrens")
            child_ids: list[int] = []
            if isinstance(children, list):
                for node in children:
                    if isinstance(node, dict) and isinstance(node.get("id"), int):
                        child_ids.append(node["id"])
            in_scope_children = [cid for cid in child_ids if cid in all_qid_set]
            print(
                "[CHECK]"
                f" material_parent_qid={qid}"
                f" child_count={len(child_ids)}"
                f" child_in_scope={len(in_scope_children)}"
            )

    parent_ref_count = 0
    parent_with_material_count = 0
    for qid in all_qids:
        row = question_rows.get(qid)
        if not isinstance(row, dict):
            continue
        parent_id = row.get("parent")
        if not isinstance(parent_id, int) or parent_id <= 0:
            continue
        parent_ref_count += 1
        parent_row = question_rows.get(parent_id)
        if not isinstance(parent_row, dict):
            continue
        if extract_material_contents(parent_row):
            parent_with_material_count += 1
    print(
        "[CHECK]"
        f" parent_ref_rows={parent_ref_count}"
        f" parent_with_material_rows={parent_with_material_count}"
    )

    async with async_db_session() as db:
        print("[DB] session_opened")
        try:
            await db.execute(sa_text("SET lock_timeout = '8s'"))
            await db.execute(sa_text("SET statement_timeout = '120s'"))
            print("[DB] timeout_set lock_timeout=8s statement_timeout=120s")
        except Exception as exc:
            print(f"[DB][WARN] set timeout failed: {exc}")

        await align_question_id_sequence(db)

        paper_codes = [f"{args.paper_code_prefix.upper()}_{pid}" for pid in paper_map]
        bank_rows = (await db.execute(select(QuestionBank).where(QuestionBank.code.in_(paper_codes)))).scalars().all()
        bank_map = {row.code: row for row in bank_rows}
        missing_paper_ids = [pid for pid in paper_map if f"{args.paper_code_prefix.upper()}_{pid}" not in bank_map]
        if missing_paper_ids:
            sample = ",".join(str(x) for x in missing_paper_ids[:20])
            raise ImportErrorBase(f"paper bank missing: {sample}")
        print(f"[DB] paper_banks_ok count={len(bank_map)}")

        remote_qid_to_local_id: dict[int, int] = {}
        for paper in paper_map.values():
            bank = bank_map[f"{args.paper_code_prefix.upper()}_{paper.paper_id}"]
            placement_rows = (
                await db.execute(select(QuestionPlacement).where(QuestionPlacement.bank_id == bank.id))
            ).scalars().all()
            placement_qid_by_sort: dict[int, int] = {}
            placement_active_by_sort: dict[int, bool] = {}
            for placement in placement_rows:
                sort_key = int(placement.sort_order or 0)
                local_question_id = int(placement.question_id)
                current_active = placement_active_by_sort.get(sort_key)
                if current_active is None:
                    placement_qid_by_sort[sort_key] = local_question_id
                    placement_active_by_sort[sort_key] = bool(placement.is_active)
                    continue
                if not current_active and placement.is_active:
                    placement_qid_by_sort[sort_key] = local_question_id
                    placement_active_by_sort[sort_key] = True

            for index, remote_qid in enumerate(paper.qids):
                sort_order = paper.qsort[index] if index < len(paper.qsort) else index + 1
                local_question_id = placement_qid_by_sort.get(int(sort_order))
                if not local_question_id:
                    continue
                if remote_qid in remote_qid_to_local_id:
                    continue
                remote_qid_to_local_id[remote_qid] = local_question_id

        question_lookup_ids = set(all_qids)
        question_lookup_ids.update(remote_qid_to_local_id.values())
        existing_questions_by_id: dict[int, Question] = {}
        for chunk in split_chunks(list(question_lookup_ids), 1000):
            stmt = select(Question).where(Question.id.in_(chunk))
            for row in (await db.execute(stmt)).scalars().all():
                existing_questions_by_id[int(row.id)] = row
        print(
            "[DB]"
            f" existing_questions={len(existing_questions_by_id)}"
            f" pre_mapped_qids={len(remote_qid_to_local_id)}"
        )

        source_bank_ids = {
            int(bank.chapter_source_bank_id or bank.id)
            for bank in bank_map.values()
        }
        source_bank_rows = (
            await db.execute(select(QuestionBank).where(QuestionBank.id.in_(list(source_bank_ids))))
        ).scalars().all()
        source_bank_map = {int(bank.id): bank for bank in source_bank_rows}

        chapter_map_by_source_bank_id: dict[int, dict[str, int]] = {}
        source_bank_code_by_id: dict[int, str] = {}
        for source_bank_id in sorted(source_bank_ids):
            source_bank = source_bank_map.get(source_bank_id)
            if source_bank is None:
                raise ImportErrorBase(f"chapter source bank missing: id={source_bank_id}")

            chapter_rows = (
                await db.execute(select(QuestionChapter).where(QuestionChapter.bank_id == source_bank_id))
            ).scalars().all()
            chapter_map: dict[str, int] = {}
            for row in chapter_rows:
                name = normalize_chapter_name(row.name)
                if name:
                    chapter_map[name] = row.id

            source_bank_code = str(source_bank.code or source_bank_id)
            for chapter_name in CANONICAL_CHAPTERS:
                if chapter_name not in chapter_map:
                    raise ImportErrorBase(f"chapter missing under {source_bank_code}: {chapter_name}")

            chapter_map_by_source_bank_id[source_bank_id] = chapter_map
            source_bank_code_by_id[source_bank_id] = source_bank_code
            print(
                "[DB] chapters_ok"
                f" source_bank_id={source_bank_id}"
                f" source_bank_code={source_bank_code}"
                f" count={len(chapter_map)}"
            )

        q_created = 0
        q_updated = 0
        p_created = 0
        p_updated = 0
        p_skipped = 0
        q_missing = 0
        m_created = 0
        m_linked = 0
        m_unlinked = 0
        m_sort_updated = 0

        trace_each_question = args.trace_db or len(all_qids) <= 20
        for idx_q, qid in enumerate(all_qids, start=1):
            row = question_rows.get(qid)
            if row is None:
                q_missing += 1
                continue

            if trace_each_question:
                print(f"[DB][QUESTION] begin idx={idx_q}/{len(all_qids)} qid={qid}")

            options = build_option_items(row)
            answer_codes, raw_answers = parse_answers(row, len(options))
            question_type = map_question_type(row, len(options), len(answer_codes))
            if question_type in ["single", "judgement"]:
                correct_value = answer_codes[0] if answer_codes else (raw_answers[0] if raw_answers else "")
                answer_data = {"correct": correct_value}
            elif question_type == "multiple":
                answer_data = {"correct": answer_codes if answer_codes else raw_answers}
            else:
                answer_data = {"correct": raw_answers}

            stem = str(row.get("stem") or "").strip() or "<p>暂无题干</p>"
            score = to_decimal(row.get("score"))
            if score is None or score <= Decimal("0"):
                score = Decimal("1")
            else:
                score = score.quantize(Decimal("0.01"))
            difficult = to_decimal(row.get("difficult")) or to_decimal(row.get("difficultyScore")) or Decimal("5")
            if difficult <= Decimal("3"):
                difficulty = "easy"
            elif difficult <= Decimal("7"):
                difficulty = "medium"
            else:
                difficulty = "hard"
            status = 10 if int(row.get("status") or 0) == 2 else 0

            points: list[str] = []
            point_list = row.get("pointList")
            if isinstance(point_list, list):
                for node in point_list:
                    if not isinstance(node, dict):
                        continue
                    names = node.get("pointsName")
                    if not isinstance(names, list):
                        continue
                    for name in names:
                        point_name = str(name).strip()
                        if not point_name:
                            continue
                        if point_name in points:
                            continue
                        points.append(point_name)

            mapped_local_id = remote_qid_to_local_id.get(qid)
            qobj = None
            if mapped_local_id:
                qobj = existing_questions_by_id.get(mapped_local_id)
            if qobj is None:
                qobj = existing_questions_by_id.get(qid)
            if qobj is None:
                qobj = Question(
                    type=question_type,
                    stem=stem,
                    difficulty=difficulty,
                    default_score=score,
                    knowledge_point=points or None,
                    content_status=status,
                    created_by=args.created_by,
                )
                db.add(qobj)
                await db.flush()
                existing_questions_by_id[int(qobj.id)] = qobj
                q_created += 1
            else:
                qobj.type = question_type
                qobj.stem = stem
                qobj.difficulty = difficulty
                qobj.default_score = score
                qobj.knowledge_point = points or None
                qobj.content_status = status
                qobj.updated_by = args.created_by
                q_updated += 1

            local_question_id = int(qobj.id)
            remote_qid_to_local_id[qid] = local_question_id
            existing_questions_by_id[local_question_id] = qobj

            if trace_each_question:
                print(f"[DB][QUESTION] flush_question qid={qid}")
            await db.flush()

            if trace_each_question:
                print(f"[DB][QUESTION] replace_options qid={qid}")
            await question_option_dao.replace_by_items(
                db,
                question_id=local_question_id,
                items=options,
                option_content_crud=option_content_dao,
            )

            if trace_each_question:
                print(f"[DB][QUESTION] replace_analyses qid={qid}")
            await question_analysis_dao.replace_versions(
                db,
                question_id=local_question_id,
                items=build_analysis_items(row, answer_data),
                user_id=args.created_by,
            )
            if trace_each_question:
                print(f"[DB][QUESTION] done qid={qid}")

            if idx_q % 20 == 0 or idx_q == len(all_qids):
                print(
                    "[DB][QUESTION]"
                    f" done={idx_q}/{len(all_qids)}"
                    f" created={q_created}"
                    f" updated={q_updated}"
                    f" missing={q_missing}"
                )

        for idx_paper, paper in enumerate(paper_map.values(), start=1):
            bank = bank_map[f"{args.paper_code_prefix.upper()}_{paper.paper_id}"]
            source_bank_id = int(bank.chapter_source_bank_id or bank.id)
            chapter_map = chapter_map_by_source_bank_id.get(source_bank_id)
            if chapter_map is None:
                source_bank_code = source_bank_code_by_id.get(source_bank_id, str(source_bank_id))
                raise ImportErrorBase(f"chapter map missing for source bank: {source_bank_code}")

            material_stmt = select(QuestionMaterial).where(
                QuestionMaterial.bank_id == bank.id,
                QuestionMaterial.is_active.is_(True),
            )
            bank_material_rows = (await db.execute(material_stmt)).scalars().all()
            material_hash_map: dict[str, int] = {}
            for material_row in bank_material_rows:
                material_hash = build_material_hash(material_row.content)
                if not material_hash:
                    continue
                if material_hash in material_hash_map:
                    continue
                material_hash_map[material_hash] = material_row.id
            next_material_sort = len(bank_material_rows)

            placement_stmt = select(QuestionPlacement).where(QuestionPlacement.bank_id == bank.id)
            existing_placements = (await db.execute(placement_stmt)).scalars().all()
            placement_map_by_sort: dict[int, QuestionPlacement] = {}
            bank_question_ids: list[int] = []
            for item in existing_placements:
                bank_question_ids.append(int(item.question_id))
                sort_key = int(item.sort_order or 0)
                current = placement_map_by_sort.get(sort_key)
                if current is None:
                    placement_map_by_sort[sort_key] = item
                    continue
                if not current.is_active and item.is_active:
                    placement_map_by_sort[sort_key] = item

            existing_rel_map: dict[int, dict[int, int]] = {}
            if bank_question_ids:
                rel_stmt = (
                    select(
                        question_material_relation.c.question_id,
                        question_material_relation.c.material_id,
                        question_material_relation.c.sort_order,
                    )
                    .join(QuestionMaterial, QuestionMaterial.id == question_material_relation.c.material_id)
                    .where(
                        question_material_relation.c.question_id.in_(bank_question_ids),
                        QuestionMaterial.bank_id == bank.id,
                    )
                )
                existing_rel_rows = await db.execute(rel_stmt)
                for qid, mid, sort_order in existing_rel_rows.all():
                    qmap = existing_rel_map.setdefault(int(qid), {})
                    qmap[int(mid)] = int(sort_order or 0)
            desired_rel_map: dict[int, list[int]] = {}

            for index, qid in enumerate(paper.qids):
                row = question_rows.get(qid)
                if row is None:
                    p_skipped += 1
                    continue
                local_qid = remote_qid_to_local_id.get(qid)
                if not local_qid:
                    p_skipped += 1
                    continue
                module_name = paper.modules[index] if index < len(paper.modules) else None
                chapter_name = pick_chapter_name(row, module_name)
                chapter_id = chapter_map.get(chapter_name) if chapter_name else None
                sort_order = paper.qsort[index] if index < len(paper.qsort) else index + 1
                placement_score = to_decimal(row.get("score"))
                if placement_score is not None and placement_score <= Decimal("0"):
                    placement_score = None

                placement = placement_map_by_sort.get(sort_order)
                if placement is None:
                    db.add(
                        QuestionPlacement(
                            question_id=local_qid,
                            bank_id=bank.id,
                            chapter_id=chapter_id,
                            sort_order=sort_order,
                            is_active=True,
                            score=placement_score,
                            review_status=10,
                            scene_mask=None,
                            created_by=args.created_by,
                        )
                    )
                    p_created += 1
                else:
                    placement.question_id = local_qid
                    placement.chapter_id = chapter_id
                    placement.sort_order = sort_order
                    placement.is_active = True
                    placement.score = placement_score
                    placement.review_status = 10
                    placement.scene_mask = None
                    placement.updated_by = args.created_by
                    p_updated += 1

                material_source_row = row
                material_contents = extract_material_contents(row)
                if not material_contents:
                    parent_id = row.get("parent")
                    if isinstance(parent_id, int) and parent_id > 0:
                        parent_row = question_rows.get(parent_id)
                        if isinstance(parent_row, dict):
                            parent_material_contents = extract_material_contents(parent_row)
                            if parent_material_contents:
                                material_contents = parent_material_contents
                                material_source_row = parent_row

                material_ids: list[int] = []
                for material_content in material_contents:
                    material_hash = build_material_hash(material_content)
                    material_id = material_hash_map.get(material_hash)
                    if material_id is None:
                        next_material_sort += 1
                        material_obj = QuestionMaterial(
                            bank_id=bank.id,
                            title=f"{paper.paper_name} 材料 {next_material_sort}",
                            content=material_content,
                            category_id=None,
                            source=build_material_source(material_source_row, paper.paper_name),
                            year=parse_year(material_source_row.get("year")),
                            sort_order=next_material_sort,
                            is_active=True,
                            created_by=args.created_by,
                        )
                        db.add(material_obj)
                        await db.flush()
                        material_id = material_obj.id
                        material_hash_map[material_hash] = material_id
                        m_created += 1
                    material_ids.append(material_id)

                desired_rel_map[local_qid] = material_ids

            for local_qid, desired_ids in desired_rel_map.items():
                desired_set = set(desired_ids)
                current_rel_map = existing_rel_map.get(local_qid, {})
                current_set = set(current_rel_map.keys())

                for order_index, material_id in enumerate(desired_ids, start=1):
                    if material_id in current_set:
                        old_order = current_rel_map.get(material_id, 0)
                        if old_order != order_index:
                            await db.execute(
                                sa_update(question_material_relation)
                                .where(
                                    question_material_relation.c.question_id == local_qid,
                                    question_material_relation.c.material_id == material_id,
                                )
                                .values(sort_order=order_index)
                            )
                            m_sort_updated += 1
                        continue
                    await db.execute(
                        question_material_relation.insert().values(
                            question_id=local_qid,
                            material_id=material_id,
                            sort_order=order_index,
                        )
                    )
                    m_linked += 1

                remove_ids = list(current_set - desired_set)
                if remove_ids:
                    await db.execute(
                        sa_delete(question_material_relation).where(
                            question_material_relation.c.question_id == local_qid,
                            question_material_relation.c.material_id.in_(remove_ids),
                        )
                    )
                    m_unlinked += len(remove_ids)

            print(
                "[DB][PLACEMENT]"
                f" done={idx_paper}/{len(paper_map)}"
                f" bank_id={bank.id}"
                f" p_created={p_created}"
                f" p_updated={p_updated}"
                f" p_skipped={p_skipped}"
                f" m_created={m_created}"
                f" m_linked={m_linked}"
                f" m_unlinked={m_unlinked}"
                f" m_sort_updated={m_sort_updated}"
            )

        await db.flush()
        if args.dry_run:
            print("[DB] rollback")
            await db.rollback()
        else:
            print("[DB] commit")
            await db.commit()

    print(
        "[DONE]"
        f" papers={len(paper_map)}"
        f" unique_qids={len(all_qids)}"
        f" q_created={q_created}"
        f" q_updated={q_updated}"
        f" q_missing={q_missing}"
        f" p_created={p_created}"
        f" p_updated={p_updated}"
        f" p_skipped={p_skipped}"
        f" m_created={m_created}"
        f" m_linked={m_linked}"
        f" m_unlinked={m_unlinked}"
        f" m_sort_updated={m_sort_updated}"
        f" dry_run={args.dry_run}"
    )
    return 0


async def clear_question_locks() -> list[int]:
    """清理导入相关锁会话。"""
    sql = """
    select distinct a.pid
    from pg_stat_activity a
    join pg_locks l on l.pid = a.pid
    left join pg_class c on c.oid = l.relation
    where a.datname = current_database()
      and a.pid <> pg_backend_pid()
      and c.relname in (
          'study_question',
          'study_question_placement',
          'study_question_option',
          'study_option_content',
          'study_question_analysis'
      )
      and (
          a.state = 'idle in transaction'
          or (a.wait_event_type = 'Lock')
      )
    order by a.pid
    """

    async with async_db_session() as db:
        pids = [int(x) for x in (await db.execute(sa_text(sql))).scalars().all()]
        for pid in pids:
            await db.execute(sa_text("select pg_terminate_backend(:pid)"), {"pid": pid})
    return pids


async def verify_paper(paper_id: int) -> None:
    """
    校验单卷本地落库完整性。

    :param paper_id: 试卷 ID
    :return:
    """
    code = f"PAPER_{paper_id}"
    async with async_db_session() as db:
        bank_row = (
            await db.execute(
                sa_text(
                    """
                    select id, name, chapter_source_bank_id
                    from study_question_bank
                    where code = :code
                    limit 1
                    """
                ),
                {"code": code},
            )
        ).first()
        if not bank_row:
            print(f"[校验] 本地未找到试卷 {code}")
            return

        bank_id = int(bank_row.id)
        source_bank_id = int(bank_row.chapter_source_bank_id or bank_id)
        result = (
            await db.execute(
                sa_text(
                    """
                    select
                        (select count(*) from study_question_placement where bank_id = :bank_id) as placement_count,
                        (
                            select count(distinct question_id)
                            from study_question_placement
                            where bank_id = :bank_id
                        ) as distinct_question_count,
                        (
                            select count(*)
                            from study_question_material
                            where bank_id = :bank_id and is_active = true
                        ) as material_count,
                        (
                            select count(*)
                            from study_question_material_relation r
                            join study_question_material m on m.id = r.material_id
                            where m.bank_id = :bank_id and m.is_active = true
                        ) as material_relation_count,
                        (
                            select count(*)
                            from study_question_placement p
                            left join study_question q on q.id = p.question_id
                            where p.bank_id = :bank_id and q.id is null
                        ) as question_missing,
                        (
                            select count(*)
                            from study_question_placement
                            where bank_id = :bank_id and chapter_id is null
                        ) as null_chapter,
                        (
                            select count(*)
                            from study_question_placement p
                            join study_question_chapter c on c.id = p.chapter_id
                            where p.bank_id = :bank_id and c.bank_id <> :source_bank_id
                        ) as bad_chapter
                    """
                ),
                {"bank_id": bank_id, "source_bank_id": source_bank_id},
            )
        ).first()

    print(f"[校验] 试卷 id={paper_id} bank_id={bank_id} name={bank_row.name}")
    print(
        "[校验]"
        f" 挂载={result.placement_count}"
        f" 去重题数={result.distinct_question_count}"
        f" 材料数={result.material_count}"
        f" 材料关联数={result.material_relation_count}"
        f" 缺失题目={result.question_missing}"
        f" 空章节={result.null_chapter}"
        f" 错章节={result.bad_chapter}"
    )


async def build_incremental_plan(
    area_nodes: list[AreaNode],
    name_regex: str,
) -> tuple[list[RemotePaper], list[RemotePaper]]:
    """
    对比远程和本地，生成增量导入计划。

    :param area_nodes: 区域列表
    :param name_regex: 名称正则
    :return:
    """
    remote_papers = await fetch_remote_papers(area_nodes, name_regex)
    if not remote_papers:
        return [], []

    paper_ids = sorted({x.paper_id for x in remote_papers})
    codes = [f"PAPER_{pid}" for pid in paper_ids]
    remote_by_id = {x.paper_id: x for x in remote_papers}

    async with async_db_session() as db:
        bank_rows = (
            await db.execute(select(QuestionBank.id, QuestionBank.code).where(QuestionBank.code.in_(codes)))
        ).all()
        bank_id_by_paper: dict[int, int] = {}
        for bank_id, code in bank_rows:
            try:
                paper_id = int(str(code).split("_", 1)[1])
            except Exception:
                continue
            bank_id_by_paper[paper_id] = int(bank_id)

        placement_count_by_bank: dict[int, int] = {}
        if bank_id_by_paper:
            grouped = (
                await db.execute(
                    select(QuestionPlacement.bank_id, func.count(QuestionPlacement.id))
                    .where(QuestionPlacement.bank_id.in_(list(bank_id_by_paper.values())))
                    .group_by(QuestionPlacement.bank_id)
                )
            ).all()
            placement_count_by_bank = {int(bank_id): int(count) for bank_id, count in grouped}

    missing_bank: list[RemotePaper] = []
    need_import: list[RemotePaper] = []
    for pid in paper_ids:
        paper = remote_by_id[pid]
        bank_id = bank_id_by_paper.get(pid)
        if bank_id is None:
            missing_bank.append(paper)
            continue
        current_count = placement_count_by_bank.get(bank_id, 0)
        if current_count < paper.qcount:
            need_import.append(paper)

    return missing_bank, need_import

async def fetch_local_empty_paper_banks(name_regex: str) -> list[LocalEmptyPaperBank]:
    """
    Scan local paper banks that currently have no valid questions.

    :param name_regex: paper name regex
    :return:
    """
    pattern = re.compile(name_regex)
    sql = sa_text(
        """
        select
            b.id as bank_id,
            b.code as code,
            b.name as name,
            count(p.id)::bigint as placement_count,
            count(distinct q.id)::bigint as distinct_question_count
        from study_question_bank b
        left join study_question_placement p on p.bank_id = b.id
        left join study_question q on q.id = p.question_id
        where b.code like 'PAPER_%'
        group by b.id, b.code, b.name
        having count(distinct q.id) = 0
        order by b.id
        """
    )

    async with async_db_session() as db:
        rows = (await db.execute(sql)).mappings().all()

    result: list[LocalEmptyPaperBank] = []
    for row in rows:
        code = str(row["code"] or "").strip()
        name = str(row["name"] or "").strip()
        if not code or not name:
            continue
        if not pattern.search(name):
            continue
        try:
            paper_id = int(code.split("_", 1)[1])
        except Exception:
            continue
        result.append(
            LocalEmptyPaperBank(
                bank_id=int(row["bank_id"]),
                paper_id=paper_id,
                code=code,
                name=name,
                placement_count=int(row["placement_count"] or 0),
                distinct_question_count=int(row["distinct_question_count"] or 0),
            )
        )
    return result


async def fetch_local_missing_material_paper_banks(name_regex: str) -> list[LocalMissingMaterialPaperBank]:
    """
    Scan local paper banks that currently have questions but no active materials.

    :param name_regex: paper name regex
    :return:
    """
    pattern = re.compile(name_regex)
    sql = sa_text(
        """
        select
            b.id as bank_id,
            b.code as code,
            b.name as name,
            count(distinct p.id)::bigint as placement_count,
            count(distinct q.id)::bigint as distinct_question_count,
            count(distinct m.id)::bigint as material_count
        from study_question_bank b
        left join study_question_placement p on p.bank_id = b.id
        left join study_question q on q.id = p.question_id
        left join study_question_material m on m.bank_id = b.id and m.is_active = true
        where b.code like 'PAPER_%'
        group by b.id, b.code, b.name
        having count(distinct q.id) > 0 and count(distinct m.id) = 0
        order by b.id
        """
    )

    async with async_db_session() as db:
        rows = (await db.execute(sql)).mappings().all()

    result: list[LocalMissingMaterialPaperBank] = []
    for row in rows:
        code = str(row["code"] or "").strip()
        name = str(row["name"] or "").strip()
        if not code or not name:
            continue
        if not pattern.search(name):
            continue
        try:
            paper_id = int(code.split("_", 1)[1])
        except Exception:
            continue
        result.append(
            LocalMissingMaterialPaperBank(
                bank_id=int(row["bank_id"]),
                paper_id=paper_id,
                code=code,
                name=name,
                placement_count=int(row["placement_count"] or 0),
                distinct_question_count=int(row["distinct_question_count"] or 0),
                material_count=int(row["material_count"] or 0),
            )
        )
    return result


async def build_empty_bank_repair_plan(
    area_nodes: list[AreaNode],
    name_regex: str,
) -> tuple[list[LocalEmptyPaperBank], list[RemotePaper], list[LocalEmptyPaperBank]]:
    """
    Build targeted repair plan for local empty paper banks.

    :param area_nodes: area list
    :param name_regex: paper name regex
    :return:
    """
    local_empty_banks = await fetch_local_empty_paper_banks(name_regex)
    if not local_empty_banks:
        return [], [], []

    remote_papers = await fetch_remote_papers(area_nodes, name_regex)
    remote_by_id = {paper.paper_id: paper for paper in remote_papers}

    need_import: list[RemotePaper] = []
    missing_remote: list[LocalEmptyPaperBank] = []
    for bank in local_empty_banks:
        remote_paper = remote_by_id.get(bank.paper_id)
        if remote_paper is None:
            missing_remote.append(bank)
            continue
        need_import.append(remote_paper)

    return local_empty_banks, need_import, missing_remote


async def build_missing_material_repair_plan(
    area_nodes: list[AreaNode],
    name_regex: str,
    target_paper_id: int = 0,
) -> tuple[list[LocalMissingMaterialPaperBank], list[RemotePaper], list[LocalMissingMaterialPaperBank]]:
    """
    Build targeted repair plan for local paper banks with missing materials.

    :param area_nodes: area list
    :param name_regex: paper name regex
    :return:
    """
    local_missing_banks = await fetch_local_missing_material_paper_banks(name_regex)
    if not local_missing_banks:
        return [], [], []

    if target_paper_id > 0:
        local_missing_banks = [bank for bank in local_missing_banks if bank.paper_id == target_paper_id]
        if not local_missing_banks:
            return [], [], []

    remote_papers = await fetch_remote_papers(area_nodes, name_regex)
    remote_by_id = {paper.paper_id: paper for paper in remote_papers}

    need_import: list[RemotePaper] = []
    missing_remote: list[LocalMissingMaterialPaperBank] = []
    for bank in local_missing_banks:
        remote_paper = remote_by_id.get(bank.paper_id)
        if remote_paper is None:
            missing_remote.append(bank)
            continue
        need_import.append(remote_paper)

    return local_missing_banks, need_import, missing_remote


async def run_empty_bank_repair() -> None:
    """Targeted import for local empty paper banks."""
    areas = await select_areas()
    name_regex = ask("输入试卷关键词正则（为空=全部）", ".*")
    dry_run = ask_yes_no("是否 DryRun（仅演练不落库）", False)
    mirror_images = ask_yes_no("是否启用外链图片镜像到 OSS", False)
    mirror_safe_interval = 2.5
    if mirror_images:
        mirror_safe_interval = ask_float("图片请求安全间隔秒数（建议 2-5）", 2.5)
    max_banks = ask_int("本次最多补录多少套空题库（0=不限）", 0)

    local_empty_banks, need_import, missing_remote = await build_empty_bank_repair_plan(areas, name_regex)
    print(
        f"[空题库补录] 本地空题库={len(local_empty_banks)} "
        f"可匹配远程={len(need_import)} 未匹配远程={len(missing_remote)}"
    )

    if local_empty_banks:
        print("[空题库补录] 本地空题库样本:")
        for bank in local_empty_banks[:50]:
            print(
                f"  - code={bank.code} bank_id={bank.bank_id} "
                f"placements={bank.placement_count} questions={bank.distinct_question_count} {bank.name}"
            )
        if len(local_empty_banks) > 50:
            print(f"  ... 其余 {len(local_empty_banks) - 50} 条未展示")

    if missing_remote:
        print("[空题库补录] 以下本地空题库未在当前区域/关键词下匹配到远程试卷:")
        for bank in missing_remote[:50]:
            print(f"  - code={bank.code} bank_id={bank.bank_id} {bank.name}")
        if len(missing_remote) > 50:
            print(f"  ... 其余 {len(missing_remote) - 50} 条未展示")

    if not need_import:
        print("[空题库补录] 没有可补录的试卷。")
        return

    if max_banks > 0:
        need_import = need_import[:max_banks]

    print("[空题库补录] 准备补录试卷:")
    for paper in need_import[:50]:
        print(f"  - [{paper.area_name}] paper_id={paper.paper_id} qcount={paper.qcount} {paper.name}")
    if len(need_import) > 50:
        print(f"  ... 其余 {len(need_import) - 50} 条未展示")

    if not ask_yes_no("是否继续执行空题库补录", True):
        print("已取消。")
        return

    success_count = 0
    for index, paper in enumerate(need_import, start=1):
        print(
            f"[空题库补录] {index}/{len(need_import)} 开始 "
            f"area={paper.area_name}(id={paper.area_id}) paper_id={paper.paper_id}"
        )
        pids = await clear_question_locks()
        if pids:
            print(f"[空题库补录] 清理锁会话: {pids}")

        args = build_import_args(
            areas=[paper.area_id],
            name_regex=".*",
            dry_run=dry_run,
            mirror_images=mirror_images,
            paper_id=paper.paper_id,
            max_papers=0,
            max_questions=0,
            mirror_safe_interval=mirror_safe_interval,
        )
        try:
            await run_question_import_core(args)
            success_count += 1
            print(f"[空题库补录] 完成 paper_id={paper.paper_id}")
            if not dry_run:
                await verify_paper(paper.paper_id)
        except Exception as exc:
            print(f"[空题库补录] 失败 paper_id={paper.paper_id} error={exc}")

    print(f"[空题库补录] 完成成功数={success_count}/{len(need_import)}")


async def run_missing_material_repair() -> None:
    """Targeted import for local paper banks with missing materials."""
    areas = await select_areas()
    name_regex = ask("输入试卷关键词正则（为空=全部）", ".*")
    target_paper_id = ask_int("仅补录指定 paper_id（0=按规则扫描全部）", 0)
    dry_run = ask_yes_no("是否 DryRun（仅演练不落库）", False)
    mirror_images = ask_yes_no("是否启用外链图片镜像到 OSS", False)
    mirror_safe_interval = 2.5
    if mirror_images:
        mirror_safe_interval = ask_float("图片请求安全间隔秒数（建议 2-5）", 2.5)
    max_banks = ask_int("本次最多补录多少套缺材料题库（0=不限）", 0)

    local_missing_banks, need_import, missing_remote = await build_missing_material_repair_plan(
        areas,
        name_regex,
        target_paper_id=target_paper_id,
    )
    print(
        f"[缺材料补录] 本地缺材料题库={len(local_missing_banks)} "
        f"可匹配远程={len(need_import)} 未匹配远程={len(missing_remote)}"
    )

    if local_missing_banks:
        print("[缺材料补录] 本地缺材料题库样本:")
        for bank in local_missing_banks[:50]:
            print(
                f"  - code={bank.code} bank_id={bank.bank_id} placements={bank.placement_count} "
                f"questions={bank.distinct_question_count} materials={bank.material_count} {bank.name}"
            )
        if len(local_missing_banks) > 50:
            print(f"  ... 其余 {len(local_missing_banks) - 50} 条未展示")

    if missing_remote:
        print("[缺材料补录] 以下本地题库未在当前区域/关键词下匹配到远程试卷:")
        for bank in missing_remote[:50]:
            print(f"  - code={bank.code} bank_id={bank.bank_id} {bank.name}")
        if len(missing_remote) > 50:
            print(f"  ... 其余 {len(missing_remote) - 50} 条未展示")

    if not need_import:
        print("[缺材料补录] 没有可补录的试卷。")
        return

    if max_banks > 0:
        need_import = need_import[:max_banks]

    print("[缺材料补录] 准备补录试卷:")
    for paper in need_import[:50]:
        print(f"  - [{paper.area_name}] paper_id={paper.paper_id} qcount={paper.qcount} {paper.name}")
    if len(need_import) > 50:
        print(f"  ... 其余 {len(need_import) - 50} 条未展示")

    if not ask_yes_no("是否继续执行缺材料补录", True):
        print("已取消。")
        return

    success_count = 0
    for index, paper in enumerate(need_import, start=1):
        print(
            f"[缺材料补录] {index}/{len(need_import)} 开始 "
            f"area={paper.area_name}(id={paper.area_id}) paper_id={paper.paper_id}"
        )
        pids = await clear_question_locks()
        if pids:
            print(f"[缺材料补录] 清理锁会话: {pids}")

        args = build_import_args(
            areas=[paper.area_id],
            name_regex=".*",
            dry_run=dry_run,
            mirror_images=mirror_images,
            paper_id=paper.paper_id,
            max_papers=0,
            max_questions=0,
            mirror_safe_interval=mirror_safe_interval,
        )
        try:
            await run_question_import_core(args)
            success_count += 1
            print(f"[缺材料补录] 完成 paper_id={paper.paper_id}")
            if not dry_run:
                await verify_paper(paper.paper_id)
        except Exception as exc:
            print(f"[缺材料补录] 失败 paper_id={paper.paper_id} error={exc}")

    print(f"[缺材料补录] 完成成功数={success_count}/{len(need_import)}")


async def select_areas() -> list[AreaNode]:
    """交互选择地区。"""
    try:
        areas = await fetch_remote_areas()
    except Exception as exc:
        print(f"[警告] 地区接口获取失败，改用默认地区列表。原因: {exc}")
        areas = fallback_areas()
    return choose_areas_by_response(areas)


async def select_papers_interactive() -> list[RemotePaper]:
    """交互选择试卷。"""
    areas = await select_areas()
    keyword = ask("输入试卷关键词正则（为空=全部）", ".*")
    papers = await fetch_remote_papers(areas, keyword)
    if not papers:
        print("没有匹配到试卷。")
        return []
    return choose_papers_by_response(papers)


async def run_single_import() -> None:
    """按选中试卷逐个导入。"""
    papers = await select_papers_interactive()
    if not papers:
        return
    dry_run = ask_yes_no("是否 DryRun（仅演练不落库）", True)
    mirror_images = ask_yes_no("是否启用外链图片镜像到 OSS", False)
    mirror_safe_interval = 2.5
    if mirror_images:
        mirror_safe_interval = ask_float("图片请求安全间隔秒数（建议 2-5）", 2.5)
    smoke_mode = ask_yes_no("是否启用验收小模式（仅跑 1 套并输出 URL 对照样本）", True)
    mirror_sample_limit = 0
    selected_papers = papers
    if smoke_mode:
        selected_papers = papers[:1]
        if not mirror_images:
            print("[小模式] 已自动开启图片镜像，便于输出前后 URL 样本")
            mirror_images = True
        mirror_sample_limit = ask_int("输出多少条 URL 对照样本", 10)
        print(
            f"[小模式] 仅处理首套试卷 paper_id={selected_papers[0].paper_id} "
            f"name={selected_papers[0].name}"
        )

    for index, paper in enumerate(selected_papers, start=1):
        print(
            f"[导入] {index}/{len(selected_papers)} 开始 "
            f"area={paper.area_name}(id={paper.area_id}) paper_id={paper.paper_id}"
        )
        pids = await clear_question_locks()
        if pids:
            print(f"[导入] 清理锁会话: {pids}")
        args = build_import_args(
            areas=[paper.area_id],
            name_regex=".*",
            dry_run=dry_run,
            mirror_images=mirror_images,
            paper_id=paper.paper_id,
            max_papers=0,
            max_questions=0,
            mirror_sample_limit=mirror_sample_limit,
            mirror_safe_interval=mirror_safe_interval,
        )
        await run_question_import_core(args)
        print(f"[导入] 完成 paper_id={paper.paper_id}")


async def run_area_batch() -> None:
    """按地区批量导入。"""
    areas = await select_areas()
    name_regex = ask("输入试卷关键词正则（为空=全部）", ".*")
    dry_run = ask_yes_no("是否 DryRun（仅演练不落库）", False)
    mirror_images = ask_yes_no("是否启用外链图片镜像到 OSS", False)
    mirror_safe_interval = 2.5
    if mirror_images:
        mirror_safe_interval = ask_float("图片请求安全间隔秒数（建议 2-5）", 2.5)
    max_papers = ask_int("每个地区最多导入多少套（0=不限）", 0)

    success: list[int] = []
    failed: list[int] = []
    for index, area in enumerate(areas, start=1):
        print(f"[地区批量] {index}/{len(areas)} 开始 area={area.name}(id={area.area_id})")
        pids = await clear_question_locks()
        if pids:
            print(f"[地区批量] 清理锁会话: {pids}")
        try:
            args = build_import_args(
                areas=[area.area_id],
                name_regex=name_regex,
                dry_run=dry_run,
                mirror_images=mirror_images,
                paper_id=0,
                max_papers=max_papers,
                max_questions=0,
                mirror_safe_interval=mirror_safe_interval,
            )
            await run_question_import_core(args)
            success.append(area.area_id)
            print(f"[地区批量] 完成 area={area.name}(id={area.area_id})")
        except Exception as exc:
            failed.append(area.area_id)
            print(f"[地区批量] 失败 area={area.name}(id={area.area_id}) error={exc}")

    print(f"[地区批量] 成功地区 id={success}")
    print(f"[地区批量] 失败地区 id={failed}")


async def run_incremental_batch() -> None:
    """按缺口执行增量导入。"""
    areas = await select_areas()
    name_regex = ask("输入试卷关键词正则（为空=全部）", ".*")
    dry_run = ask_yes_no("是否 DryRun（仅演练不落库）", False)
    mirror_images = ask_yes_no("是否启用外链图片镜像到 OSS", False)
    mirror_safe_interval = 2.5
    if mirror_images:
        mirror_safe_interval = ask_float("图片请求安全间隔秒数（建议 2-5）", 2.5)

    missing_bank, need_import = await build_incremental_plan(areas, name_regex)
    print(f"[增量计划] 缺失题库记录={len(missing_bank)} 需增量导入={len(need_import)}")

    if missing_bank:
        print("[增量计划] 以下试卷在本地缺少 bank 记录（跳过）:")
        for paper in missing_bank[:50]:
            print(
                f"  - [{paper.area_name}] paper_id={paper.paper_id} "
                f"qcount={paper.qcount} {paper.name}"
            )
        if len(missing_bank) > 50:
            print(f"  ... 其余 {len(missing_bank) - 50} 条未展示")

    if not need_import:
        print("[增量计划] 没有需要导入的试卷。")
        return

    print("[增量计划] 需导入试卷:")
    for paper in need_import[:50]:
        print(
            f"  - [{paper.area_name}] paper_id={paper.paper_id} "
            f"qcount={paper.qcount} {paper.name}"
        )
    if len(need_import) > 50:
        print(f"  ... 其余 {len(need_import) - 50} 条未展示")

    if not ask_yes_no("是否继续执行增量导入", True):
        print("已取消。")
        return

    success_count = 0
    for index, paper in enumerate(need_import, start=1):
        print(
            f"[增量导入] {index}/{len(need_import)} 开始 "
            f"area={paper.area_name}(id={paper.area_id}) paper_id={paper.paper_id}"
        )
        pids = await clear_question_locks()
        if pids:
            print(f"[增量导入] 清理锁会话: {pids}")

        args = build_import_args(
            areas=[paper.area_id],
            name_regex=".*",
            dry_run=dry_run,
            mirror_images=mirror_images,
            paper_id=paper.paper_id,
            max_papers=0,
            max_questions=0,
            mirror_safe_interval=mirror_safe_interval,
        )
        try:
            await run_question_import_core(args)
            success_count += 1
            print(f"[增量导入] 完成 paper_id={paper.paper_id}")
        except Exception as exc:
            print(f"[增量导入] 失败 paper_id={paper.paper_id} error={exc}")

    print(f"[增量导入] 完成成功数={success_count}/{len(need_import)}")


async def run_lock_cleanup() -> None:
    """执行锁清理。"""
    pids = await clear_question_locks()
    if pids:
        print(f"[锁清理] 已终止会话: {pids}")
    else:
        print("[锁清理] 没有待清理会话。")


async def run_verify() -> None:
    """交互选择并校验试卷。"""
    papers = await select_papers_interactive()
    if not papers:
        return
    for paper in papers:
        await verify_paper(paper.paper_id)


async def main() -> int:
    """主入口。"""
    if "PASTE_YOUR_COOKIE_HERE" in HUATU_COOKIE:
        print("请先在脚本中填写 HUATU_COOKIE，或先设置环境变量 HUATU_COOKIE。")
        return 1

    while True:
        print("\n========== 题库导入控制台 ==========")
        print("1) 清理数据库锁会话")
        print("2) 从网页选择试卷并导入（不手填 id）")
        print("3) 从网页选择地区并批量导入")
        print("4) 增量导入（自动比对本地缺口）")
        print("5) 从网页选择试卷并校验本地")
        print("6) 针对本地空题库补录")
        print("7) 针对本地缺材料题库补录")
        print("0) 退出")
        choice = ask("请选择功能", "0")

        if choice == "0":
            print("已退出。")
            return 0
        if choice == "1":
            await run_lock_cleanup()
            continue
        if choice == "2":
            await run_single_import()
            continue
        if choice == "3":
            await run_area_batch()
            continue
        if choice == "4":
            await run_incremental_batch()
            continue
        if choice == "5":
            await run_verify()
            continue
        if choice == "6":
            await run_empty_bank_repair()
            continue
        if choice == "7":
            await run_missing_material_repair()
            continue

        print("无效选择，请重试。")


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    raise SystemExit(asyncio.run(main()))
