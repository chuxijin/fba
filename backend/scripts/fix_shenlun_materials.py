#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
申论材料补录脚本
- 只补 study_question_material（材料内容）
- 只补 study_question_material_relation（材料与题目关联）
- 不创建/修改 bank、question、placement
"""
from __future__ import annotations

import asyncio
import html
import re
import sys
from pathlib import Path

import httpx
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.question_bank.model.bank import QuestionBank  # noqa: E402
from backend.app.question_bank.model.question import (  # noqa: E402
    QuestionMaterial,
    QuestionPlacement,
    question_material_relation,
)
from backend.database.db import async_db_session  # noqa: E402

SADUCK_DETAIL_URL = "https://saduck.top/api/sl/getSlContextNew"
CREATED_BY = 1


def normalize_html_text(text: str) -> str:
    source = str(text or "").strip()
    if not source:
        return ""
    if re.search(r"</?[a-zA-Z][^>]*>", source):
        return source
    lines = [line.strip() for line in source.splitlines() if line.strip()]
    return "".join(f"<p>{html.escape(line)}</p>" for line in lines)


async def fetch_materials(client: httpx.AsyncClient, token: str, decoded_id: str) -> list[str]:
    """从 SaDuck 拉取一套试卷的材料列表"""
    resp = await client.post(
        SADUCK_DETAIL_URL,
        params={"id": decoded_id},
        json={},
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Origin": "https://saduck.top",
            "Referer": "https://saduck.top/my/sl.html",
            "token": token,
            "User-Agent": "Mozilla/5.0",
        },
    )
    resp.raise_for_status()
    payload = resp.json()
    if payload.get("code") != 0:
        raise RuntimeError(payload.get("message", "unknown error"))
    materials = (payload.get("result") or {}).get("expandedMaterials") or []
    return [str(m).strip() for m in materials if str(m or "").strip()]


async def get_target_banks(db: AsyncSession) -> list[QuestionBank]:
    """找到所有 cat_id=34（申论）的试卷级 bank，且有题但没有材料的"""
    res = await db.execute(
        select(QuestionBank)
        .where(QuestionBank.cat_id == 34, QuestionBank.bank_type == 2)
        .order_by(QuestionBank.id)
    )
    banks = res.scalars().all()

    targets: list[QuestionBank] = []
    for bank in banks:
        q_count = await db.scalar(
            select(func.count(QuestionPlacement.id)).where(QuestionPlacement.bank_id == bank.id)
        )
        m_count = await db.scalar(
            select(func.count(QuestionMaterial.id)).where(QuestionMaterial.bank_id == bank.id)
        )
        if (q_count or 0) > 0 and (m_count or 0) == 0:
            targets.append(bank)
    return targets


async def main() -> None:
    token = input("请输入 SaDuck token: ").strip()
    if not token:
        raise SystemExit("token 不能为空")

    dry_run = input("是否 DryRun（仅演练不写入）[y/N]: ").strip().lower() in ("y", "yes")

    async with async_db_session() as db:
        print("\n[DB] 扫描申论 bank...")
        targets = await get_target_banks(db)
        print(f"[DB] 找到 {len(targets)} 个有题但无材料的申论试卷\n")

        if not targets:
            print("没有需要补录的 bank，退出。")
            return

        ok_count = 0
        skip_count = 0

        async with httpx.AsyncClient(timeout=30) as client:
            for i, bank in enumerate(targets, 1):
                # bank.code 格式: SL_<decoded_id>（可能被截断到 32 位）
                if not bank.code.upper().startswith("SL_"):
                    print(f"[{i}] SKIP bank={bank.id} code={bank.code}（非 SL_ 前缀）")
                    skip_count += 1
                    continue

                decoded_id = bank.code[3:]  # 去掉 "SL_" 前缀

                print(f"[{i}/{len(targets)}] bank={bank.id} | {bank.name}")

                try:
                    materials_raw = await fetch_materials(client, token, decoded_id)
                except Exception as exc:
                    print(f"  [ERROR] 拉取失败: {exc}")
                    skip_count += 1
                    continue

                if not materials_raw:
                    print(f"  [SKIP] API 返回材料为空")
                    skip_count += 1
                    continue

                print(f"  [API] 获取到 {len(materials_raw)} 条材料")

                # 获取该 bank 下所有 question_id（按 sort_order）
                q_res = await db.execute(
                    select(QuestionPlacement.question_id)
                    .where(QuestionPlacement.bank_id == bank.id)
                    .order_by(QuestionPlacement.sort_order)
                )
                question_ids = [r[0] for r in q_res.all()]
                print(f"  [DB] 该 bank 共 {len(question_ids)} 道题")

                if dry_run:
                    print("  [DRYRUN] 跳过写入")
                    continue

                # 1. 写入材料记录
                material_ids: list[int] = []
                for idx, content_raw in enumerate(materials_raw, 1):
                    mat = QuestionMaterial(
                        bank_id=bank.id,
                        title=f"材料{idx}",
                        content=normalize_html_text(content_raw),
                        category_id=None,
                        source="saduck",
                        year=None,
                        sort_order=idx,
                        is_active=True,
                        created_by=CREATED_BY,
                    )
                    db.add(mat)
                    await db.flush()
                    material_ids.append(int(mat.id))

                # 2. 写入题目-材料关联（每道题挂全部材料）
                for question_id in question_ids:
                    for sort_order, material_id in enumerate(material_ids, 1):
                        await db.execute(
                            question_material_relation.insert().values(
                                question_id=question_id,
                                material_id=material_id,
                                sort_order=sort_order,
                            )
                        )

                await db.commit()
                print(
                    f"  [OK] 写入材料 {len(material_ids)} 条"
                    f"，关联 {len(question_ids) * len(material_ids)} 条"
                )
                ok_count += 1

        print(f"\n完成！成功 {ok_count} 个，跳过 {skip_count} 个。")


if __name__ == "__main__":
    asyncio.run(main())
