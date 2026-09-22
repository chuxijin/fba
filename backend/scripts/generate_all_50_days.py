# -*- coding: utf-8 -*-
"""
批量生成 50 份公考行测提速专项突破特训题卡 (Day 00 ~ Day 50)
每份包含 62 题：
1. 基础计算 50 题（5 类各 10 题）
2. 资料分析 12 题（基期量 4 题、增长量 4 题、上下立体分数比大小 4 题）
3. 卷末全卷 62 题 5 列顿号速查参考答案

优化机制：
- 先批量并发/流式生成所有 .docx 题本（含 OMML 原生矢量公式转译与物理净化）；
- 复用单个 Word 自动化 COM 进程批量编译输出矢量 PDF，大幅降低启动开销，保证 100% 稳定高效。
"""

import sys
from pathlib import Path
import time
import shutil
import tempfile

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.plugin.render_book.schema.payload import (
    RenderBookMeta,
    RenderDocumentPayload,
    RenderPaperPayload,
    RenderPlanPayload,
    RenderQuestionPayload,
    RenderSectionPayload,
)
from backend.plugin.render_book.schema.render import RenderOptions, RenderOutputTargets
from backend.plugin.render_book.service.adapters.basic_calc_adapter import adapt_basic_calc_payload
from backend.plugin.render_book.service.docx_engine import docx_render_engine
from backend.plugin.render_book.utils.template_catalog import TEMPLATES_ROOT
from backend.scripts.gongkao_question_generator import GongkaoQuestionGenerator


def build_day_payload(day_idx: int) -> RenderDocumentPayload:
    """生成指定 Day 的完整 RenderDocumentPayload"""
    # 种子与 day_idx 绑定，确保可复现且无重复
    gen = GongkaoQuestionGenerator(seed=202600 + day_idx)
    day_data = gen.generate_day_payload_data(day_index=day_idx)

    sections = []
    global_num = 1

    for sec_key, sec_title, q_list, q_type, type_lbl in day_data["sections_def"]:
        q_payloads = [
            RenderQuestionPayload(
                number=global_num + i,
                question_id=global_num + i,
                type=q_type,
                type_label=type_lbl,
                stem_text=stem,
                answer_text=ans,
            )
            for i, (stem, ans) in enumerate(q_list)
        ]
        global_num += len(q_payloads)
        sections.append(RenderSectionPayload(
            key=sec_key,
            title=sec_title,
            questions=q_payloads,
        ))

    total_q = global_num - 1
    # 62 题建议 31 分钟
    suggested_time = 31

    return RenderDocumentPayload(
        template_key="basic_calculation",
        render_plan=RenderPlanPayload(
            book_kind="custom",
            content_mode="questions_with_answers",
            answer_layout="appendix",
            delivery_mode="single_pdf",
            solution_mode="appendix",
            output_targets=RenderOutputTargets(),
        ),
        options=RenderOptions(include_answer=True, include_analysis=False),
        book=RenderBookMeta(
            title=day_data["title"],
            subtitle=day_data["subtitle"],
        ),
        paper=RenderPaperPayload(
            title=day_data["title"],
            subtitle="",
            question_count=total_q,
            suggested_time=suggested_time,
            material_count=0,
            sections=sections,
            materials=[],
        ),
        metadata={"user_id": 999, "nickname": "学员", "day": day_idx},
    )


def batch_generate_50_days():
    start_time = time.time()
    output_dir = PROJECT_ROOT / "backend" / "output" / "50_days_pack"
    output_dir.mkdir(parents=True, exist_ok=True)
    template_file = TEMPLATES_ROOT / "basic_calculation" / "1.0.0" / "template.docx"

    # 生成 Day 00 到 Day 50（共 51 份，全面覆盖 0~50）
    day_indices = list(range(0, 51))
    total_days = len(day_indices)
    print(f"==================================================")
    print(f" 开始批量生成行测提速专项突破特训题卡 (Day 00 ~ Day 50, 共 {total_days} 份)")
    print(f" 目标目录: {output_dir}")
    print(f"==================================================")

    # 阶段 1：批量渲染所有 .docx 文件
    docx_files = []
    print("\n[阶段 1/2] 正在批量渲染 Word 题本与公式矢量转译...")
    for idx, day in enumerate(day_indices, start=1):
        base_name = f"Day_{day:02d}"
        payload = build_day_payload(day)
        ctx = adapt_basic_calc_payload(payload)

        # 仅渲染 docx
        output_docx = output_dir / f"{base_name}.docx"
        docx_path = docx_render_engine.render_docx(
            template_file=template_file,
            context=ctx,
            output_docx=output_docx,
        )
        docx_files.append((day, docx_path))
        if idx % 10 == 0 or idx == total_days:
            print(f" - 已完成 Word 渲染: {idx}/{total_days} 份")

    # 阶段 2：复用单 Word 进程批量编译矢量 PDF
    print("\n[阶段 2/2] 启动 Word 原生引擎批量编译矢量 PDF...")
    import win32com.client

    pdf_files = []
    word = win32com.client.DispatchEx("Word.Application")
    word.Visible = False
    word.DisplayAlerts = 0

    try:
        for idx, (day, docx_path) in enumerate(docx_files, start=1):
            pdf_path = output_dir / f"Day_{day:02d}.pdf"
            with tempfile.TemporaryDirectory() as tmp_dir:
                tmp_docx = Path(tmp_dir) / "temp.docx"
                tmp_pdf = Path(tmp_dir) / "temp.pdf"
                shutil.copyfile(docx_path, tmp_docx)

                doc = word.Documents.Open(str(tmp_docx), ReadOnly=1)
                doc.SaveAs(str(tmp_pdf), FileFormat=17)  # 17 = wdFormatPDF
                doc.Close(0)

                shutil.copyfile(tmp_pdf, pdf_path)
                pdf_files.append(pdf_path)

            if idx % 10 == 0 or idx == total_days:
                print(f" - 已完成 PDF 矢量编译: {idx}/{total_days} 份")
    finally:
        word.Quit()

    elapsed = time.time() - start_time
    print(f"\n==================================================")
    print(f" 批量生成圆满完成！")
    print(f" 总生成份数: {len(pdf_files)} 份 (Day 00 ~ Day 50)")
    print(f" 总耗时: {elapsed:.1f} 秒 (平均每份 {elapsed/len(pdf_files):.2f} 秒)")
    print(f" 文件存放路径: {output_dir}")
    print(f"==================================================")


if __name__ == "__main__":
    batch_generate_50_days()
