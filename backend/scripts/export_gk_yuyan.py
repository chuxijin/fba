"""
从 MCP 工具输出的 JSON 文件中读取国考言语理解题目数据，生成 Markdown 文档。

用法：
  python backend/scripts/export_gk_yuyan.py <file1.json> [file2.json] ...

示例：
  python backend/scripts/export_gk_yuyan.py data_2024_2026.json data_2019_2023.json
"""

from __future__ import annotations

import ast
import html
import json
import re
import sys
from collections import OrderedDict
from datetime import datetime
from pathlib import Path

OUTPUT_DIR = Path(__file__).parent.parent / "output"
OUTPUT_FILE = OUTPUT_DIR / "gk_yuyan_2019_2026.md"


def strip_html(text: str | None) -> str:
    """去除 HTML 标签，保留纯文本和换行。"""
    if not text:
        return ""
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</p>\s*<p[^>]*>", "\n\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</?p[^>]*>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    text = html.unescape(text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def load_mcp_output(filepath: str) -> list[dict]:
    """读取 MCP 工具输出文件，解析题目数据。"""
    raw = Path(filepath).read_text(encoding="utf-8")
    obj = json.loads(raw)
    text_payload = obj["result"][0]["text"]
    return ast.literal_eval(text_payload)


def format_question(idx: int, row: dict) -> str:
    """格式化单道题目为 Markdown。"""
    parts: list[str] = []

    # 题号与题干
    stem = strip_html(row["stem"])
    parts.append(f"**{idx}.** {stem}")

    # 选项
    options = row.get("options") or []
    if options:
        for opt in sorted(options, key=lambda o: o.get("sort_order", 0)):
            code = opt.get("option_code", "")
            content = strip_html(opt.get("content", ""))
            parts.append(f"- {code}. {content}")

    # 答案
    answer_data = row.get("answer_data") or {}
    correct = answer_data.get("correct", "")
    if correct:
        parts.append(f"\n**答案：{correct}**")

    return "\n\n".join(parts)


def build_markdown(rows: list[dict]) -> str:
    """按年份和试卷分组，生成完整 Markdown。"""
    if not rows:
        return "> 未查询到符合条件的数据。"

    # 按 (年份, 试卷) 分组，保持顺序
    grouped: OrderedDict[tuple[int, str], list[dict]] = OrderedDict()
    for row in rows:
        key = (row["paper_year"], row["paper_name"])
        grouped.setdefault(key, []).append(row)

    lines: list[str] = []
    lines.append("# 国考行测 · 言语理解与表达 真题集")
    lines.append("")
    lines.append(f"> 题目数量：{len(rows)} 道")
    lines.append(f"> 试卷数量：{len(grouped)} 套")
    lines.append(f"> 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append("")
    lines.append("---")
    lines.append("")

    # 统计信息
    lines.append("## 统计概览")
    lines.append("")
    lines.append("| 年份 | 试卷数 | 题目数 |")
    lines.append("|------|--------|--------|")
    year_stats: OrderedDict[int, dict] = OrderedDict()
    for (year, _), qs in grouped.items():
        if year not in year_stats:
            year_stats[year] = {"papers": 0, "questions": 0}
        year_stats[year]["papers"] += 1
        year_stats[year]["questions"] += len(qs)
    for year, stats in year_stats.items():
        lines.append(f"| {year} | {stats['papers']} | {stats['questions']} |")
    lines.append("")
    lines.append("---")
    lines.append("")

    # 题目正文
    current_year = None
    idx = 0
    for (year, paper_name), questions in grouped.items():
        if year != current_year:
            if current_year is not None:
                lines.append("")
            lines.append(f"## {year} 年")
            lines.append("")
            current_year = year

        lines.append(f"### {paper_name}")
        lines.append("")

        for q in questions:
            idx += 1
            lines.append(format_question(idx, q))
            lines.append("")
            lines.append("---")
            lines.append("")

    return "\n".join(lines)


def main() -> None:
    if len(sys.argv) < 2:
        print("用法: python export_gk_yuyan.py <file1.json> [file2.json] ...")
        sys.exit(1)

    all_rows: list[dict] = []
    for filepath in sys.argv[1:]:
        print(f"读取: {filepath}")
        rows = load_mcp_output(filepath)
        print(f"  -> {len(rows)} 道题目")
        all_rows.extend(rows)

    print(f"\n共 {len(all_rows)} 道题目，正在生成 Markdown...")
    md = build_markdown(all_rows)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(md, encoding="utf-8")
    print(f"已导出到: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
