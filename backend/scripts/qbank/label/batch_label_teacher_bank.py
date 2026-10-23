import argparse
import concurrent.futures
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
OFFICIAL_DATA_PATH = BASE_DIR / "benchmark_data_2026.json"

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


def format_question_text(q: dict[str, Any], chapter_name: str) -> str:
    stem = strip_html(q.get("stem"))
    qtype = q.get("question_type") or "未知题型"
    type_map = {
        "single": "单项选择题",
        "multiple": "多项选择题",
        "choice": "选择题",
        "analysis": "分析题"
    }
    type_name = type_map.get(qtype, qtype)
    
    parts = [
        f"【所属章节】{chapter_name}",
        f"【题型】{type_name}（题号：{q['question_id']}）",
        f"【题干】\n{stem}"
    ]
    
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


def call_llm_section(question_text: str, candidates: list[dict[str, Any]]) -> dict[str, Any]:
    candidate_lines = [
        f"ID {c['section_id']}: {c['section_name']}"
        for c in candidates
    ]
    
    prompt = f"""你是一名资深考研政治教研老师。已知本题属于该章，请在以下本章小节候选清单中选出最贴切的一个小节。

{question_text}

【本章小节候选清单（只能选其中一个ID）】
{chr(10).join(candidate_lines)}

【答题要求】
1. 分析题干本质与正确答案考查的实质考点。
2. 只能从上述本章候选清单中选择一个 ID。
3. 请严格返回纯 JSON 格式（不要包含任何 markdown 标记，不要 ```json）：
{{"point_id": 候选ID数字, "confidence": 0.0到1.0的置信度, "reason": "25字以内的定性理由"}}
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
        "max_tokens": 120
    }
    
    for attempt in range(3):
        t0 = time.perf_counter()
        try:
            req = urllib.request.Request(HAPPY_API_URL, headers=headers, data=json.dumps(data).encode("utf-8"))
            with urllib.request.urlopen(req, timeout=30) as resp:
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
            time.sleep(wait_sec)
            
    return {"success": False, "error": "Max retries exceeded", "latency_ms": 0}


def process_single_question(q: dict[str, Any], sec_mappings: dict[int, Any], chapter_sections: dict[int, Any], sec_map: dict[int, Any]) -> dict[str, Any]:
    qid = q["question_id"]
    sec_id = q["bank_section_id"]
    sec_info = sec_mappings.get(sec_id)
    if not sec_info:
        return {"question_id": qid, "success": False, "error": "No section mapping"}

    off_ch_id = sec_info["official_chapter_id"]
    off_ch_name = sec_info["official_chapter_name"]
    candidates = chapter_sections.get(off_ch_id, [])

    if len(candidates) == 1:
        return {
            "question_id": qid,
            "bank_section_id": sec_id,
            "official_chapter_id": off_ch_id,
            "chapter_name": off_ch_name,
            "point_id": candidates[0]["section_id"],
            "confidence": 1.0,
            "reason": "单节章节直接落位",
            "latency_ms": 0.0,
            "success": True
        }

    q_text = format_question_text(q, f"{sec_info['parent_subject_name']} · {off_ch_name}")
    llm_res = call_llm_section(q_text, candidates)
    return {
        "question_id": qid,
        "bank_section_id": sec_id,
        "official_chapter_id": off_ch_id,
        "chapter_name": off_ch_name,
        "point_id": llm_res.get("point_id"),
        "confidence": llm_res.get("confidence", 0.0),
        "reason": llm_res.get("reason", ""),
        "latency_ms": llm_res.get("latency_ms", 0.0),
        "success": bool(llm_res.get("point_id"))
    }


def generate_sql_chunks(results: list[dict[str, Any]], out_prefix: str, chunk_size: int = 350) -> list[Path]:
    valid_results = [r for r in results if r.get("point_id")]
    chunks = [valid_results[i:i + chunk_size] for i in range(0, len(valid_results), chunk_size)]
    
    saved_paths = []
    for idx, chunk in enumerate(chunks, 1):
        qids = [str(r["question_id"]) for r in chunk]
        soft_del = f"""UPDATE fba.qbank_v2_question_knowledge_point qkp
SET deleted = qkp.id, deleted_time = NOW()
FROM fba.qbank_v2_knowledge_point kp
WHERE qkp.knowledge_point_id = kp.id
  AND kp.system_id = 8
  AND qkp.question_id IN ({', '.join(qids)})
  AND qkp.deleted = 0;"""

        value_rows = []
        for r in chunk:
            qid = r["question_id"]
            pid = r["point_id"]
            conf = r.get("confidence", 0.95)
            value_rows.append(f"({qid}, {pid}, 'primary', 1.0000, 'ai', {conf:.4f}, 1, 1, NOW(), 0)")
            
        ins = "INSERT INTO fba.qbank_v2_question_knowledge_point\n  (question_id, knowledge_point_id, role, weight, source, confidence, created_by, updated_by, created_time, deleted)\nVALUES\n  " + ",\n  ".join(value_rows) + ";"
        
        sql = f"{soft_del}\n\n{ins}\n"
        p = BASE_DIR / f"{out_prefix}_chunk{idx}.sql"
        p.write_text(sql, encoding="utf-8")
        saved_paths.append(p)
        print(f"  -> 生成 Chunk {idx}: {len(chunk)} 题 -> {p.name} ({len(sql)} 字符)")
        
    return saved_paths


def main():
    parser = argparse.ArgumentParser(description="名师题库章内高精度多线程标注引擎")
    parser.add_argument("--bank", type=str, required=True, choices=["tuijie", "xiao", "yangpan"], help="指定题库")
    parser.add_argument("--workers", type=int, default=5, help="并发线程数")
    parser.add_argument("--limit", type=int, default=0, help="限制跑题数量")
    args = parser.parse_args()

    config = {
        "tuijie": {
            "name": "【27版】腿姐刷题计划",
            "data_file": "tuijie_1370_data.json",
            "cache_file": "tuijie_1370_results_cache.json",
            "sql_prefix": "apply_tuijie"
        },
        "xiao": {
            "name": "【27版】肖1000题",
            "data_file": "xiao_1147_data.json",
            "cache_file": "xiao_1147_results_cache.json",
            "sql_prefix": "apply_xiao"
        },
        "yangpan": {
            "name": "【27】杨攀刻意练题",
            "data_file": "yangpan_503_data.json",
            "cache_file": "yangpan_503_results_cache.json",
            "sql_prefix": "apply_yangpan"
        }
    }[args.bank]

    data_path = BASE_DIR / config["data_file"]
    cache_path = BASE_DIR / config["cache_file"]

    # 1. 载入官方大纲
    with open(OFFICIAL_DATA_PATH, "r", encoding="utf-8") as f:
        official_data = json.load(f)
    all_sections = official_data["sections"]
    sec_map = {s["section_id"]: s for s in all_sections}

    chapter_sections: dict[int, list[dict[str, Any]]] = {}
    for s in all_sections:
        ch_id = s["chapter_id"]
        if ch_id not in chapter_sections:
            chapter_sections[ch_id] = []
        chapter_sections[ch_id].append(s)

    # 2. 载入题库数据
    with open(data_path, "r", encoding="utf-8") as f:
        bank_data = json.load(f)
    sec_mappings = {m["bank_section_id"]: m for m in bank_data["section_mappings"]}
    all_questions = bank_data["questions"]

    if args.limit > 0:
        all_questions = all_questions[:args.limit]

    print(f"=== {config['name']} 章内高精度标注引擎启动 ===")
    print(f"待处理题目数: {len(all_questions)} 题")
    print(f"并发线程数: {args.workers}")
    print(f"模型: {HAPPY_MODEL} (DeepSeek-V3)\n")

    # 3. 载入缓存
    cached_results: dict[int, dict[str, Any]] = {}
    if cache_path.exists():
        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                for item in json.load(f):
                    if item.get("success") and item.get("point_id"):
                        cached_results[item["question_id"]] = item
            print(f"已从缓存加载 {len(cached_results)} 道已标注题目")
        except Exception:
            pass

    to_process = [q for q in all_questions if q["question_id"] not in cached_results]
    print(f"剩余待调用模型题目: {len(to_process)} 题\n")

    completed_count = len(cached_results)
    total_count = len(all_questions)

    def do_work(q):
        res = process_single_question(q, sec_mappings, chapter_sections, sec_map)
        return q["question_id"], res

    if to_process:
        with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as executor:
            future_to_q = {executor.submit(do_work, q): q for q in to_process}
            for future in concurrent.futures.as_completed(future_to_q):
                qid, res = future.result()
                cached_results[qid] = res
                completed_count += 1
                
                p_name = sec_map.get(res.get("point_id"), {}).get("section_name", "未知")
                conf = res.get("confidence", 0.0)
                lat = res.get("latency_ms", 0.0)
                print(f"[{completed_count:04d}/{total_count:04d}] 题号 {qid} -> {p_name} (置信度: {conf:.2f}, {lat}ms)")

                # 每 10 题保存一次缓存
                if completed_count % 10 == 0 or completed_count == total_count:
                    with open(cache_path, "w", encoding="utf-8") as f:
                        json.dump(list(cached_results.values()), f, ensure_ascii=False, indent=2)

    # 最终保存缓存
    with open(cache_path, "w", encoding="utf-8") as f:
        json.dump(list(cached_results.values()), f, ensure_ascii=False, indent=2)

    # 生成落库 SQL
    final_results = [cached_results[q["question_id"]] for q in all_questions if q["question_id"] in cached_results]
    print("\n" + "=" * 60)
    print(f"【标注统计】")
    print(f"题库: {config['name']}")
    print(f"题目总数: {len(final_results)}")
    success_count = sum(1 for r in final_results if r.get("success"))
    print(f"成功命中数: {success_count} ({success_count/len(final_results)*100:.1f}%)")
    avg_conf = sum(r.get("confidence", 0) for r in final_results) / len(final_results) if final_results else 0
    print(f"平均置信度: {avg_conf:.4f}")
    print("\n【生成落库 SQL 分块】")
    generate_sql_chunks(final_results, config["sql_prefix"], chunk_size=350)
    print("=" * 60)


if __name__ == "__main__":
    main()
