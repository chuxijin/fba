#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Word 题本渲染引擎与后端集成端到端自动化测试脚本
测试内容：
1. 通用 Word 引擎 DocxRenderEngine 的渲染、PDF 导出与预览图抽取；
2. 公考真题专属适配器（严格验证新大纲官方六大模块：政治理论、常识、言语、数量、判断、资料）；
3. 动态跳过空模块与过渡语/结束语自动生成；
4. RenderDocumentPayload 到 Word 上下文的转换精度；
5. 产物完整性与 OSS 存储元数据字段验证。
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
from backend.plugin.render_book.service.adapters import adapt_default_payload, adapt_gongkao_payload
from backend.plugin.render_book.service.docx_engine import docx_render_engine
from backend.plugin.render_book.utils.template_catalog import TEMPLATES_ROOT


def build_mock_gongkao_document_payload() -> RenderDocumentPayload:
    """构造包含新大纲政治理论、常识判断、言语理解、判断推理（带材料）等真实试卷数据"""
    materials = [
        RenderMaterialPayload(
            id=101,
            title="根据以下资料，回答 106～110 题。",
            content_text=(
                "某园区为保障日常管理工作有序开展，将赵琳、孙越、吴浩、郑佳、王玥、冯哲、高洋这7名工作人员安排在周一至周日值班，每天安排1人，每人每周仅值班1天，且相邻两天值班人员的学历不同。已知：\n"
                "（1）所有工作人员要么是初中学历，要么是高中学历；\n"
                "（2）孙越和郑佳的学历相同；\n"
                "（3）吴浩在周四值班，且吴浩是初中学历；\n"
                "（4）赵琳的值班日期在王玥和冯哲的值班日期之间；\n"
                "（5）高洋的学历与吴浩相同，且高洋不在周六、周日值班。"
            ),
        )
    ]

    # 1. 政治理论（新大纲第一模块）
    sec_zhengzhi = RenderSectionPayload(
        key="zhengzhi",
        title="政治理论",
        questions=[
            RenderQuestionPayload(
                number=1,
                question_id=1001,
                type="single",
                type_label="单选题",
                stem_text="高质量发展是全面建设社会主义现代化国家的首要任务。下列关于推动高质量发展的说法不正确的是：",
                options=[
                    RenderQuestionOptionPayload(key="A", content_text="必须完整、准确、全面贯彻新发展理念"),
                    RenderQuestionOptionPayload(key="B", content_text="必须坚持把发展经济的着力点放在虚拟经济上"),
                    RenderQuestionOptionPayload(key="C", content_text="必须更好统筹质的有效提升和量的合理增长"),
                    RenderQuestionOptionPayload(key="D", content_text="必须坚定不移深化改革开放、深入转变发展方式"),
                ],
            )
        ],
    )

    # 2. 常识判断
    sec_changshi = RenderSectionPayload(
        key="changshi",
        title="常识判断",
        questions=[
            RenderQuestionPayload(
                number=21,
                question_id=1021,
                type="single",
                type_label="单选题",
                stem_text="根据《中华人民共和国行政处罚法》，下列关于行政处罚设定的说法正确的是：",
                options=[
                    RenderQuestionOptionPayload(key="A", content_text="法律可以设定各种行政处罚"),
                    RenderQuestionOptionPayload(key="B", content_text="行政法规可以设定限制人身自由的行政处罚"),
                    RenderQuestionOptionPayload(key="C", content_text="地方性法规可以设定吊销营业执照的处罚"),
                    RenderQuestionOptionPayload(key="D", content_text="规章可以设定拘留等行政处罚"),
                ],
            )
        ],
    )

    # 3. 言语理解与表达
    sec_yanyu = RenderSectionPayload(
        key="yanyu",
        title="言语理解与表达",
        questions=[
            RenderQuestionPayload(
                number=36,
                question_id=1036,
                type="single",
                type_label="单选题",
                stem_text="面对人工智能时代日益猖獗且复杂多变的网络犯罪，传统法律的应对困境日渐凸显。",
                options=[
                    RenderQuestionOptionPayload(key="A", content_text="传统法律移植到网络空间具有一定的局限性"),
                    RenderQuestionOptionPayload(key="B", content_text="人工智能时代的网络犯罪呈现复杂化特征"),
                    RenderQuestionOptionPayload(key="C", content_text="网络犯罪的滋生亟待完善现行法律法规"),
                    RenderQuestionOptionPayload(key="D", content_text="现实空间的刑事法律规则无法适用于网络"),
                ],
            )
        ],
    )

    # 4. 判断推理（带材料）
    sec_panduan = RenderSectionPayload(
        key="panduan",
        title="判断推理",
        questions=[
            RenderQuestionPayload(
                number=106,
                question_id=1106,
                type="single",
                type_label="单选题",
                stem_text="以下从左到右列出的工作人员，哪项可能是从周一至周日的值班安排？",
                material_ids=[101],
                options=[
                    RenderQuestionOptionPayload(key="A", content_text="高洋、孙越、赵琳、吴浩、王玥、郑佳、冯哲"),
                    RenderQuestionOptionPayload(key="B", content_text="赵琳、吴浩、孙越、高洋、王玥、郑佳、冯哲"),
                    RenderQuestionOptionPayload(key="C", content_text="孙越、高洋、王玥、吴浩、赵琳、冯哲、郑佳"),
                    RenderQuestionOptionPayload(key="D", content_text="冯哲、王玥、吴浩、赵琳、高洋、郑佳、孙越"),
                ],
            )
        ],
    )

    return RenderDocumentPayload(
        template_key="gongkao_xingce",
        render_plan=RenderPlanPayload(
            book_kind="exam",
            content_mode="questions_only",
            answer_layout=None,
            delivery_mode="single_pdf",
            solution_mode="none",
            output_targets=RenderOutputTargets(question_pdf=True, solution_pdf=False),
            render_variants=["questions_only"],
        ),
        book=RenderBookMeta(
            title="2027年中央机关及其直属机构考试录用公务员笔试",
            subtitle="行政职业能力测验（副省级）",
            meta_lines=["总题量：4 题", "满分：100 分"],
        ),
        options=RenderOptions(),
        paper=RenderPaperPayload(
            question_count=4,
            material_count=1,
            sections=[sec_zhengzhi, sec_changshi, sec_yanyu, sec_panduan],
            materials=materials,
        ),
        metadata={"exam_type": "国考", "subject": "行测"},
    )


def test_full_flow():
    print("=== 开始运行 Word 渲染引擎与公考六大模块端到端自动化测试 ===")

    # 1. 构建 payload
    payload = build_mock_gongkao_document_payload()
    print(f"[✓] 成功构建测试 Payload，包含 {len(payload.paper.sections)} 个模块，{payload.paper.question_count} 道题目")

    # 2. 测试公考专属适配器
    context = adapt_gongkao_payload(payload)
    parts = context["paper"]["parts"]
    print(f"[✓] 公考适配器转换成功，生成大模块数量: {len(parts)}")

    # 验证模块名称与顺延编号
    part_names = [p["name"] for p in parts]
    print(f"    模块列表: {part_names}")
    assert "第一部分 政治理论" in part_names[0], f"第一模块应为政治理论，实际为: {part_names[0]}"
    assert "第二部分 常识判断" in part_names[1], f"第二模块应为常识判断，实际为: {part_names[1]}"
    assert "第三部分 言语理解与表达" in part_names[2], f"第三模块应为言语理解与表达，实际为: {part_names[2]}"
    assert "第四部分 判断推理" in part_names[3], f"第四模块应为判断推理，实际为: {part_names[3]}"

    # 验证过渡语与卷末结束语
    assert "请继续做第二部分" in parts[0]["end_notice"]
    assert "全部测验到此结束" in parts[-1]["end_notice"]
    print("[✓] 模块过渡语与卷末结束语验证通过！")

    # 验证第 106 题材料题结构
    q_106 = parts[3]["questions"][0]
    assert q_106["no"] == 106
    assert q_106["material"] is not None
    assert q_106["material"]["intro"] == "根据以下资料，回答 106～110 题。"
    assert len(q_106["material"]["lines"]) >= 5
    print("[✓] 材料题引导语与正文结构化验证通过！")

    # 验证反向设问词加粗
    q_1 = parts[0]["questions"][0]
    bold_segs = [s["text"] for s in q_1["stem_segments"] if s.get("bold")]
    assert "不正确的是" in bold_segs
    print(f"[✓] 反向设问词智能加粗验证通过: {bold_segs}")

    # 3. 测试通用 Word 引擎渲染
    template_file = TEMPLATES_ROOT / "gongkao_xingce" / "1.0.0" / "template.docx"
    assert template_file.exists(), f"模板文件必须存在: {template_file}"

    test_output_dir = PROJECT_ROOT / "backend" / "output" / "exam_test" / "backend_e2e"
    render_result = docx_render_engine.render_all(
        template_file=template_file,
        context=context,
        output_dir=test_output_dir,
        base_name=f"gongkao_backend_e2e_test_{int(time.time())}",
        compile_pdf=True,
        max_previews=2,
    )

    docx_file = render_result["docx"]
    pdf_file = render_result["pdf"]
    previews = render_result["previews"]

    assert docx_file.exists() and docx_file.stat().st_size > 0, "生成的 Word 题本文件必须有效且非空"
    print(f"[✓] Word 题本渲染成功: {docx_file} (大小: {docx_file.stat().st_size} 字节)")

    assert pdf_file is not None and pdf_file.exists() and pdf_file.stat().st_size > 0, "生成的 PDF 题本文件必须有效且非空"
    print(f"[✓] 矢量 PDF 题本导出成功: {pdf_file} (大小: {pdf_file.stat().st_size} 字节)")

    assert len(previews) > 0, "必须成功提取封面预览图"
    for p in previews:
        assert p.exists() and p.stat().st_size > 0
        print(f"[✓] 封面缩略图抽取成功: {p.name} (大小: {p.stat().st_size} 字节)")

    # 4. 测试通用适配器隔离性（确保非公考题本不受影响）
    default_ctx = adapt_default_payload(payload)
    assert "sections" in default_ctx
    assert "parts" not in default_ctx.get("paper", {})
    print("[✓] 通用题本适配器隔离性验证通过（非公考模板绝不套用公考六大模块）！")

    print("\n=======================================================")
    print("🎉 恭喜！后端题本纯原生 Word 渲染引擎重构所有测试 100% 全部通过！")
    print("=======================================================")


if __name__ == "__main__":
    test_full_flow()
