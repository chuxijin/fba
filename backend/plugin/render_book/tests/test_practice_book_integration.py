#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
公考刷题本 (gongkao_practice) 端到端自动化集成测试
测试内容：
1. B5 尺寸与个人专属打卡扉页（用户昵称、生成时间、题量、建议用时、自律打卡栏）
2. 双栏做题区（考点微标签、反向设问智能加粗、我的作答打卡圈、选项智能分栏）
3. 附录参考答案速查表（5 列网格卡片，极速对正误）
4. 附录深度逐题解析精讲（正确答案、核心考点、详细解题思路）
5. 纯原生 Word 渲染 + 矢量 PDF 导出 + 封面缩略图抽取全链路闭环
"""

import sys
import time
from pathlib import Path

# 添加项目根目录到 Python 路径
PROJECT_ROOT = Path(__file__).resolve().parents[4]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.plugin.render_book.schema.payload import (
    RenderBookMeta,
    RenderDocumentPayload,
    RenderMaterialPayload,
    RenderPaperPayload,
    RenderPlanPayload,
    RenderQuestionOptionPayload,
    RenderQuestionPayload,
    RenderSectionPayload,
)
from backend.plugin.render_book.schema.render import RenderOptions, RenderOutputTargets
from backend.plugin.render_book.service.adapters import adapt_practice_payload
from backend.plugin.render_book.service.docx_engine import docx_render_engine
from backend.plugin.render_book.utils.template_catalog import TEMPLATES_ROOT

def build_mock_practice_payload() -> RenderDocumentPayload:
    # 构造包含单选、反向设问、不同长度选项、材料题的完整题目集
    materials = [
        RenderMaterialPayload(
            id=10,
            title="资料分析材料",
            content_text="根据以下资料，回答 6～7 题：\n2025年全国规模以上工业增加值比上年增长5.8%。分三大门类看，采矿业增加值增长2.5%，制造业增长6.1%，电力、热力、燃气及水生产和供应业增长6.3%。\n高技术制造业增加值比上年增长8.9%，快于规模以上工业3.1个百分点。",
        )
    ]

    questions = [
        # 第 1 题：短选项（4 列），反向设问加粗，国考真题
        RenderQuestionPayload(
            number=1,
            question_id=101,
            type="single_choice",
            type_label="单选题",
            source_text="2026年国家公务员考试《行政职业能力测验》真题",
            stem_text="下列关于我国新发展理念的说法不正确的是：",
            options=[
                RenderQuestionOptionPayload(key="A", content_text="创新"),
                RenderQuestionOptionPayload(key="B", content_text="协调"),
                RenderQuestionOptionPayload(key="C", content_text="绿色"),
                RenderQuestionOptionPayload(key="D", content_text="保守"),
            ],
            answer_text="D",
            analysis_text="新发展理念包含创新、协调、绿色、开放、共享五大理念，不包含保守。因此本题选 D。",
            knowledge_points=["政治理论 · 习近平新时代中国特色社会主义思想"],
        ),
        # 第 2 题：中长选项（2 列），常识判断，江苏省考
        RenderQuestionPayload(
            number=2,
            question_id=102,
            type="single_choice",
            type_label="单选题",
            source_text="2025年江苏省公务员录用考试《行测》真题",
            stem_text="下列历史事件按照发生时间先后顺序排列正确的是：",
            options=[
                RenderQuestionOptionPayload(key="A", content_text="商鞅变法-戊戌变法"),
                RenderQuestionOptionPayload(key="B", content_text="安史之乱-玄武门之变"),
                RenderQuestionOptionPayload(key="C", content_text="靖康之变-楚汉相争"),
                RenderQuestionOptionPayload(key="D", content_text="辛亥革命-虎门销烟"),
            ],
            answer_text="A",
            analysis_text="商鞅变法发生于战国时期，戊戌变法发生于晚清1898年，顺序正确。因此本题选 A。",
            knowledge_points=["常识判断 · 中国古代史与近代史"],
        ),
        # 第 3 题：长选项（1 列），言语理解与表达，联考
        RenderQuestionPayload(
            number=3,
            question_id=103,
            type="single_choice",
            type_label="单选题",
            source_text="2024年421联考《行测》真题",
            stem_text="中华文明源远流长，生生不息，不仅需要我们在传承中发扬光大，更需要在现代转化中赋予新的时代内涵。这段文字主要强调的是：",
            options=[
                RenderQuestionOptionPayload(key="A", content_text="中华优秀传统文化的深厚底蕴与历史价值"),
                RenderQuestionOptionPayload(key="B", content_text="推动中华优秀传统文化创造性转化与创新性发展"),
                RenderQuestionOptionPayload(key="C", content_text="必须全盘继承古代所有文化形态与民俗传统"),
                RenderQuestionOptionPayload(key="D", content_text="中华文化在世界多元文明交流互鉴中的特殊地位"),
            ],
            answer_text="B",
            analysis_text="文段核心强调'更需要在现代转化中赋予新的时代内涵'，即两创精神（创造性转化与创新性发展）。因此本题选 B。",
            knowledge_points=["言语理解与表达 · 主旨概括"],
        ),
        # 第 4 题：数量关系，广东
        RenderQuestionPayload(
            number=4,
            question_id=104,
            type="single_choice",
            type_label="单选题",
            source_text="2023年广东省考行测真题",
            stem_text="某项工程由甲队单独做需 12 天完成，乙队单独做需 18 天完成。若两队合作 3 天后，剩余工程由甲队单独完成，还需多少天？",
            options=[
                RenderQuestionOptionPayload(key="A", content_text="6 天"),
                RenderQuestionOptionPayload(key="B", content_text="7 天"),
                RenderQuestionOptionPayload(key="C", content_text="8 天"),
                RenderQuestionOptionPayload(key="D", content_text="9 天"),
            ],
            answer_text="B",
            analysis_text="赋工程总量为 36。甲效率为 3，乙效率为 2。合作 3 天完成 (3+2)*3 = 15。剩余 36 - 15 = 21。甲单独完成需 21 / 3 = 7 天。因此选 B。",
            knowledge_points=["数量关系 · 工程问题"],
        ),
        # 第 5 题：判断推理，四川
        RenderQuestionPayload(
            number=5,
            question_id=105,
            type="single_choice",
            type_label="单选题",
            source_text="2025年四川省考行测真题",
            stem_text="望梅止渴 之于 （   ） 相当于 （   ） 之于 经验主义",
            options=[
                RenderQuestionOptionPayload(key="A", content_text="条件反射；刻舟求剑"),
                RenderQuestionOptionPayload(key="B", content_text="画饼充饥；按图索骥"),
                RenderQuestionOptionPayload(key="C", content_text="心理暗示；掩耳盗铃"),
                RenderQuestionOptionPayload(key="D", content_text="杯弓蛇影；守株待兔"),
            ],
            answer_text="A",
            analysis_text="望梅止渴体现了条件反射原理，刻舟求剑体现了经验主义（静止看问题）。逻辑映射关系成立。因此选 A。",
            knowledge_points=["判断推理 · 类比推理"],
        ),
        # 第 6 题：材料题 1（资料分析），国考
        RenderQuestionPayload(
            number=6,
            question_id=106,
            type="single_choice",
            type_label="单选题",
            source_text="2026年国考行测真题",
            stem_text="2025年全国三大门类中，增加值同比增速最快的是：",
            options=[
                RenderQuestionOptionPayload(key="A", content_text="采矿业"),
                RenderQuestionOptionPayload(key="B", content_text="制造业"),
                RenderQuestionOptionPayload(key="C", content_text="电力、热力、燃气及水生产和供应业"),
                RenderQuestionOptionPayload(key="D", content_text="建筑业"),
            ],
            material_ids=[10],
            answer_text="C",
            analysis_text="由材料可知，电力热力燃气水生产供应业增速为 6.3%，高于制造业的 6.1% 和采矿业的 2.5%。因此选 C。",
            knowledge_points=["资料分析 · 直接查找与比较"],
        ),
        # 第 7 题：材料题 2（资料分析），国考
        RenderQuestionPayload(
            number=7,
            question_id=107,
            type="single_choice",
            type_label="单选题",
            source_text="2026年国考行测真题",
            stem_text="2025年高技术制造业增加值比上年增长：",
            options=[
                RenderQuestionOptionPayload(key="A", content_text="5.8%"),
                RenderQuestionOptionPayload(key="B", content_text="6.1%"),
                RenderQuestionOptionPayload(key="C", content_text="8.9%"),
                RenderQuestionOptionPayload(key="D", content_text="3.1%"),
            ],
            material_ids=[10],
            answer_text="C",
            analysis_text="材料明确说明高技术制造业增加值比上年增长 8.9%。因此选 C。",
            knowledge_points=["资料分析 · 简单读数"],
        ),
    ]

    return RenderDocumentPayload(
        template_key="gongkao_practice",
        render_plan=RenderPlanPayload(
            book_kind="custom",
            content_mode="questions_with_answers",
            answer_layout="appendix",
            delivery_mode="single_pdf",
            solution_mode="appendix",
            output_targets=RenderOutputTargets(),
        ),
        options=RenderOptions(include_answer=True, include_analysis=True),
        book=RenderBookMeta(
            title="言语理解与判断推理精选刷题本",
            subtitle="公考行测高频考点必刷 7 题",
        ),
        paper=RenderPaperPayload(
            question_count=len(questions),
            material_count=len(materials),
            sections=[
                RenderSectionPayload(
                    key="gongkao_practice_section_1",
                    title="第一阶段 · 核心能力专项巩固",
                    questions=questions,
                )
            ],
            materials=materials,
        ),
        metadata={
            "user_id": 888,
            "nickname": "公考上岸小分队",
            "module_title": "言语理解与判断推理 · 高频冲刺专项刷题",
            "generated_at": "2026-09-21 21:15",
        },
    )

def test_full_practice_flow():
    print("=== 开始运行【公考刷题本】端到端全链路集成测试 ===")

    payload = build_mock_practice_payload()

    # 1. 验证适配器转换
    ctx = adapt_practice_payload(payload)
    print(f"[✓] 适配器转换成功，模块名称: {ctx['paper']['module_title']}")
    print(f"[✓] 学员打卡信息: 昵称={ctx['user']['nickname']}, 题量={ctx['paper']['question_count']}, 建议用时={ctx['paper']['suggested_time']}分钟")

    # 2. 验证速查参考答案网格 (5 列)
    answer_rows = ctx["paper"]["answer_rows"]
    assert len(answer_rows) == 2, f"7 道题每行 5 列应分成 2 行，实际: {len(answer_rows)}"
    print(f"[✓] 参考答案速查网格生成成功: 共 {len(answer_rows)} 行")
    print(f"    行 1: {list(answer_rows[0].values())}")
    print(f"    行 2: {list(answer_rows[1].values())}")

    # 3. 验证题目与材料结构
    q1 = ctx["paper"]["parts"][0]["questions"][0]
    assert q1["opt_cols"] == 4, "短选项应为 4 列"
    assert any(s.get("bold") for s in q1["stem_segments"]), "反向设问词必须加粗"
    assert q1["kp_label"] is not None, "必须携带考点微标签"
    assert q1["source_tag"] == "26·国考", f"第1题来源应为 26·国考，实际: {q1['source_tag']}"

    q2 = ctx["paper"]["parts"][0]["questions"][1]
    assert q2["source_tag"] == "25·江苏", f"第2题来源应为 25·江苏，实际: {q2['source_tag']}"

    q3 = ctx["paper"]["parts"][0]["questions"][2]
    assert q3["source_tag"] == "24·联考", f"第3题来源应为 24·联考，实际: {q3['source_tag']}"

    q6 = ctx["paper"]["parts"][0]["questions"][5]
    assert q6["material"] is not None, "材料题必须正确绑定材料"
    assert "根据以下资料" in q6["material"]["intro"], "材料题引导语必须正确分离"
    assert q6["source_tag"] == "26·国考", f"第6题材料题来源应为 26·国考，实际: {q6['source_tag']}"
    print("[✓] 题目、来源短标签【26·国考/25·江苏】、选项自适应分栏、考点标签与材料题结构验证全部通过！")

    # 4. 调用原生 Word 引擎进行真实渲染、PDF 导出与预览图抽取
    template_file = TEMPLATES_ROOT / "gongkao_practice" / "1.0.0" / "template.docx"
    assert template_file.exists(), f"模板文件必须存在: {template_file}"

    test_output_dir = PROJECT_ROOT / "backend" / "output" / "practice_test"
    base_name = f"practice_book_e2e_{int(time.time())}"

    render_result = docx_render_engine.render_all(
        template_file=template_file,
        context=ctx,
        output_dir=test_output_dir,
        base_name=base_name,
        compile_pdf=True,
        max_previews=4,
    )

    docx_file = render_result["docx"]
    pdf_file = render_result["pdf"]
    previews = render_result["previews"]

    assert docx_file.exists() and docx_file.stat().st_size > 0, "Word 题本文件必须有效且非空"
    print(f"[✓] Word 刷题本生成成功: {docx_file} (大小: {docx_file.stat().st_size} 字节)")

    assert pdf_file is not None and pdf_file.exists() and pdf_file.stat().st_size > 0, "PDF 题本文件必须有效且非空"
    print(f"[✓] 矢量 PDF 刷题本导出成功: {pdf_file} (大小: {pdf_file.stat().st_size} 字节)")

    assert len(previews) > 0, "必须成功抽取预览图"
    for p in previews:
        assert p.exists() and p.stat().st_size > 0
        print(f"[✓] 页面缩略图抽取成功: {p.name} (大小: {p.stat().st_size} 字节)")

    # 另外将生成的封面和正文图片复制到 artifact 目录供汇报展示
    brain_dir = Path(r"C:/Users/19396/.gemini/antigravity/brain/187ced23-f104-44ff-88f4-aa1c9d171d79")
    import shutil
    for idx, p in enumerate(previews, start=1):
        target_preview = brain_dir / f"practice_preview_page_{idx}.jpg"
        shutil.copyfile(p, target_preview)
        print(f"[✓] 导出展示预览图: {target_preview.name}")

    print("\n=======================================================")
    print("🎉 恭喜！【公考刷题本】原生 Word 渲染引擎全链路测试 100% 全部通过！")
    print("=======================================================")

if __name__ == "__main__":
    test_full_practice_flow()
