#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
2026 年考研政治真题知识点自动标注评测脚本
对比引擎：
1. 决策模型：阿里云百炼 System One 决策模型 (decision-model-preview)
2. LLM 认知推理：Happy 渠道 DeepSeek-V3 (deepseek-chat)
"""

import argparse
import json
import re
import time
import urllib.request
import urllib.error
from html import unescape
from pathlib import Path
from typing import Any

DATA_PATH = Path(__file__).resolve().parent.parent.parent / "seed" / "data" / "benchmark_data_2026.json"

# 百炼决策模型配置
ALIYUN_DECISION_URL = "https://ws-72im6229rwe2na8f.cn-beijing.maas.aliyuncs.com/compatible-mode/v1/systemone"
ALIYUN_DECISION_KEY = "sk-ws-H.PLLIXMI.ekJ3.MEUCIQDPDFSjp1KJYZkEYYHm91ZS3-P5Gh3bQiftd0cp9_mwIQIgQ2jttLTuEeeVeEw9Yh9xmSLZclt8FsKZzvJMNuxfk8c"
ALIYUN_MODEL = "decision-model-preview"

# Happy LLM 配置
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
    """根据考研政治统考严格题号规则定位科目"""
    # 589: 马原 (24节)
    # 590: 毛中特 (22节)
    # 591: 新思想 (51节)
    # 592: 史纲 (30节)
    # 593: 思修 (21节)
    # 594: 当代与时政 (7节)
    if sort_order in (1, 2, 3, 4, 17, 18, 19, 20, 21, 34):
        return [589]
    elif sort_order in (5, 6, 7, 8, 22, 23, 24, 25, 26, 35):
        return [590, 591]  # 毛中特与新思想通常交融
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


def call_aliyun_decision_model(question_text: str, candidates: list[dict[str, Any]]) -> dict[str, Any]:
    criteria = {}
    for c in candidates:
        criteria[str(c["section_id"])] = f"{c['chapter_name']} > {c['section_name']}"
        
    payload = {
        "state": question_text,
        "model": ALIYUN_MODEL,
        "questions": {
            "point": {
                "type": "choice",
                "instructions": "分析题干、选项与解析，严格判断该题考查的是 criteria 里的哪一个知识点？只能选一个最吻合的。",
                "criteria": criteria
            }
        }
    }
    
    headers = {
        "Authorization": f"Bearer {ALIYUN_DECISION_KEY}",
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0"
    }
    
    t0 = time.perf_counter()
    req = urllib.request.Request(ALIYUN_DECISION_URL, headers=headers, data=json.dumps(payload).encode("utf-8"))
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            latency = (time.perf_counter() - t0) * 1000
            ans = data.get("answers", {}).get("point", {})
            choice_id = ans.get("choice")
            conf = ans.get("confidence")
            prob = ans.get("probabilities", {}).get(str(choice_id), 0.0)
            return {
                "success": True,
                "point_id": int(choice_id) if choice_id and str(choice_id).isdigit() else None,
                "confidence": conf,
                "prob": prob,
                "latency_ms": round(latency, 1)
            }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "latency_ms": round((time.perf_counter() - t0) * 1000, 1)
        }


def call_happy_llm_model(question_text: str, candidates: list[dict[str, Any]]) -> dict[str, Any]:
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
    
    t0 = time.perf_counter()
    for attempt in range(2):
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
            if attempt == 0:
                time.sleep(1)
                continue
            return {
                "success": False,
                "error": str(e),
                "latency_ms": round((time.perf_counter() - t0) * 1000, 1)
            }
    return {"success": False, "error": "Unknown error", "latency_ms": 0}


def main():
    parser = argparse.ArgumentParser(description="2026考研政治真题自动标注评测")
    parser.add_argument("--limit", type=int, default=0, help="测试题目数量，0表示跑完整张卷38题")
    parser.add_argument("--start", type=int, default=1, help="起始题号(sort_order)")
    args = parser.parse_args()

    with open(DATA_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    questions = data["questions"]
    sections = data["sections"]
    
    sec_map = {s["section_id"]: s for s in sections}
    
    filtered_qs = [
        q for q in questions 
        if q["sort_order"] >= args.start
    ]
    if args.limit > 0:
        filtered_qs = filtered_qs[:args.limit]
        
    print(f"=== 开始 2026 年考研政治真题评测 (测试题目数: {len(filtered_qs)}) ===")
    print(f"决策模型: {ALIYUN_MODEL} (System One)")
    print(f"LLM 认知推理: {HAPPY_MODEL} (Happy API)\n")
    
    results = []
    
    for q in filtered_qs:
        sort_order = q["sort_order"]
        sub_ids = get_subject_ids_by_sort_order(sort_order)
        candidates = [s for s in sections if s["subject_id"] in sub_ids]
        
        q_text = format_question_text(q)
        stem_brief = strip_html(q.get("stem"))[:45].replace("\n", " ") + "..."
        
        print(f"[{sort_order:02d}/38] 正在评估第 {sort_order} 题 (候选小节数: {len(candidates)})...")
        print(f"     题干: {stem_brief}")
        
        # 1. 调决策模型
        dec_res = call_aliyun_decision_model(q_text, candidates)
        # 2. 调 LLM
        llm_res = call_happy_llm_model(q_text, candidates)
        
        dec_sec = sec_map.get(dec_res.get("point_id"))
        llm_sec = sec_map.get(llm_res.get("point_id"))
        
        is_match = (
            dec_res.get("success") and 
            llm_res.get("success") and 
            dec_res.get("point_id") == llm_res.get("point_id")
        )
        
        item = {
            "sort_order": sort_order,
            "question_id": q["question_id"],
            "stem_brief": stem_brief,
            "decision_model": {
                "point_id": dec_res.get("point_id"),
                "point_name": f"{dec_sec['chapter_name']} -> {dec_sec['section_name']}" if dec_sec else "无",
                "confidence": dec_res.get("confidence"),
                "prob": dec_res.get("prob"),
                "latency_ms": dec_res.get("latency_ms"),
                "success": dec_res.get("success")
            },
            "llm_model": {
                "point_id": llm_res.get("point_id"),
                "point_name": f"{llm_sec['chapter_name']} -> {llm_sec['section_name']}" if llm_sec else "无",
                "confidence": llm_res.get("confidence"),
                "reason": llm_res.get("reason"),
                "latency_ms": llm_res.get("latency_ms"),
                "success": llm_res.get("success")
            },
            "consensus": is_match
        }
        results.append(item)
        
        status_tag = "✅ MATCH" if is_match else "⚠️ DIVERGE"
        print(f"     决策模型: ID={dec_res.get('point_id')} ({item['decision_model']['point_name']}) [置信度: {dec_res.get('confidence')}, {dec_res.get('latency_ms')}ms]")
        print(f"     LLM 推理: ID={llm_res.get('point_id')} ({item['llm_model']['point_name']}) [置信度: {llm_res.get('confidence')}, {llm_res.get('latency_ms')}ms]")
        print(f"     LLM 理由: {llm_res.get('reason')}")
        print(f"     自洽状态: {status_tag}\n")
        
        time.sleep(0.3)  # 温和间隔
        
    # 汇总统计
    total = len(results)
    matches = sum(1 for r in results if r["consensus"])
    match_rate = (matches / total) * 100 if total > 0 else 0
    avg_dec_latency = sum(r["decision_model"]["latency_ms"] for r in results) / total if total > 0 else 0
    avg_llm_latency = sum(r["llm_model"]["latency_ms"] for r in results) / total if total > 0 else 0
    
    print("=" * 60)
    print(f"【评估总结】")
    print(f"评估题目数: {total}")
    print(f"双轨自洽一致数: {matches} / {total} (一致率: {match_rate:.1f}%)")
    print(f"决策模型平均耗时: {avg_dec_latency:.1f} ms")
    print(f"LLM 推理平均耗时: {avg_llm_latency:.1f} ms")
    print("=" * 60)

    # 保存报告 JSON
    report_path = Path(__file__).resolve().parent.parent.parent / "seed" / "data" / "benchmark_result_2026.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump({
            "total": total,
            "matches": matches,
            "match_rate": match_rate,
            "avg_decision_latency_ms": avg_dec_latency,
            "avg_llm_latency_ms": avg_llm_latency,
            "results": results
        }, f, ensure_ascii=False, indent=2)
    print(f"详细评测结果已保存至: {report_path}")

    # 同时输出 Markdown 报告到 Artifacts 目录
    md_lines = [
        "# 2026 年考研政治真题知识点自动标注全卷评测报告",
        "",
        f"- **评测题目总量**：{total} 题（1~16 单选、17~33 多选、34~38 分析题）",
        f"- **LLM 认知推理引擎**：DeepSeek-V3 (`deepseek-chat`)",
        f"- **决策模型引擎**：阿里云百炼 System One (`decision-model-preview`)",
        f"- **双轨自洽一致数**：{matches} / {total} (一致率: {match_rate:.1f}%)",
        f"- **决策模型平均耗时**：{avg_dec_latency:.1f} ms",
        f"- **LLM 推理平均耗时**：{avg_llm_latency:.1f} ms",
        "",
        "---",
        "",
        "## 全卷 38 题详细判定明细",
        "",
        "| 题号 | 题干摘要 | LLM判定知识点 (DeepSeek-V3) | LLM置信度 | LLM核心归因理由 | 决策模型判定 (System One) | 置信度 | 自洽 |",
        "| :---: | :--- | :--- | :---: | :--- | :--- | :---: | :---: |"
    ]
    for r in results:
        status = "✅ 一致" if r["consensus"] else "⚠️ 分歧"
        llm_p = r["llm_model"]["point_name"]
        llm_c = r["llm_model"]["confidence"]
        llm_r = r["llm_model"]["reason"]
        dec_p = r["decision_model"]["point_name"]
        dec_c = r["decision_model"]["confidence"]
        md_lines.append(
            f"| **{r['sort_order']:02d}** | {r['stem_brief'][:30]}... | {llm_p} | `{llm_c}` | {llm_r} | {dec_p} | `{dec_c}` | {status} |"
        )
    md_content = "\n".join(md_lines)
    artifact_md = Path(r"C:\Users\19396\.gemini\antigravity\brain\738149b1-faa3-4504-9362-270670c0721b\2026年考研政治真题知识点自动标注全卷评测报告.md")
    with open(artifact_md, "w", encoding="utf-8") as f:
        f.write(md_content)
    print(f"Markdown 评测报告已保存至: {artifact_md}")


if __name__ == "__main__":
    main()
