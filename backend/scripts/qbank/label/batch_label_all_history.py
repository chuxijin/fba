#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
2015-2025 考研政治历年真题全量自动标注脚本
引擎：Happy 渠道 DeepSeek-V3 (deepseek-chat)
特性：
1. 严格学科过滤（基于统考题号规则）
2. 逐卷断点续传（单题保存，意外中断无需重跑）
3. 超时指数退避重试（最多3次）
4. 自动生成每卷与全量落库 SQL
"""

import argparse
import json
import os
import re
import time
import urllib.request
import urllib.error
from html import unescape
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent.parent.parent / "seed" / "data"
BENCHMARK_2026_PATH = BASE_DIR / "benchmark_data_2026.json"
HISTORY_PAPERS_PATH = BASE_DIR / "all_history_papers.json"

HAPPY_API_URL = "https://happyapi.org/v1/chat/completions"
HAPPY_API_KEY = "sk-7tgJkgLC2asCQhqCE1180041615a4a0c87E6399e0d6bE837"
HAPPY_MODEL = "deepseek-chat"


def strip_html(content: str | None) -> str:
    if not content:
        return ""
    val = re.sub(r"<br\s*/?>", "\n", str(content), flags=re.IGNORECASE)
    val = re.sub(r"</(p|div|li)>", "\n", val, flags=re.IGNORECASE)
    val = re.sub(r"<[^>]+>", "", val)
    return re.sub(r"\n{2,}", "\n", unescape(val)).strip()


def get_subject_ids_by_sort_order(sort_order: int) -> list[int]:
    """根据考研政治统考严格题号规则定位学科"""
    # 589: 马原 (24节)
    # 590: 毛中特 (22节)
    # 591: 新思想 (51节)
    # 592: 史纲 (30节)
    # 593: 思修 (21节)
    # 594: 当代与时政 (7节)
    if sort_order in (1, 2, 3, 4, 17, 18, 19, 20, 21, 34):
        return [589]
    elif sort_order in (5, 6, 7, 8, 22, 23, 24, 25, 26, 35):
        return [590, 591]  # 毛中特与新思想交融
    elif sort_order in (9, 10, 11, 12, 27, 28, 29, 36):
        return [592]
    elif sort_order in (13, 14, 30, 31, 37):
        return [593]
    elif sort_order in (15, 16, 32, 33, 38):
        return [594]
    return [589, 590, 591, 592, 593, 594]


def format_question_text(q: dict[str, Any]) -> str:
    stem = strip_html(q.get("stem"))
    qtype = q.get("question_type") or "未知题型"
    type_name = "单项选择题" if qtype == "single_choice" else ("多项选择题" if qtype == "multiple_choice" else "分析题")
    
    parts = [f"【题型】第 {q['sort_order']} 题 · {type_name}", f"【题干】\n{stem}"]
    
    opts = q.get("option_data") or []
    if isinstance(opts, str):
        try:
            opts = json.loads(opts)
        except Exception:
            opts = []
            
    if opts:
        opt_lines = []
        for i, opt in enumerate(opts):
            code = opt.get("option_code") or chr(65 + i)
            c = strip_html(opt.get("content"))
            opt_lines.append(f"{code}. {c}")
        parts.append("【选项】\n" + "\n".join(opt_lines))
        
    expl = strip_html(q.get("explanation"))
    if expl:
        parts.append(f"【解析】\n{expl}")
        
    return "\n\n".join(parts)


def call_llm(question_text: str, candidates: list[dict[str, Any]]) -> dict[str, Any]:
    candidate_lines = [
        f"ID {c['section_id']}: [{c['subject_name']}] {c['chapter_name']} -> {c['section_name']}"
        for c in candidates
    ]
    
    prompt = f"""你是一名资深考研政治教研命题专家。请分析以下考研政治试题的考查本质，并从候选知识点小节清单中选出唯一最准确的归属知识点。

{question_text}

【候选知识点小节清单】
{chr(10).join(candidate_lines)}

【答题要求】
1. 深入分析题干情境、正确选项及试题解析揭示的实质性哲学范畴/历史事件/理论体系。
2. 只能从上述候选清单中选择一个 ID。
3. 请严格返回纯 JSON 格式，不要包含任何 markdown 标记（不要 ```json），格式如下：
{{"point_id": 候选ID数字, "confidence": 0.0到1.0的置信度, "reason": "30字以内的定性依据"}}
"""

    headers = {
        "Authorization": f"Bearer {HAPPY_API_KEY}",
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0"
    }
    
    data = {
        "model": HAPPY_MODEL,
        "messages": [
            {"role": "system", "content": "你只输出严格的 JSON 字符串。"},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.1,
        "max_tokens": 150
    }
    
    for attempt in range(3):
        t0 = time.perf_counter()
        try:
            req = urllib.request.Request(HAPPY_API_URL, headers=headers, data=json.dumps(data).encode("utf-8"))
            with urllib.request.urlopen(req, timeout=35) as resp:
                res_obj = json.loads(resp.read().decode("utf-8"))
                latency = (time.perf_counter() - t0) * 1000
                content = res_obj["choices"][0]["message"]["content"].strip()
                if content.startswith("```"):
                    content = re.sub(r"^```(?:json)?\s*", "", content)
                    content = re.sub(r"\s*```$", "", content)
                parsed = json.loads(content)
                return {
                    "success": True,
                    "point_id": int(parsed.get("point_id")) if parsed.get("point_id") else None,
                    "confidence": float(parsed.get("confidence", 0.0)),
                    "reason": parsed.get("reason", ""),
                    "latency_ms": round(latency, 1)
                }
        except Exception as e:
            wait_sec = 2 * (attempt + 1)
            print(f"       [重试 {attempt + 1}/3] 接口异常: {e}，等待 {wait_sec}s...")
            time.sleep(wait_sec)
            
    return {"success": False, "error": "Max retries exceeded", "latency_ms": 0}


def build_sql_for_paper(results: list[dict[str, Any]]) -> str:
    qids = [r["question_id"] for r in results if r.get("point_id")]
    if not qids:
        return ""
    qids_str = ", ".join(str(q) for q in qids)
    
    soft_del = f"""UPDATE fba.qbank_v2_question_knowledge_point qkp
SET deleted = qkp.id, deleted_time = NOW()
FROM fba.qbank_v2_knowledge_point kp
WHERE qkp.knowledge_point_id = kp.id
  AND kp.system_id = 8
  AND qkp.question_id IN ({qids_str})
  AND qkp.deleted = 0;"""

    value_rows = []
    for r in results:
        qid = r["question_id"]
        pid = r.get("point_id")
        conf = r.get("confidence", 0.95)
        if pid:
            value_rows.append(f"({qid}, {pid}, 'primary', 1.0000, 'ai', {conf:.4f}, 1, 1, NOW(), 0)")
            
    ins = "INSERT INTO fba.qbank_v2_question_knowledge_point\n  (question_id, knowledge_point_id, role, weight, source, confidence, created_by, updated_by, created_time, deleted)\nVALUES\n  " + ",\n  ".join(value_rows) + ";"
    return f"{soft_del}\n\n{ins}\n"


def main():
    parser = argparse.ArgumentParser(description="2015-2025考研政治历年真题全量自动标注")
    parser.add_argument("--rev-id", type=int, default=0, help="仅跑指定试卷 bank_revision_id，0为全跑")
    args = parser.parse_args()

    # 读取知识点元数据
    with open(BENCHMARK_2026_PATH, "r", encoding="utf-8") as f:
        bench_data = json.load(f)
    sections = bench_data["sections"]
    sec_map = {s["section_id"]: s for s in sections}

    # 读取 418 道历史真题
    with open(HISTORY_PAPERS_PATH, "r", encoding="utf-8") as f:
        all_questions = json.load(f)

    # 按试卷分组
    papers: dict[int, list[dict[str, Any]]] = {}
    for q in all_questions:
        rev_id = q["bank_revision_id"]
        if rev_id not in papers:
            papers[rev_id] = []
        papers[rev_id].append(q)

    # 排序：年份从新到旧
    sorted_rev_ids = sorted(papers.keys(), reverse=True)
    if args.rev_id > 0:
        sorted_rev_ids = [args.rev_id]

    print(f"=== 考研政治历年真题全量自动标注启动 ===")
    print(f"待处理试卷数: {len(sorted_rev_ids)} 套，题目总数: {sum(len(papers[rid]) for rid in sorted_rev_ids)} 题")
    print(f"模型: {HAPPY_MODEL} (DeepSeek-V3)\n")

    total_all_results = []
    
    for p_idx, rev_id in enumerate(sorted_rev_ids, 1):
        q_list = sorted(papers[rev_id], key=lambda x: x["sort_order"])
        paper_name = q_list[0]["paper_name"]
        print(f"\n==================================================")
        print(f"【{p_idx}/{len(sorted_rev_ids)}】正在处理试卷: {paper_name} (rev_id={rev_id}, 共 {len(q_list)} 题)")
        print(f"==================================================")

        cache_file = BASE_DIR / f"labels_rev_{rev_id}.json"
        cached_results: dict[int, dict[str, Any]] = {}
        if cache_file.exists():
            try:
                with open(cache_file, "r", encoding="utf-8") as f:
                    for item in json.load(f):
                        cached_results[item["question_id"]] = item
                print(f"已从缓存加载该卷 {len(cached_results)} 道已标注题目")
            except Exception:
                pass

        paper_results = []
        for q in q_list:
            qid = q["question_id"]
            sort_order = q["sort_order"]
            stem_brief = strip_html(q.get("stem"))[:35].replace("\n", " ") + "..."

            if qid in cached_results and cached_results[qid].get("success") and cached_results[qid].get("point_id"):
                res_item = cached_results[qid]
                paper_results.append(res_item)
                sec_info = sec_map.get(res_item.get("point_id"))
                sec_name = f"{sec_info['chapter_name']} -> {sec_info['section_name']}" if sec_info else ""
                print(f"  [{sort_order:02d}/38] 题号{qid} [跳过/已缓存] -> {sec_name}")
                continue

            sub_ids = get_subject_ids_by_sort_order(sort_order)
            candidates = [s for s in sections if s["subject_id"] in sub_ids]
            q_text = format_question_text(q)

            print(f"  [{sort_order:02d}/38] 题号{qid} 处理中: {stem_brief}")
            llm_res = call_llm(q_text, candidates)
            point_id = llm_res.get("point_id")
            conf = llm_res.get("confidence")
            reason = llm_res.get("reason")
            sec_info = sec_map.get(point_id)
            sec_name = f"{sec_info['chapter_name']} -> {sec_info['section_name']}" if sec_info else "未匹配"

            print(f"         -> 命中: ID={point_id} ({sec_name}) [置信度: {conf}]")
            print(f"         -> 归因: {reason}")

            res_item = {
                "bank_revision_id": rev_id,
                "paper_name": paper_name,
                "question_id": qid,
                "sort_order": sort_order,
                "point_id": point_id,
                "point_name": sec_name,
                "confidence": conf,
                "reason": reason,
                "latency_ms": llm_res.get("latency_ms"),
                "success": llm_res.get("success", False)
            }
            paper_results.append(res_item)
            cached_results[qid] = res_item

            # 实时追加单题缓存
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(list(cached_results.values()), f, ensure_ascii=False, indent=2)

            time.sleep(0.3)

        # 该套卷完成，生成该卷 SQL
        paper_sql = build_sql_for_paper(paper_results)
        paper_sql_file = BASE_DIR / f"apply_rev_{rev_id}.sql"
        with open(paper_sql_file, "w", encoding="utf-8") as f:
            f.write(paper_sql)
        print(f"【{paper_name}】全部标注完成！落库 SQL 已保存至: {paper_sql_file}")

        total_all_results.extend(paper_results)

    # 生成全量 SQL
    all_sql = build_sql_for_paper(total_all_results)
    all_sql_file = BASE_DIR / "apply_all_418_labels.sql"
    with open(all_sql_file, "w", encoding="utf-8") as f:
        f.write(all_sql)
    print(f"\n==================================================")
    print(f"🎉 全部 418 道真题标注完毕！全量落库 SQL 已保存至: {all_sql_file}")
    print(f"==================================================")


if __name__ == "__main__":
    main()
