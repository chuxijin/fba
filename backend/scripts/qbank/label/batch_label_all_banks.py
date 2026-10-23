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
HAPPY_MODEL = "deepseek/deepseek-v4.1-flash"


def strip_html(content: str | None) -> str:
    if not content:
        return ""
    val = re.sub(r"<br\s*/?>", "\n", str(content), flags=re.IGNORECASE)
    val = re.sub(r"</(p|div|li)>", "\n", val, flags=re.IGNORECASE)
    val = re.sub(r"<[^>]+>", "", val)
    return re.sub(r"\n{2,}", "\n", unescape(val)).strip()


def format_question_text(q: dict[str, Any], context_label: str) -> str:
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
        f"【上下文归属】{context_label}",
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


def call_llm_select(question_text: str, candidates: list[dict[str, Any]], scope_desc: str) -> dict[str, Any]:
    # 按章节对候选进行分组展示，提升可读性
    lines = []
    curr_chapter = ""
    for c in candidates:
        ch_name = c.get("chapter_name", "")
        if ch_name and ch_name != curr_chapter:
            curr_chapter = ch_name
            lines.append(f"【{curr_chapter}】")
        lines.append(f"  ID {c['section_id']}: {c['section_name']}")
    
    prompt = f"""你是一名资深考研政治教研老师。已知本题属于【{scope_desc}】，请在以下考点候选清单中选出最贴切的一个小节。

{question_text}

【候选小节清单（只能选其中一个ID）】
{chr(10).join(lines)}

【答题要求】
1. 深入分析题干考查的实质考点与正确选项的理论定位。
2. 只能从上述候选清单中选择一个 ID。
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
    parser = argparse.ArgumentParser(description="考研政治全名师题库智能高精度多线程标注流水线")
    parser.add_argument("--bank", type=str, required=True, 
                        choices=["tuijie", "xiao", "yangpan", "xutao_basic", "xutao_hexin", "xutao_bagao", "xutao_10juan", "mi", "yu"], 
                        help="指定题库代号")
    parser.add_argument("--workers", type=int, default=6, help="并发线程数")
    parser.add_argument("--limit", type=int, default=0, help="限制跑题数量")
    parser.add_argument("--apply", action="store_true", help="标注完成后自动执行 SQL 写入生产数据库")
    args = parser.parse_args()

    bank_configs = {
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
        },
        "xutao_basic": {
            "name": "【27版】U题库 | 基础题篇 (徐涛)",
            "data_file": "xutao_basic_645_data.json",
            "cache_file": "xutao_basic_645_results_cache.json",
            "sql_prefix": "apply_xutao_basic"
        },
        "xutao_hexin": {
            "name": "【27版】核心考案 | 课后习题篇 (徐涛)",
            "data_file": "xutao_hexin_115_data.json",
            "cache_file": "xutao_hexin_115_results_cache.json",
            "sql_prefix": "apply_xutao_hexin"
        },
        "xutao_bagao": {
            "name": "【27版】U题库 | 拔高题篇 (徐涛)",
            "data_file": "xutao_bagao_630_data.json",
            "cache_file": "xutao_bagao_630_results_cache.json",
            "sql_prefix": "apply_xutao_bagao"
        },
        "xutao_10juan": {
            "name": "【27版】徐10套卷",
            "data_file": "xutao_10juan_330_data.json",
            "cache_file": "xutao_10juan_330_results_cache.json",
            "sql_prefix": "apply_xutao_10juan"
        },
        "mi": {
            "name": "27米1000题",
            "data_file": "mi_1000_data.json",
            "cache_file": "mi_1000_results_cache.json",
            "sql_prefix": "apply_mi"
        },
        "yu": {
            "name": "27余500题",
            "data_file": "yu_500_data.json",
            "cache_file": "yu_500_results_cache.json",
            "sql_prefix": "apply_yu"
        }
    }

    config = bank_configs[args.bank]
    data_path = BASE_DIR / config["data_file"]
    cache_path = BASE_DIR / config["cache_file"]

    # 1. 载入官方大纲字典
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

    print(f"=== {config['name']} 智能标注引擎启动 ===")
    print(f"题目总数: {len(all_questions)} 题")
    print(f"并发线程数: {args.workers}")
    print(f"推理模型: {HAPPY_MODEL}\n")

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
    print(f"待处理题目: {len(to_process)} 题\n")

    completed_count = len(cached_results)
    total_count = len(all_questions)

    def do_work(q):
        qid = q["question_id"]
        sec_id = q["bank_section_id"]
        sec_info = sec_mappings.get(sec_id)
        if not sec_info:
            return qid, {"question_id": qid, "success": False, "error": "No mapping found"}

        # 获取候选小节列表
        candidates = []
        if "candidate_section_ids" in sec_info and sec_info["candidate_section_ids"]:
            candidates = [sec_map[sid] for sid in sec_info["candidate_section_ids"] if sid in sec_map]
        elif "official_chapter_id" in sec_info and sec_info["official_chapter_id"]:
            candidates = chapter_sections.get(sec_info["official_chapter_id"], [])

        if not candidates:
            return qid, {"question_id": qid, "success": False, "error": "No candidates"}

        # 如果只有 1 个候选，直接落位
        if len(candidates) == 1:
            return qid, {
                "question_id": qid,
                "bank_section_id": sec_id,
                "point_id": candidates[0]["section_id"],
                "confidence": 1.0,
                "reason": "先验唯一候选直接落位",
                "latency_ms": 0.0,
                "success": True
            }

        # 组织上下文标签
        sub_name = sec_info.get("parent_subject_name") or sec_info.get("subject_name") or ""
        ch_name = sec_info.get("target_chapter_name") or sec_info.get("official_chapter_name") or sec_info.get("bank_section_name") or ""
        context_label = f"{sub_name} · {ch_name}".strip(" ·")

        q_text = format_question_text(q, context_label)
        llm_res = call_llm_select(q_text, candidates, context_label)
        
        return qid, {
            "question_id": qid,
            "bank_section_id": sec_id,
            "point_id": llm_res.get("point_id"),
            "confidence": llm_res.get("confidence", 0.0),
            "reason": llm_res.get("reason", ""),
            "latency_ms": llm_res.get("latency_ms", 0.0),
            "success": bool(llm_res.get("point_id"))
        }

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

                if completed_count % 15 == 0 or completed_count == total_count:
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
    chunk_paths = generate_sql_chunks(final_results, config["sql_prefix"], chunk_size=350)
    print("=" * 60)

    if args.apply:
        print("\n[*] 检测到 --apply 参数，开始执行自动生产落库...")
        import asyncio
        import importlib.util
        exec_path = Path(__file__).resolve().parent.parent.parent / "seed" / "execute_sql_file.py"
        spec = importlib.util.spec_from_file_location("execute_sql_file", exec_path)
        exec_mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(exec_mod)
        for cp in chunk_paths:
            print(f"[*] 正在自动执行落库: {cp.name}")
            asyncio.run(exec_mod.execute_file(str(cp)))
        print("[✓] 本题库所有分块已 100% 成功落库生产数据库！\n")


if __name__ == "__main__":
    main()
