#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""构建「考点短语 → 官方节」的章约束映射任务（试标/全量通用）。

设计要点（依据业务反馈定稿）：
1. **映射必须约束在题目自己的章内**：题库的章节归属即官方分类，不得因考点短语出现某学科
   字眼就跨科/跨章挂靠。故每个短语的候选池 = 它所在章对应的官方节（通常 2~4 个）。
2. 考点短语取自每题解析首行 `📌 考点：XXX`；按去重短语为映射单元（同短语必然同章、同落点）。
3. 若某短语在其章内确实无法落点（例如「马原·导论」里混入的习近平思想考点），允许返回
   section_id=null，进入「暂缓/待人工确认」清单。

输入：seed/data/mi_li_720_data.json + seed/data/benchmark_data_2026.json
输出：seed/data/labeling/phrase_tasks_{scope}_{i}.md + phrase_tasks_{scope}_meta.json

用法：
    cd backend
    uv run python -m scripts.qbank.label.build_phrase_map_tasks --scope pilot
    uv run python -m scripts.qbank.label.build_phrase_map_tasks --scope full
"""

import argparse
import collections
import html as H
import json
import re
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parents[2] / "seed" / "data"
LABEL_DIR = DATA_DIR / "labeling"
BENCH_PATH = DATA_DIR / "benchmark_data_2026.json"
DATA_PATH = DATA_DIR / "mi_li_720_data.json"

KP_RE = re.compile(r"考点[：:]\s*(.+)")


def strip_html(t: str | None) -> str:
    if not t:
        return ""
    t = re.sub(r"<br\s*/?>", "\n", str(t), flags=re.I)
    t = re.sub(r"</(p|div|li)>", "\n", t, flags=re.I)
    t = re.sub(r"<[^>]+>", "", t)
    return re.sub(r"\n{2,}", "\n", H.unescape(t)).strip()


def kp_of(explanation: str | None) -> str | None:
    for line in strip_html(explanation).split("\n"):
        m = KP_RE.search(line)
        if m:
            return m.group(1).strip()
    return None


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scope", choices=["pilot", "full"], required=True)
    parser.add_argument("--batch-size", type=int, default=25)
    args = parser.parse_args()

    bench = json.loads(BENCH_PATH.read_text(encoding="utf-8"))
    secmeta = {s["section_id"]: s for s in bench["sections"]}
    data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    mapping = {m["bank_section_id"]: m for m in data["section_mappings"]}
    qmap = {q["question_id"]: q for q in data["questions"]}

    if args.scope == "pilot":
        meta = json.loads((LABEL_DIR / "pilot_meta.json").read_text(encoding="utf-8"))
        scope_qids = set(int(k) for k in meta["questions"])
    else:
        scope_qids = set(qmap)

    # 短语 -> {qids, 章 key, 章候选节, 例句}
    phrases: dict[str, dict] = collections.OrderedDict()
    for qid in sorted(scope_qids):
        q = qmap[qid]
        ph = kp_of(q["explanation"])
        if not ph:
            continue
        m = mapping[q["bank_section_id"]]
        chap_key = f"{m['parent_subject_name']} · {m['bank_section_name']}"
        rec = phrases.setdefault(ph, {
            "qids": [], "chap_key": chap_key,
            "candidates": m["candidate_section_ids"],
            "bank_section_id": m["bank_section_id"],
            "sample_stem": strip_html(q["stem"])[:80],
        })
        rec["qids"].append(qid)

    # 一致性自检：同短语必须同章
    for ph, rec in phrases.items():
        if rec["chap_key"] == "":
            raise SystemExit(f"短语缺少章: {ph}")

    def cand_block(ids: list[int]) -> str:
        out = []
        for sid in ids:
            s = secmeta.get(sid)
            nm = f"{s['chapter_name']} > {s['section_name']}" if s else f"section_{sid}"
            out.append(f"  id={sid}  {nm}")
        return "\n".join(out)

    phrases_list = list(phrases.items())
    batches = [phrases_list[i:i + args.batch_size] for i in range(0, len(phrases_list), args.batch_size)]
    out_meta = {"scope": args.scope, "phrase_count": len(phrases_list), "phrases": {}}

    for bi, batch in enumerate(batches, 1):
        lines = [
            f"# 考点短语 → 官方节 映射（{args.scope}）· 批次 {bi}/{len(batches)}",
            "",
            "## 任务",
            "对下面每个【考点短语】，**只能从它自己的【本章候选节】里**选出唯一最贴切的 `id`。",
            "题库的章节归属是官方分类，**不得跨章跨科挂靠**。",
            "若该考点确实无法在本章任何一个候选节中合理落点，则该条 `section_id` 填 null，并在 reason 说明。",
            "",
            "## 输出（严格）",
            "最终**只输出一个 JSON 数组**，不要任何多余文字或代码块，元素：",
            '{"phrase": "<原样复制考点短语>", "section_id": <int 或 null>, "confidence": <0-1>, "reason": "<25字以内>"}',
            "",
        ]
        for ph, rec in batch:
            lines += [
                "---",
                f"### 考点短语：{ph}",
                f"所属章：{rec['chap_key']}",
                "【本章候选节（只能选这里的 id）】",
                cand_block(rec["candidates"]),
                f"【例句题干】{rec['sample_stem']} …",
                "",
            ]
        p = LABEL_DIR / f"phrase_tasks_{args.scope}_{bi}.md"
        p.write_text("\n".join(lines), encoding="utf-8")
        for ph, rec in batch:
            out_meta["phrases"][ph] = {
                "chap_key": rec["chap_key"], "candidates": rec["candidates"],
                "qids": rec["qids"], "bank_section_id": rec["bank_section_id"],
            }
        print(f"写出 {p.name} ({len(batch)} 短语)")

    (LABEL_DIR / f"phrase_tasks_{args.scope}_meta.json").write_text(
        json.dumps(out_meta, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"写出 phrase_tasks_{args.scope}_meta.json：{len(phrases_list)} 个短语 / {len(batches)} 批")


if __name__ == "__main__":
    main()
