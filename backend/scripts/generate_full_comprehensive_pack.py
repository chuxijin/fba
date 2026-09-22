# -*- coding: utf-8 -*-
"""
生成全套公考行测速算与资料分析特训题卡：
1. 基础计算（5 类，每类 10 题，共 50 题）：
   (a) 10~19 乘以个位数
   (b) 三位数乘以一位数
   (c) 五位数除以三位数
   (d) 三位数的减法
   (e) 三位数的加法
2. 资料分析特训：
   - 求基期量（4列数据盒，8 题）
   - 求增长量（4列数据盒，8 题）
   - 分数大小比较（2列比较盒，上下立体分数，8 题）
3. 卷末答案速查（全 74 题顿号速查）
"""
import sys
from pathlib import Path
import time

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

def run():
    sections = []
    global_num = 1

    # ---------------- 1. 基础计算：10~19 乘以个位数 (10题) ----------------
    sec1_stems = [
        ("17 × 8 =", "136"),
        ("14 × 7 =", "98"),
        ("19 × 6 =", "114"),
        ("16 × 9 =", "144"),
        ("18 × 4 =", "72"),
        ("13 × 8 =", "104"),
        ("15 × 7 =", "105"),
        ("12 × 9 =", "108"),
        ("19 × 8 =", "152"),
        ("16 × 6 =", "96"),
    ]
    qs_sec1 = [
        RenderQuestionPayload(
            number=global_num + i,
            question_id=100 + global_num + i,
            type="blank",
            type_label="基础速算",
            stem_text=stem,
            answer_text=ans,
        )
        for i, (stem, ans) in enumerate(sec1_stems)
    ]
    global_num += len(qs_sec1)
    sections.append(RenderSectionPayload(
        key="sec_calc_1",
        title="一、基础计算：10~19 乘以个位数",
        questions=qs_sec1,
    ))

    # ---------------- 2. 基础计算：三位数乘以一位数 (10题) ----------------
    sec2_stems = [
        ("243 × 6 =", "1458"),
        ("418 × 4 =", "1672"),
        ("327 × 7 =", "2289"),
        ("519 × 3 =", "1557"),
        ("682 × 5 =", "3410"),
        ("715 × 8 =", "5720"),
        ("834 × 4 =", "3336"),
        ("196 × 9 =", "1764"),
        ("452 × 6 =", "2712"),
        ("378 × 8 =", "3024"),
    ]
    qs_sec2 = [
        RenderQuestionPayload(
            number=global_num + i,
            question_id=100 + global_num + i,
            type="blank",
            type_label="基础速算",
            stem_text=stem,
            answer_text=ans,
        )
        for i, (stem, ans) in enumerate(sec2_stems)
    ]
    global_num += len(qs_sec2)
    sections.append(RenderSectionPayload(
        key="sec_calc_2",
        title="二、基础计算：三位数乘以一位数",
        questions=qs_sec2,
    ))

    # ---------------- 3. 基础计算：五位数除以三位数 (10题) ----------------
    sec3_stems = [
        ("45238 ÷ 214 =", "211.39"),
        ("63892 ÷ 345 =", "185.19"),
        ("87421 ÷ 452 =", "193.41"),
        ("53210 ÷ 628 =", "84.73"),
        ("71239 ÷ 531 =", "134.16"),
        ("38945 ÷ 189 =", "206.06"),
        ("92147 ÷ 412 =", "223.66"),
        ("67823 ÷ 831 =", "81.62"),
        ("84215 ÷ 293 =", "287.42"),
        ("56341 ÷ 746 =", "75.52"),
    ]
    qs_sec3 = [
        RenderQuestionPayload(
            number=global_num + i,
            question_id=100 + global_num + i,
            type="blank",
            type_label="基础速算",
            stem_text=stem,
            answer_text=ans,
        )
        for i, (stem, ans) in enumerate(sec3_stems)
    ]
    global_num += len(qs_sec3)
    sections.append(RenderSectionPayload(
        key="sec_calc_3",
        title="三、基础计算：五位数除以三位数（截位直除，保留1位或2位小数）",
        questions=qs_sec3,
    ))

    # ---------------- 4. 基础计算：三位数的减法 (10题) ----------------
    sec4_stems = [
        ("742 - 389 =", "353"),
        ("815 - 467 =", "348"),
        ("934 - 578 =", "356"),
        ("621 - 285 =", "336"),
        ("543 - 198 =", "345"),
        ("872 - 496 =", "376"),
        ("654 - 387 =", "267"),
        ("723 - 459 =", "264"),
        ("912 - 648 =", "264"),
        ("831 - 574 =", "257"),
    ]
    qs_sec4 = [
        RenderQuestionPayload(
            number=global_num + i,
            question_id=100 + global_num + i,
            type="blank",
            type_label="基础速算",
            stem_text=stem,
            answer_text=ans,
        )
        for i, (stem, ans) in enumerate(sec4_stems)
    ]
    global_num += len(qs_sec4)
    sections.append(RenderSectionPayload(
        key="sec_calc_4",
        title="四、基础计算：三位数的减法",
        questions=qs_sec4,
    ))

    # ---------------- 5. 基础计算：三位数的加法 (10题) ----------------
    sec5_stems = [
        ("384 + 547 =", "931"),
        ("469 + 375 =", "844"),
        ("582 + 269 =", "851"),
        ("647 + 188 =", "835"),
        ("736 + 485 =", "1221"),
        ("294 + 638 =", "932"),
        ("517 + 396 =", "913"),
        ("483 + 379 =", "862"),
        ("658 + 274 =", "932"),
        ("395 + 468 =", "863"),
    ]
    qs_sec5 = [
        RenderQuestionPayload(
            number=global_num + i,
            question_id=100 + global_num + i,
            type="blank",
            type_label="基础速算",
            stem_text=stem,
            answer_text=ans,
        )
        for i, (stem, ans) in enumerate(sec5_stems)
    ]
    global_num += len(qs_sec5)
    sections.append(RenderSectionPayload(
        key="sec_calc_5",
        title="五、基础计算：三位数的加法",
        questions=qs_sec5,
    ))

    # ---------------- 6. 资料分析：求基期量 (8题, 4列数据盒) ----------------
    sec6_stems = [
        ("4971    8.8%", "4569"),
        ("5363    7.8%", "4975"),
        ("11782   8.1%", "10899"),
        ("6450    12.5%", "5733"),
        ("8720    14.3%", "7629"),
        ("9340    9.5%", "8530"),
        ("3850    -12.0%", "4375"),
        ("7210    16.7%", "6178"),
    ]
    qs_sec6 = [
        RenderQuestionPayload(
            number=global_num + i,
            question_id=200 + global_num + i,
            type="blank",
            type_label="基期量计算",
            stem_text=stem,
            answer_text=ans,
        )
        for i, (stem, ans) in enumerate(sec6_stems)
    ]
    global_num += len(qs_sec6)
    sections.append(RenderSectionPayload(
        key="sec_data_base",
        title="六、资料分析 · 基期量计算特训（给出现期量与增长率，求基期量）",
        questions=qs_sec6,
    ))

    # ---------------- 7. 资料分析：求增长量 (8题, 4列数据盒) ----------------
    sec7_stems = [
        ("5420    12.5%", "677.5"),
        ("8250    14.3%", "1180"),
        ("3640    25.0%", "910"),
        ("9200    9.1%", "837"),
        ("4800    16.7%", "800"),
        ("7500    20.0%", "1500"),
        ("6300    11.1%", "700"),
        ("8800    12.5%", "1100"),
    ]
    qs_sec7 = [
        RenderQuestionPayload(
            number=global_num + i,
            question_id=300 + global_num + i,
            type="blank",
            type_label="增长量计算",
            stem_text=stem,
            answer_text=ans,
        )
        for i, (stem, ans) in enumerate(sec7_stems)
    ]
    global_num += len(qs_sec7)
    sections.append(RenderSectionPayload(
        key="sec_data_inc",
        title="七、资料分析 · 增长量计算特训（给出基期量与增长率，求增长量）",
        questions=qs_sec7,
    ))

    # ---------------- 8. 资料分析：分数大小比较 (8题, 2列立体比较盒) ----------------
    sec8_stems = [
        (r"$\frac{165}{5284}$    (     )    $\frac{65}{2010}$", "＜"),
        (r"$\frac{584}{3755}$    (     )    $\frac{887}{5555}$", "＜"),
        (r"$\frac{214}{5222}$    (     )    $\frac{296}{7096}$", "＜"),
        (r"$\frac{985}{9178}$    (     )    $\frac{835}{7646}$", "＞"),
        (r"$\frac{432}{1580}$    (     )    $\frac{512}{1920}$", "＞"),
        (r"$\frac{729}{3840}$    (     )    $\frac{615}{3120}$", "＜"),
        (r"$\frac{381}{6420}$    (     )    $\frac{492}{7850}$", "＜"),
        (r"$\frac{845}{2310}$    (     )    $\frac{765}{2150}$", "＞"),
    ]
    qs_sec8 = [
        RenderQuestionPayload(
            number=global_num + i,
            question_id=400 + global_num + i,
            type="blank",
            type_label="分数比较",
            stem_text=stem,
            answer_text=ans,
        )
        for i, (stem, ans) in enumerate(sec8_stems)
    ]
    global_num += len(qs_sec8)
    sections.append(RenderSectionPayload(
        key="sec_compare",
        title="八、资料分析 · 分数大小比较特训（在括号内填写 ＞ 或 ＜）",
        questions=qs_sec8,
    ))

    total_q = global_num - 1
    payload = RenderDocumentPayload(
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
            title="公务员考试·行测提速专项突破",
            subtitle="基础速算强化 · 资料分析核心应用 · 分数极速直除比大小",
        ),
        paper=RenderPaperPayload(
            title="公务员考试·行测提速专项突破",
            subtitle="",
            question_count=total_q,
            material_count=0,
            sections=sections,
            materials=[],
        ),
        metadata={"user_id": 999, "nickname": "学员"},
    )

    ctx = adapt_basic_calc_payload(payload)
    template_file = TEMPLATES_ROOT / "basic_calculation" / "1.0.0" / "template.docx"
    output_dir = PROJECT_ROOT / "backend" / "output" / "full_comprehensive_pack"
    output_dir.mkdir(parents=True, exist_ok=True)
    base_name = f"full_comprehensive_{int(time.time())}"

    result = docx_render_engine.render_all(
        template_file=template_file,
        context=ctx,
        output_dir=output_dir,
        base_name=base_name,
        compile_pdf=True,
        max_previews=10,
    )
    print("SUCCESS! Generated files:")
    print("DOCX:", result.get("docx"))
    print("PDF:", result.get("pdf"))
    print("Previews count:", len(result.get("previews", [])))
    for p in result.get("previews", []):
        print("Preview:", p)

if __name__ == "__main__":
    run()
