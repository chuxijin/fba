#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio
import html
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
from sqlalchemy.ext.asyncio import AsyncSession

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.question_bank.model import (  # noqa: E402
    Question,
    QuestionAnalysis,
    QuestionBank,
    QuestionMaterial,
    QuestionPlacement,
)
from backend.app.question_bank.model.question import question_material_relation  # noqa: E402
from backend.database.db import async_db_session  # noqa: E402
from backend.scripts.qbank_image_mirror import QbankImageMirror  # noqa: E402

SADUCK_API_BASE = "https://saduck.top/api"
SADUCK_LIST_URL = f"{SADUCK_API_BASE}/sl/getSl"
SADUCK_DETAIL_URL = f"{SADUCK_API_BASE}/sl/getSlContextNew"

ROOT_BANK_CODE = "BANK_SHENLUN"
ROOT_BANK_NAME = "申论"
ROOT_BANK_TYPE = 3
SUB_BANK_TYPE = 3
PAPER_BANK_TYPE = 2
NATIONAL_BANK_CODE = "BANK_SHENLUN_NATIONAL"
NATIONAL_BANK_NAME = "国家公务员考试申论"
PROVINCIAL_BANK_CODE = "BANK_SHENLUN_PROVINCIAL"
PROVINCIAL_BANK_NAME = "省公务员申论"
DEFAULT_CATEGORY_ID = 2
DEFAULT_CREATED_BY = 1

PROVINCIAL_REGION_RULES: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("BEIJING", "北京省考申论", ("北京", "北京市")),
    ("TIANJIN", "天津省考申论", ("天津", "天津市")),
    ("HEBEI", "河北省考申论", ("河北",)),
    ("SHANXI", "山西省考申论", ("山西",)),
    ("INNER_MONGOLIA", "内蒙古省考申论", ("内蒙古",)),
    ("LIAONING", "辽宁省考申论", ("辽宁",)),
    ("JILIN", "吉林省考申论", ("吉林",)),
    ("HEILONGJIANG", "黑龙江省考申论", ("黑龙江",)),
    ("SHANGHAI", "上海省考申论", ("上海", "上海市")),
    ("JIANGSU", "江苏省考申论", ("江苏",)),
    ("ZHEJIANG", "浙江省考申论", ("浙江",)),
    ("ANHUI", "安徽省考申论", ("安徽",)),
    ("FUJIAN", "福建省考申论", ("福建",)),
    ("JIANGXI", "江西省考申论", ("江西",)),
    ("SHANDONG", "山东省考申论", ("山东",)),
    ("HENAN", "河南省考申论", ("河南",)),
    ("HUBEI", "湖北省考申论", ("湖北",)),
    ("HUNAN", "湖南省考申论", ("湖南",)),
    ("GUANGDONG", "广东省考申论", ("广东",)),
    ("GUANGXI", "广西省考申论", ("广西",)),
    ("HAINAN", "海南省考申论", ("海南",)),
    ("CHONGQING", "重庆省考申论", ("重庆", "重庆市")),
    ("SICHUAN", "四川省考申论", ("四川",)),
    ("GUIZHOU", "贵州省考申论", ("贵州",)),
    ("YUNNAN", "云南省考申论", ("云南",)),
    ("XIZANG", "西藏省考申论", ("西藏",)),
    ("SHAANXI", "陕西省考申论", ("陕西",)),
    ("GANSU", "甘肃省考申论", ("甘肃",)),
    ("QINGHAI", "青海省考申论", ("青海",)),
    ("NINGXIA", "宁夏省考申论", ("宁夏",)),
    ("XINJIANG", "新疆省考申论", ("新疆",)),
)


@dataclass
class SaduckPaper:
    """Saduck paper item."""

    encrypted_id: str
    decoded_id: str
    test_name: str
    sort: int


@dataclass
class ImportStats:
    """Import statistics."""

    papers_total: int = 0
    papers_imported: int = 0
    papers_skipped: int = 0
    questions_total: int = 0
    questions_upserted: int = 0
    analyses_upserted: int = 0
    placements_upserted: int = 0
    materials_upserted: int = 0


def ask(prompt: str, default: str | None = None) -> str:
    """
    Read user input.

    :param prompt: prompt text
    :param default: default value
    :return:
    """
    if default is None:
        return input(f"{prompt}: ").strip()

    value = input(f"{prompt} [{default}]: ").strip()
    if value:
        return value
    return default


def ask_int(prompt: str, default: int) -> int:
    """
    Read int input.

    :param prompt: prompt text
    :param default: default value
    :return:
    """
    while True:
        raw = ask(prompt, str(default))
        try:
            return int(raw)
        except ValueError:
            print("请输入整数")


def ask_float(prompt: str, default: float) -> float:
    """
    Read float input.

    :param prompt: prompt text
    :param default: default value
    :return:
    """
    while True:
        raw = ask(prompt, str(default))
        try:
            return float(raw)
        except ValueError:
            print("请输入数字")


def ask_yes_no(prompt: str, default_yes: bool = True) -> bool:
    """
    Read yes/no input.

    :param prompt: prompt text
    :param default_yes: default bool
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
        print("请输入 y 或 n")


def parse_index_input(raw: str, max_index: int) -> list[int]:
    """
    Parse index expression like 1,3,8-10/all.

    :param raw: raw input
    :param max_index: max index
    :return:
    """
    text_value = raw.strip().lower()
    if text_value in {"all", "a", "*"}:
        return list(range(1, max_index + 1))

    selected: set[int] = set()
    parts = [item.strip() for item in raw.split(",") if item.strip()]
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


def decrypt_remote_id(encrypted_id: str, key: int = 1) -> str:
    """
    Decrypt saduck paper id.

    :param encrypted_id: encrypted id
    :param key: xor key
    :return:
    """
    chars: list[str] = []
    for index, ch in enumerate(str(encrypted_id)):
        value = (ord(ch) - index) ^ key
        chars.append(chr(value))
    return "".join(chars)


def sanitize_code(raw: str, prefix: str = "") -> str:
    """
    Build safe bank code.

    :param raw: raw text
    :param prefix: code prefix
    :return:
    """
    base = re.sub(r"[^A-Za-z0-9_]+", "_", raw.strip()).strip("_")
    if not base:
        base = "PAPER"
    code = f"{prefix}{base}" if prefix else base
    return code[:32].upper()


def is_national_shenlun_paper(test_name: str) -> bool:
    """
    Detect national exam shenlun paper by title.

    :param test_name: paper title
    :return:
    """
    title = str(test_name or "")
    keywords = ("国家公考", "国家公务员", "国考")
    for keyword in keywords:
        if keyword in title:
            return True
    return False


def detect_provincial_region(test_name: str) -> tuple[str, str] | None:
    """
    Detect provincial region node by title.

    :param test_name: paper title
    :return:
    """
    title = str(test_name or "")
    for region_code, region_name, keywords in PROVINCIAL_REGION_RULES:
        for keyword in keywords:
            if keyword in title:
                return region_code, region_name
    return None


def parse_score(text: str) -> Decimal:
    """
    Parse score from question text.

    :param text: question text
    :return:
    """
    if not text:
        return Decimal("1.0")
    match = re.search(r"[（(]\s*(\d+(?:\.\d+)?)\s*分\s*[）)]", text)
    if not match:
        return Decimal("1.0")
    try:
        value = Decimal(match.group(1))
    except InvalidOperation:
        return Decimal("1.0")
    if value <= 0:
        return Decimal("1.0")
    return value


def normalize_html_text(text: str) -> str:
    """
    Normalize plain text to html paragraphs.

    :param text: raw text
    :return:
    """
    source = str(text or "").strip()
    if not source:
        return ""
    if re.search(r"</?[a-zA-Z][^>]*>", source):
        return source

    lines = [line.strip() for line in source.splitlines() if line.strip()]
    if not lines:
        return ""
    return "".join(f"<p>{html.escape(line)}</p>" for line in lines)


def build_stem(content: str, require: str) -> str:
    """
    Build question stem html.

    :param content: question content
    :param require: question requirement
    :return:
    """
    parts: list[str] = []
    content_html = normalize_html_text(content)
    if content_html:
        parts.append(content_html)
    require_html = normalize_html_text(require)
    if require_html:
        parts.append(require_html)
    return "".join(parts)


def build_run_args() -> SimpleNamespace:
    """Read interactive runtime args."""
    token_env = os.getenv("SADUCK_TOKEN", "").strip()
    token = ask("请输入 SaDuck token（可留空使用环境变量 SADUCK_TOKEN）", token_env).strip()
    if not token:
        raise RuntimeError("token 不能为空")

    dry_run = ask_yes_no("是否 DryRun（仅演练不提交）", True)
    update_existing = ask_yes_no("已存在试卷是否覆盖更新", False)
    max_questions = ask_int("每套试卷最多导入题目数（0=不限）", 0)
    cat_id = ask_int("题库分类 cat_id", DEFAULT_CATEGORY_ID)
    created_by = ask_int("created_by 用户 ID", DEFAULT_CREATED_BY)

    mirror_images = ask_yes_no("是否镜像题干/材料/答案中的图片到 OSS", True)
    mirror_timeout = 20.0
    mirror_safe_interval = 2.5
    mirror_sample_limit = 5
    if mirror_images:
        mirror_timeout = ask_float("图片下载超时秒数", 20.0)
        mirror_safe_interval = ask_float("图片请求安全间隔秒数（建议 >= 1.5）", 2.5)
        mirror_sample_limit = ask_int("输出前后 URL 对照样本条数（0=不输出）", 5)

    return SimpleNamespace(
        token=token,
        dry_run=dry_run,
        update_existing=update_existing,
        max_questions=max_questions,
        cat_id=cat_id,
        created_by=created_by,
        mirror_images=mirror_images,
        mirror_timeout=mirror_timeout,
        mirror_safe_interval=mirror_safe_interval,
        mirror_sample_limit=mirror_sample_limit,
    )


def build_http_headers(token: str) -> dict[str, str]:
    """
    Build request headers.

    :param token: saduck token
    :return:
    """
    return {
        "Accept": "application/json, text/plain, */*",
        "Content-Type": "application/json",
        "Origin": "https://saduck.top",
        "Referer": "https://saduck.top/my/sl.html",
        "token": token,
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/145.0.0.0 Safari/537.36"
        ),
    }


async def fetch_paper_list(client: httpx.AsyncClient, token: str) -> list[SaduckPaper]:
    """
    Fetch paper list from saduck.

    :param client: http client
    :param token: auth token
    :return:
    """
    response = await client.post(SADUCK_LIST_URL, json={}, headers=build_http_headers(token))
    response.raise_for_status()
    payload = response.json()
    if payload.get("code") != 0:
        raise RuntimeError(f"获取试卷列表失败: {payload.get('message')}")

    result = payload.get("result")
    if not isinstance(result, list):
        raise RuntimeError("试卷列表结构异常：result 不是数组")

    papers: list[SaduckPaper] = []
    for item in result:
        if not isinstance(item, dict):
            continue
        encrypted_id = str(item.get("id") or "").strip()
        test_name = str(item.get("testName") or "").strip()
        if not encrypted_id or not test_name:
            continue
        decoded_id = decrypt_remote_id(encrypted_id)
        papers.append(
            SaduckPaper(
                encrypted_id=encrypted_id,
                decoded_id=decoded_id,
                test_name=test_name,
                sort=int(item.get("sort") or 0),
            )
        )

    papers.sort(key=lambda item: (item.sort, item.test_name), reverse=True)
    return papers


async def fetch_paper_detail(
    client: httpx.AsyncClient, token: str, decoded_paper_id: str
) -> tuple[list[dict[str, Any]], list[str]]:
    """
    Fetch one paper detail.

    :param client: http client
    :param token: auth token
    :param decoded_paper_id: decoded paper id
    :return:
    """
    response = await client.post(
        SADUCK_DETAIL_URL,
        params={"id": decoded_paper_id},
        json={},
        headers=build_http_headers(token),
    )
    response.raise_for_status()
    payload = response.json()
    if payload.get("code") != 0:
        raise RuntimeError(f"获取试卷详情失败: {payload.get('message')}")

    result = payload.get("result") or {}
    questions = result.get("questions") or []
    materials = result.get("expandedMaterials") or []
    if not isinstance(questions, list):
        questions = []
    if not isinstance(materials, list):
        materials = []

    normalized_materials = [str(item or "").strip() for item in materials if str(item or "").strip()]
    normalized_questions = [item for item in questions if isinstance(item, dict)]
    return normalized_questions, normalized_materials


def choose_target_papers(all_papers: list[SaduckPaper]) -> list[SaduckPaper]:
    """
    Interactively choose papers.

    :param all_papers: all papers
    :return:
    """
    keyword = ask("输入试卷关键字（支持模糊，留空=全部）", "").strip()
    if keyword:
        filtered = [paper for paper in all_papers if keyword in paper.test_name]
    else:
        filtered = list(all_papers)

    if not filtered:
        print("没有匹配到试卷")
        return []

    show_count = min(120, len(filtered))
    print(f"\n匹配试卷 {len(filtered)} 个（最多显示前 {show_count} 个）:")
    for index in range(show_count):
        paper = filtered[index]
        print(f"{index + 1:>3}. id={paper.decoded_id} name={paper.test_name}")
    if len(filtered) > show_count:
        print(f"... 其余 {len(filtered) - show_count} 个未显示，可缩小关键字后再选")

    while True:
        raw = ask("输入序号（支持 1,3,8-10；all=全部）", "1")
        try:
            indices = parse_index_input(raw, len(filtered))
        except Exception:
            print("序号格式错误，请重试")
            continue
        if not indices:
            print("请至少选择一个试卷")
            continue

        selected = [filtered[index - 1] for index in indices]
        print("已选择:")
        for paper in selected:
            print(f"  - {paper.decoded_id} ({paper.test_name})")
        return selected


async def ensure_bank(
    db: AsyncSession,
    *,
    cat_id: int,
    code: str,
    name: str,
    bank_type: int,
    parent_id: int | None,
    created_by: int,
) -> QuestionBank:
    """
    Create or update bank by code.

    :param db: db session
    :param cat_id: category id
    :param code: bank code
    :param name: bank name
    :param bank_type: bank type
    :param parent_id: parent bank id
    :param created_by: created by user id
    :return:
    """
    bank = await db.scalar(select(QuestionBank).where(QuestionBank.code == code))
    if bank is None:
        bank = QuestionBank(
            cat_id=cat_id,
            name=name,
            code=code,
            desc=None,
            cover_url=None,
            difficulty=None,
            bank_type=bank_type,
            scene_mask=1,
            parent_id=parent_id,
            status=1,
            q_count_cache=0,
            total_score_cache=Decimal("0"),
            buy_count=0,
            created_by=created_by,
        )
        db.add(bank)
        await db.flush()
        return bank

    changed = False
    if bank.cat_id != cat_id:
        bank.cat_id = cat_id
        changed = True
    if bank.name != name:
        bank.name = name
        changed = True
    if bank.bank_type != bank_type:
        bank.bank_type = bank_type
        changed = True
    if bank.parent_id != parent_id:
        bank.parent_id = parent_id
        changed = True
    if bank.status != 1:
        bank.status = 1
        changed = True
    if changed:
        bank.updated_by = created_by
        await db.flush()
    return bank


async def mirror_html_text(
    *,
    mirror: QbankImageMirror | None,
    html_text: str,
    bank_code: str,
    field_name: str,
    question_id: int | None = None,
    scope_segment: str | None = None,
) -> str:
    """
    Mirror html images if mirror is enabled.

    :param mirror: mirror service
    :param html_text: html text
    :param bank_code: bank code
    :param field_name: field name
    :param question_id: optional question id
    :param scope_segment: optional scope
    :return:
    """
    if mirror is None:
        return html_text
    if not isinstance(html_text, str):
        return html_text
    if "<img" not in html_text.lower():
        return html_text

    return await mirror.mirror_html(
        html=html_text,
        bank_code=bank_code,
        field_name=field_name,
        question_id=question_id,
        scope_segment=scope_segment,
    )


async def upsert_materials(
    *,
    db: AsyncSession,
    paper_bank: QuestionBank,
    material_contents: list[str],
    mirror: QbankImageMirror | None,
    created_by: int,
) -> tuple[list[int], int]:
    """
    Upsert paper materials.

    :param db: db session
    :param paper_bank: paper bank
    :param material_contents: material text list
    :param mirror: mirror service
    :param created_by: user id
    :return:
    """
    if not material_contents:
        return [], 0

    existing_rows = (
        await db.execute(
            select(QuestionMaterial).where(
                QuestionMaterial.bank_id == paper_bank.id,
                QuestionMaterial.is_active.is_(True),
            )
        )
    ).scalars().all()
    existing_by_title = {str(item.title): item for item in existing_rows}

    material_ids: list[int] = []
    upserted = 0
    for index, content_raw in enumerate(material_contents, start=1):
        title = f"材料{index}"
        content_html = normalize_html_text(content_raw)
        content_html = await mirror_html_text(
            mirror=mirror,
            html_text=content_html,
            bank_code=paper_bank.code,
            field_name="material_content",
            scope_segment=f"material_{index:02d}",
        )

        current = existing_by_title.get(title)
        if current is None:
            current = QuestionMaterial(
                bank_id=paper_bank.id,
                title=title,
                content=content_html,
                category_id=None,
                source="saduck",
                year=None,
                sort_order=index,
                is_active=True,
                created_by=created_by,
            )
            db.add(current)
            await db.flush()
            upserted += 1
        else:
            changed = False
            if current.content != content_html:
                current.content = content_html
                changed = True
            if current.sort_order != index:
                current.sort_order = index
                changed = True
            if not current.is_active:
                current.is_active = True
                changed = True
            if changed:
                current.updated_by = created_by
                upserted += 1

        material_ids.append(current.id)

    return material_ids, upserted


async def sync_material_relations(
    *,
    db: AsyncSession,
    question_id: int,
    paper_bank_id: int,
    material_ids: list[int],
) -> None:
    """
    Sync question material relation for one question.

    :param db: db session
    :param question_id: question id
    :param paper_bank_id: paper bank id
    :param material_ids: target material ids
    :return:
    """
    if not material_ids:
        return

    relation_rows = (
        await db.execute(
            select(question_material_relation.c.material_id)
            .join(QuestionMaterial, QuestionMaterial.id == question_material_relation.c.material_id)
            .where(
                question_material_relation.c.question_id == question_id,
                QuestionMaterial.bank_id == paper_bank_id,
            )
        )
    ).all()
    existing_ids = {int(row.material_id) for row in relation_rows}
    target_ids = set(material_ids)

    for sort_order, material_id in enumerate(material_ids, start=1):
        if material_id in existing_ids:
            await db.execute(
                sa_update(question_material_relation)
                .where(
                    question_material_relation.c.question_id == question_id,
                    question_material_relation.c.material_id == material_id,
                )
                .values(sort_order=sort_order)
            )
            continue
        await db.execute(
            question_material_relation.insert().values(
                question_id=question_id,
                material_id=material_id,
                sort_order=sort_order,
            )
        )

    remove_ids = existing_ids - target_ids
    if remove_ids:
        await db.execute(
            sa_delete(question_material_relation).where(
                question_material_relation.c.question_id == question_id,
                question_material_relation.c.material_id.in_(remove_ids),
            )
        )


async def recalc_bank_cache(db: AsyncSession, bank: QuestionBank) -> None:
    """
    Recalculate one bank cache fields.

    :param db: db session
    :param bank: bank row
    :return:
    """
    q_count = await db.scalar(
        select(func.count(QuestionPlacement.id)).where(
            QuestionPlacement.bank_id == bank.id,
            QuestionPlacement.is_active.is_(True),
        )
    )
    total_score = await db.scalar(
        select(func.coalesce(func.sum(QuestionPlacement.score), 0)).where(
            QuestionPlacement.bank_id == bank.id,
            QuestionPlacement.is_active.is_(True),
        )
    )
    bank.q_count_cache = int(q_count or 0)
    bank.total_score_cache = Decimal(str(total_score or 0))


async def align_question_id_sequence(db: AsyncSession) -> None:
    """
    Align question id sequence to current max id.

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
        print(f"[DB][WARN] align question id sequence failed: {exc!s}")


async def import_one_paper(
    *,
    db: AsyncSession,
    client: httpx.AsyncClient,
    token: str,
    national_bank: QuestionBank,
    provincial_bank: QuestionBank,
    province_bank_cache: dict[str, QuestionBank],
    paper: SaduckPaper,
    args: SimpleNamespace,
    mirror: QbankImageMirror | None,
    stats: ImportStats,
    paper_index: int,
    total_papers: int,
) -> None:
    """
    Import one paper.

    :param db: db session
    :param client: http client
    :param token: auth token
    :param national_bank: national shenlun bank
    :param provincial_bank: provincial shenlun bank
    :param province_bank_cache: cached province banks
    :param paper: remote paper
    :param args: runtime args
    :param mirror: mirror service
    :param stats: global stats
    :param paper_index: paper index
    :param total_papers: total papers
    :return:
    """
    parent_bank = national_bank
    if not is_national_shenlun_paper(paper.test_name):
        region_info = detect_provincial_region(paper.test_name)
        region_bank_code = "BANK_SHENLUN_PROV_OTHER"
        region_bank_name = "其他省考申论"
        if region_info is not None:
            region_code, region_name = region_info
            region_bank_code = sanitize_code(region_code, prefix="BANK_SHENLUN_PROV_")
            region_bank_name = region_name

        parent_bank = province_bank_cache.get(region_bank_code)
        if parent_bank is None:
            parent_bank = await ensure_bank(
                db,
                cat_id=args.cat_id,
                code=region_bank_code,
                name=region_bank_name,
                bank_type=SUB_BANK_TYPE,
                parent_id=provincial_bank.id,
                created_by=args.created_by,
            )
            province_bank_cache[region_bank_code] = parent_bank
            print(f"[DB] province_bank code={parent_bank.code} name={parent_bank.name}")

    paper_code = sanitize_code(paper.decoded_id, prefix="SL_")
    paper_bank = await ensure_bank(
        db,
        cat_id=args.cat_id,
        code=paper_code,
        name=paper.test_name,
        bank_type=PAPER_BANK_TYPE,
        parent_id=parent_bank.id,
        created_by=args.created_by,
    )

    existing_count = await db.scalar(
        select(func.count(QuestionPlacement.id)).where(
            QuestionPlacement.bank_id == paper_bank.id,
            QuestionPlacement.is_active.is_(True),
        )
    )
    if not args.update_existing and int(existing_count or 0) > 0:
        print(
            f"[PAPER] {paper_index}/{total_papers}"
            f" code={paper_code} 已存在题目 {int(existing_count or 0)}，跳过"
        )
        stats.papers_skipped += 1
        return

    print(
        f"[PAPER] {paper_index}/{total_papers}"
        f" code={paper_code}"
        f" parent={parent_bank.code}"
        f" name={paper.test_name}"
    )
    questions_remote, materials_remote = await fetch_paper_detail(client, token, paper.decoded_id)
    if args.max_questions > 0:
        questions_remote = questions_remote[: args.max_questions]
    print(f"[PAPER] fetched questions={len(questions_remote)} materials={len(materials_remote)}")

    material_ids, material_upserted = await upsert_materials(
        db=db,
        paper_bank=paper_bank,
        material_contents=materials_remote,
        mirror=mirror,
        created_by=args.created_by,
    )
    stats.materials_upserted += material_upserted

    placement_rows = (
        await db.execute(select(QuestionPlacement).where(QuestionPlacement.bank_id == paper_bank.id))
    ).scalars().all()
    placement_by_sort: dict[int, QuestionPlacement] = {}
    question_id_list = [int(row.question_id) for row in placement_rows]
    for row in placement_rows:
        sort_key = int(row.sort_order or 0)
        current = placement_by_sort.get(sort_key)
        if current is None:
            placement_by_sort[sort_key] = row
            continue
        if not current.is_active and row.is_active:
            placement_by_sort[sort_key] = row

    question_by_id: dict[int, Question] = {}
    if question_id_list:
        existing_rows = (
            await db.execute(select(Question).where(Question.id.in_(question_id_list)))
        ).scalars().all()
        question_by_id = {int(row.id): row for row in existing_rows}

    question_ids: list[int] = []
    for q_index, question_raw in enumerate(questions_remote, start=1):
        score_value = parse_score(str(question_raw.get("content") or ""))
        stem_raw_html = build_stem(
            str(question_raw.get("content") or ""),
            str(question_raw.get("require") or ""),
        )

        placement = placement_by_sort.get(q_index)
        question_row: Question | None = None
        local_question_id = 0
        if placement is not None:
            local_question_id = int(placement.question_id)
            question_row = question_by_id.get(local_question_id)

        if question_row is None:
            question_row = Question(
                type="shortAnswer",
                stem=stem_raw_html,
                difficulty="medium",
                default_score=score_value,
                knowledge_point=["申论"],
                content_status=10,
                created_by=args.created_by,
            )
            db.add(question_row)
            await db.flush()
            local_question_id = int(question_row.id)
            question_by_id[local_question_id] = question_row
        else:
            question_row.type = "shortAnswer"
            question_row.difficulty = "medium"
            question_row.default_score = score_value
            question_row.knowledge_point = ["申论"]
            question_row.content_status = 10
            question_row.updated_by = args.created_by

        stem_html = await mirror_html_text(
            mirror=mirror,
            html_text=stem_raw_html,
            bank_code=paper_code,
            field_name="stem",
            question_id=local_question_id,
        )
        question_row.stem = stem_html
        question_ids.append(local_question_id)
        stats.questions_upserted += 1

        answers = question_raw.get("answers") or []
        if not isinstance(answers, list):
            answers = []
        await db.execute(sa_delete(QuestionAnalysis).where(QuestionAnalysis.question_id == local_question_id))
        for answer_index, answer_raw in enumerate(answers, start=1):
            answer_html = normalize_html_text(str(answer_raw.get("answer") or ""))
            answer_html = await mirror_html_text(
                mirror=mirror,
                html_text=answer_html,
                bank_code=paper_code,
                field_name=f"analysis_{answer_index}",
                question_id=local_question_id,
            )
            organ = str(answer_raw.get("organ") or "").strip()
            analysis = QuestionAnalysis(
                question_id=local_question_id,
                answer_data={
                    "source": "saduck",
                    "organ": organ,
                    "source_answer_id": answer_raw.get("id"),
                    "problem_id": answer_raw.get("problemId"),
                },
                content=answer_html,
                type="official",
                version_no=answer_index,
                is_default=answer_index == 1,
                view_count=0,
                helpful_count=int(answer_raw.get("good") or 0),
                unhelpful_count=int(answer_raw.get("noGood") or 0),
                status=10,
                created_by=args.created_by,
            )
            db.add(analysis)
            stats.analyses_upserted += 1

        if placement is None:
            placement = QuestionPlacement(
                question_id=local_question_id,
                bank_id=paper_bank.id,
                chapter_id=None,
                sort_order=q_index,
                is_active=True,
                score=score_value,
                review_status=10,
                scene_mask=None,
                created_by=args.created_by,
            )
            db.add(placement)
            placement_by_sort[q_index] = placement
        else:
            placement.question_id = local_question_id
            placement.sort_order = q_index
            placement.is_active = True
            placement.score = score_value
            placement.review_status = 10
            placement.updated_by = args.created_by
        stats.placements_upserted += 1

        if material_ids:
            # question/placement/analysis are ORM pending rows; flush first to satisfy FK for relation DML
            await db.flush()
            await sync_material_relations(
                db=db,
                question_id=local_question_id,
                paper_bank_id=paper_bank.id,
                material_ids=material_ids,
            )

        if q_index == len(questions_remote) or q_index % 5 == 0:
            print(
                f"[PAPER_Q] code={paper_code}"
                f" progress={q_index}/{len(questions_remote)}"
                f" analyses={stats.analyses_upserted}"
            )

    if args.update_existing and question_ids:
        await db.execute(
            sa_delete(QuestionPlacement).where(
                QuestionPlacement.bank_id == paper_bank.id,
                QuestionPlacement.question_id.notin_(question_ids),
            )
        )

    await recalc_bank_cache(db, paper_bank)
    stats.questions_total += len(question_ids)
    stats.papers_imported += 1
    print(
        f"[PAPER_DONE] code={paper_code}"
        f" questions={len(question_ids)}"
        f" materials={len(material_ids)}"
    )


async def main() -> None:
    """Run saduck shenlun import."""
    args = build_run_args()
    timeout = httpx.Timeout(timeout=30.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        papers_all = await fetch_paper_list(client, args.token)
        print(f"[LIST] fetched papers={len(papers_all)}")
        selected_papers = choose_target_papers(papers_all)
        if not selected_papers:
            return

        stats = ImportStats(papers_total=len(selected_papers))
        async with async_db_session() as db:
            try:
                await db.execute(select(func.set_config("lock_timeout", "8s", True)))
                await db.execute(select(func.set_config("statement_timeout", "120s", True)))
                print("[DB] timeout_set lock_timeout=8s statement_timeout=120s")
            except Exception as exc:
                print(f"[DB][WARN] set timeout failed: {exc!s}")

            await align_question_id_sequence(db)

            root_bank = await ensure_bank(
                db,
                cat_id=args.cat_id,
                code=ROOT_BANK_CODE,
                name=ROOT_BANK_NAME,
                bank_type=ROOT_BANK_TYPE,
                parent_id=None,
                created_by=args.created_by,
            )
            print(f"[DB] root_bank id={root_bank.id} code={root_bank.code}")

            national_bank = await ensure_bank(
                db,
                cat_id=args.cat_id,
                code=NATIONAL_BANK_CODE,
                name=NATIONAL_BANK_NAME,
                bank_type=SUB_BANK_TYPE,
                parent_id=root_bank.id,
                created_by=args.created_by,
            )
            provincial_bank = await ensure_bank(
                db,
                cat_id=args.cat_id,
                code=PROVINCIAL_BANK_CODE,
                name=PROVINCIAL_BANK_NAME,
                bank_type=SUB_BANK_TYPE,
                parent_id=root_bank.id,
                created_by=args.created_by,
            )
            print(
                f"[DB] sub_banks"
                f" national={national_bank.code}({national_bank.id})"
                f" provincial={provincial_bank.code}({provincial_bank.id})"
            )
            province_bank_cache: dict[str, QuestionBank] = {}

            mirror: QbankImageMirror | None = None
            if args.mirror_images:
                mirror = QbankImageMirror(
                    request_timeout=args.mirror_timeout,
                    sample_limit=args.mirror_sample_limit,
                    safe_interval_seconds=max(0.0, args.mirror_safe_interval),
                    safe_interval_jitter_seconds=min(1.0, max(0.0, args.mirror_safe_interval * 0.2)),
                )
                await mirror.initialize(db)

            for index, paper in enumerate(selected_papers, start=1):
                await import_one_paper(
                    db=db,
                    client=client,
                    token=args.token,
                    national_bank=national_bank,
                    provincial_bank=provincial_bank,
                    province_bank_cache=province_bank_cache,
                    paper=paper,
                    args=args,
                    mirror=mirror,
                    stats=stats,
                    paper_index=index,
                    total_papers=len(selected_papers),
                )
                await db.flush()

            await recalc_bank_cache(db, root_bank)
            await recalc_bank_cache(db, national_bank)
            await recalc_bank_cache(db, provincial_bank)
            if args.dry_run:
                await db.rollback()
                print("[DB] rollback")
            else:
                await db.commit()
                print("[DB] commit")

            if mirror is not None:
                mirror.save_cache()
                if mirror.rewrite_samples:
                    print(f"[MIRROR_SAMPLE] count={len(mirror.rewrite_samples)}")
                    for index, sample in enumerate(mirror.rewrite_samples, start=1):
                        print(
                            f"[MIRROR_SAMPLE] #{index} field={sample.field_name}"
                            f" scope={sample.scope_segment} cache={'Y' if sample.from_cache else 'N'}"
                        )
                        print(f"[MIRROR_SAMPLE]   before={sample.source_url}")
                        print(f"[MIRROR_SAMPLE]   after ={sample.mirrored_url}")

                print(
                    "[MIRROR]"
                    f" uploaded={mirror.stats.uploaded_images}"
                    f" cache_hit={mirror.stats.cache_hit}"
                    f" failed={mirror.stats.failed_images}"
                    f" public={mirror.stats.public_urls}"
                    f" signed={mirror.stats.signed_urls}"
                    f" unknown={mirror.stats.unknown_urls}"
                )

        print(
            "[DONE]"
            f" papers_total={stats.papers_total}"
            f" imported={stats.papers_imported}"
            f" skipped={stats.papers_skipped}"
            f" questions_total={stats.questions_total}"
            f" questions_upserted={stats.questions_upserted}"
            f" analyses_upserted={stats.analyses_upserted}"
            f" placements_upserted={stats.placements_upserted}"
            f" materials_upserted={stats.materials_upserted}"
            f" dry_run={args.dry_run}"
        )


if __name__ == "__main__":
    asyncio.run(main())
