#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""按 bank_revision_id 从生产库导出「知识点标注」所需的数据包。

产物与 prepare_extra_banks_data.py 同构，供 batch_label_all_banks.py / 子代理标注复用：
    {
      "bank_name": ..., "bank_revision_id": ...,
      "section_mappings": [{bank_section_id, parent_subject_name, bank_section_name,
                            target_chapter_name, official_chapter_id, candidate_section_ids}],
      "questions": [{item_id, question_id, bank_section_id, sort_order,
                     question_type, stem, option_data, explanation}]
    }

与 prepare_extra_banks_data.py 的两点差异（都是为正确性）：
1. 参数化 --revision-id，不改动既有题库清单；
2. **每题只取一条解析**（优先 is_default，其次最长）。原脚本用 LEFT JOIN 会把「每题多条解析」
   的题库按解析条数打重（米720 每题 2 条解析，会从 785 变 1570）。

学科名映射：本题库的章节父节点是「模块三 习近平新时代中国特色社会主义思想概论」这类，
官方大纲学科名是「新时代中国特色社会主义思想概论」——先剥掉「模块X 」前缀再做别名归一。

用法（连哪台库由 --config 里 fba_prod.DATABASE_URI 决定）：
    cd backend
    uv run python -m scripts.qbank.label.export_bank_label_data \
        --revision-id 1625 --bank-name "【27版】米李720题" --out mi_li_720_data.json
"""

import argparse
import asyncio
import json
import re
from pathlib import Path
from typing import Any

import asyncpg

MCP_CONFIG = Path(r"C:\Users\19396\.gemini\antigravity\mcp_config.json")
SERVER_KEY = "fba_prod"
DATA_DIR = Path(__file__).resolve().parents[2] / "seed" / "data"
OFFICIAL_DATA_PATH = DATA_DIR / "benchmark_data_2026.json"

# 题库模块名（剥掉「模块X 」前缀后）-> 官方大纲学科名
SUBJECT_ALIASES = {
    "马克思主义基本原理": "马克思主义基本原理概论",
    "马克思主义基本原理概论": "马克思主义基本原理概论",
    "马原": "马克思主义基本原理概论",
    "毛泽东思想和中国特色社会主义理论体系概论": "毛泽东思想和中国特色社会主义理论体系概论",
    "毛中特": "毛泽东思想和中国特色社会主义理论体系概论",
    "习近平新时代中国特色社会主义思想概论": "新时代中国特色社会主义思想概论",
    "新时代中国特色社会主义思想概论": "新时代中国特色社会主义思想概论",
    "习思想": "新时代中国特色社会主义思想概论",
    "新思想": "新时代中国特色社会主义思想概论",
    "中国近现代史纲要": "中国近现代史纲要",
    "中国近代史纲要": "中国近现代史纲要",
    "史纲": "中国近现代史纲要",
    "思想道德与法治": "思想道德修养与法律基础",
    "思想道德修养与法律基础": "思想道德修养与法律基础",
    "思修法基": "思想道德修养与法律基础",
    "思修": "思想道德修养与法律基础",
    "形势政策以及当代世界经济与政治": "形势政策以及当代世界经济与政治",
    "时政": "形势政策以及当代世界经济与政治",
}

MODULE_PREFIX = re.compile(r"^模块[一二三四五六七八九十]+\s*")
# 章号标识：第一章 / 导论 / 绪论 / 导言 / 第一部分
CHAPTER_KEY = re.compile(r"(第[一二三四五六七八九十百]+章|导论|绪论|导言|第[一二三四五六七八九十]+部分)")
PAREN = re.compile(r"（[^）]*）|\([^)]*\)")


def clean_name(name: str | None) -> str:
    if not name:
        return ""
    # 去掉括号补充说明，并去掉所有空白（题库里存在「导 论」「绪 论 XXX」这种带空格写法）
    return re.sub(r"\s+", "", PAREN.sub("", name))


def canonical_subject(raw: str | None) -> str:
    if not raw:
        return ""
    stripped = MODULE_PREFIX.sub("", raw).strip()
    return SUBJECT_ALIASES.get(stripped, SUBJECT_ALIASES.get(raw.strip(), stripped))


def chapter_key(name: str | None) -> str | None:
    m = CHAPTER_KEY.search(clean_name(name))
    return m.group(1) if m else None


def get_prod_uri() -> str:
    with open(MCP_CONFIG, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    return cfg["mcpServers"][SERVER_KEY]["env"]["DATABASE_URI"]


async def main() -> None:
    parser = argparse.ArgumentParser(description="导出某题库 revision 的标注数据包")
    parser.add_argument("--revision-id", type=int, required=True)
    parser.add_argument("--bank-name", required=True)
    parser.add_argument("--out", required=True, help="输出文件名（写入 scripts/seed/data/）")
    args = parser.parse_args()

    with open(OFFICIAL_DATA_PATH, "r", encoding="utf-8") as f:
        official = json.load(f)
    sections = official["sections"]
    section_meta = {s["section_id"]: s for s in sections}

    # (官方学科, 章号) -> chapter_id ；chapter_id -> [节 section_id]
    chapter_map: dict[tuple[str, str], int] = {}
    chapter_sections: dict[int, list[int]] = {}
    subject_sections: dict[str, list[int]] = {}
    for s in sections:
        sub = s["subject_name"]
        ck = chapter_key(s["chapter_name"])
        if ck:
            chapter_map[(sub, ck)] = s["chapter_id"]
        chapter_sections.setdefault(s["chapter_id"], []).append(s["section_id"])
        subject_sections.setdefault(sub, []).append(s["section_id"])

    conn = await asyncpg.connect(get_prod_uri())
    try:
        rows = await conn.fetch(
            """
            SELECT s.id AS section_id, s.name AS section_name, s.depth,
                   p.id AS parent_id, p.name AS parent_name
            FROM fba.qbank_v2_bank_section s
            LEFT JOIN fba.qbank_v2_bank_section p ON s.parent_id = p.id
            WHERE s.bank_revision_id = $1 AND s.deleted = 0 AND s.depth = 1
            ORDER BY s.sort_order, s.id
            """,
            args.revision_id,
        )

        items = await conn.fetch(
            """
            SELECT bi.id AS item_id, bi.section_id, bi.sort_order,
                   q.id AS question_id, q.question_type, q.stem, q.option_data,
                   (SELECT e.content FROM fba.qbank_v2_question_explanation e
                     WHERE e.question_id = q.id AND e.deleted = 0
                     ORDER BY e.is_default DESC, length(e.content) DESC
                     LIMIT 1) AS explanation
            FROM fba.qbank_v2_bank_item bi
            JOIN fba.qbank_v2_question q ON q.id = bi.question_id
            WHERE bi.bank_revision_id = $1 AND bi.deleted = 0
            ORDER BY bi.section_id, bi.sort_order
            """,
            args.revision_id,
        )
    finally:
        await conn.close()

    section_mappings: list[dict[str, Any]] = []
    unmatched: list[str] = []
    for r in rows:
        sid = r["section_id"]
        sname = r["section_name"]
        sub = canonical_subject(r["parent_name"])
        ck = chapter_key(sname)
        ch_id = chapter_map.get((sub, ck)) if ck else None
        if ch_id:
            cand = chapter_sections.get(ch_id, [])
        else:
            cand = subject_sections.get(sub, [])
            unmatched.append(f"sid={sid} {sub} | {sname}")
        section_mappings.append({
            "bank_section_id": sid,
            "parent_subject_name": sub,
            "bank_section_name": sname,
            "target_chapter_name": sname,
            "official_chapter_id": ch_id,
            "candidate_section_ids": cand,
        })

    questions = []
    seen: set[int] = set()
    for r in items:
        qid = r["question_id"]
        if qid in seen:  # 防重（本题库应无重复，留个保险）
            continue
        seen.add(qid)
        questions.append({
            "item_id": r["item_id"],
            "question_id": qid,
            "bank_section_id": r["section_id"],
            "sort_order": r["sort_order"],
            "question_type": r["question_type"],
            "stem": r["stem"],
            "option_data": r["option_data"],
            "explanation": r["explanation"],
        })

    out = {
        "bank_name": args.bank_name,
        "bank_revision_id": args.revision_id,
        "section_mappings": section_mappings,
        "questions": questions,
    }
    out_path = DATA_DIR / args.out
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    print(f"[OK] {args.bank_name}: {len(questions)} 题, {len(section_mappings)} 个章节 -> {out_path.name}")
    if unmatched:
        print(f"[!] {len(unmatched)} 个章节未精确对齐，已降级为整学科候选池：")
        for u in unmatched[:20]:
            print("    -", u)
    else:
        print("[OK] 全部章节 100% 精确对齐到官方大纲")
    # 解析覆盖率
    no_expl = sum(1 for q in questions if not q["explanation"])
    print(f"[i] 解析覆盖：{len(questions) - no_expl}/{len(questions)}")


if __name__ == "__main__":
    asyncio.run(main())
