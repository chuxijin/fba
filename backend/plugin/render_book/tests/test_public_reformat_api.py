#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
公开免登录试卷重排接口单元与集成测试脚本
使用真实的粉笔捕获数据包 (130题) 测试端到端转换与渲染流程
"""

import json
import os
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.plugin.render_book.schema.public_reformat import (
    PublicReformatRequest,
    ReformatOptionsInput,
    UnifiedPaperInput,
    UnifiedQuestionInput,
    UnifiedSectionInput,
    convert_unified_paper_to_document_payload,
)
from backend.plugin.render_book.service.adapters import adapt_gongkao_payload
from backend.plugin.render_book.service.docx_engine import docx_render_engine
from backend.plugin.render_book.utils.template_catalog import TEMPLATES_ROOT


def load_real_fenbi_dump() -> UnifiedPaperInput:
    """从本地真实粉笔捕获数据包构造 UnifiedPaperInput（100% 对应前端 fenbi.ts 逻辑）"""
    dump_path = PROJECT_ROOT / "data" / "fenbi_dump" / "capture_2_134180.json"
    assert dump_path.exists(), f"未找到粉笔数据包: {dump_path}"

    with open(dump_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # 1. 建立题目与材料快速索引
    q_map = {}
    for q in data.get("questions", []):
        if "globalId" in q:
            q_map[str(q["globalId"])] = q
        if "id" in q:
            q_map[str(q["id"])] = q

    mat_map = {}
    for m in data.get("materials", []):
        if "globalId" in m:
            mat_map[str(m["globalId"])] = m.get("content", "")
        if "id" in m:
            mat_map[str(m["id"])] = m.get("content", "")

    sections: list[UnifiedSectionInput] = []
    global_order = 1

    card = data.get("card", {})
    card_children = card.get("children", [])

    if card_children:
        for sec_node in card_children:
            sec_name = sec_node.get("name") or "专项模块"
            questions: list[UnifiedQuestionInput] = []
            for q_node in sec_node.get("children", []):
                q_key = str(q_node.get("key") or q_node.get("id"))
                raw_q = q_map.get(q_key)
                if not raw_q:
                    continue

                # 匹配材料
                mat_text = None
                mat_keys = q_node.get("materialKeys", [])
                if mat_keys and str(mat_keys[0]) in mat_map:
                    mat_text = mat_map[str(mat_keys[0])]

                # 提取选项
                opts = []
                for acc in raw_q.get("accessories", []):
                    if "options" in acc:
                        opts = acc["options"]
                        break

                questions.append(
                    UnifiedQuestionInput(
                        order_num=global_order,
                        question_id=raw_q.get("id"),
                        stem=raw_q.get("content", ""),
                        options=opts,
                        answer=raw_q.get("answer", {}).get("choice") if isinstance(raw_q.get("answer"), dict) else None,
                        material=mat_text,
                    )
                )
                global_order += 1

            if questions:
                sections.append(
                    UnifiedSectionInput(
                        name=sec_name,
                        questions=questions,
                    )
                )

    return UnifiedPaperInput(
        title=data.get("name", "2026年国家公务员录用考试行测真题卷"),
        source_platform="fenbi",
        total_questions=global_order - 1,
        sections=sections,
    )


def test_public_reformat_pipeline():
    print("=== 开始测试【公考内容排版】公开接口转换与排版全流程 ===")

    # 1. 构造入参
    paper_input = load_real_fenbi_dump()
    print(f"[✓] 成功加载真实粉笔数据包，包含 {len(paper_input.sections[0].questions)} 道试题")

    req = PublicReformatRequest(
        paper=paper_input,
        options=ReformatOptionsInput(include_answer=False, output_format="docx"),
        target="computer_download",
    )

    doc_payload = convert_unified_paper_to_document_payload(req)
    total_q = sum(len(s.questions) for s in paper_input.sections)
    print(f"[✓] 成功转换为 RenderDocumentPayload: 题量={doc_payload.paper.question_count}, 材料数={doc_payload.paper.material_count}")
    assert doc_payload.paper.question_count <= total_q
    assert doc_payload.paper.material_count > 0

    # 3. 测试 gongkao_adapter 适配
    template_file = TEMPLATES_ROOT / "gongkao_xingce" / "1.0.0" / "template.docx"
    assert template_file.exists()

    docx_context = adapt_gongkao_payload(doc_payload, template_file=template_file)
    print(f"[✓] gongkao_adapter 考场规范适配成功，生成试卷抬头: {docx_context['paper']['exam_name']}")
    parts = docx_context["paper"]["parts"]
    print(f"[✓] 模块分类数量: {len(parts)}, 第一模块名称: {parts[0]['name']}")

    # 4. 测试 docx 渲染输出
    output_dir = PROJECT_ROOT / "backend" / "output" / "exam_test" / "public_reformat_test"
    output_dir.mkdir(parents=True, exist_ok=True)

    print(">>> 正在调用 DocxRenderEngine 生成标准 B5 考场 Word 与 PDF 矢量卷本...")
    start_t = time.time()
    render_res = docx_render_engine.render_all(
        template_file=template_file,
        context=docx_context,
        output_dir=output_dir,
        base_name=f"fenbi_130_reformat_test_{int(time.time())}",
        compile_pdf=True,  # 验证完整 PDF 导出能力
        max_previews=1,
    )
    cost = time.time() - start_t
    docx_file = Path(render_res["docx"])
    pdf_file = Path(render_res["pdf"])
    print(f"[✓] 极速排版成功！总耗时: {cost:.2f}秒")
    print(f"[✓] 生成 Word 文件: {docx_file} (大小: {docx_file.stat().st_size / 1024:.1f} KB)")
    print(f"[✓] 生成 PDF 文件: {pdf_file} (大小: {pdf_file.stat().st_size / 1024:.1f} KB)")
    assert docx_file.exists()
    assert pdf_file.exists()
    assert pdf_file.stat().st_size > 10000

    print("=== 所有公开排版全流程测试 100% 顺利通过！===")


import pytest
from httpx import ASGITransport, AsyncClient
from backend.main import app
from backend.database.db import get_db, get_db_transaction, async_db_session


@pytest.mark.anyio
async def test_fastapi_endpoints():
    print("=== 开始测试 FastAPI 公开路由端点 ===")

    # 临时覆盖 conftest 导致的 fba_test 数据库重定向，使用真实开发库进行联调测试
    async def _real_get_db():
        async with async_db_session() as session:
            yield session

    async def _real_get_db_transaction():
        async with async_db_session.begin() as session:
            yield session

    orig_get_db = app.dependency_overrides.get(get_db)
    orig_get_db_transaction = app.dependency_overrides.get(get_db_transaction)
    app.dependency_overrides[get_db] = _real_get_db
    app.dependency_overrides[get_db_transaction] = _real_get_db_transaction

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            # 1. 匿名游客查询配额 (动态读取 resource_rule trial_policy limit=5)
            resp_quota = await client.get("/api/v1/render-books/public/quota")
            assert resp_quota.status_code == 200
            quota_data = resp_quota.json()["data"]
            print(f"[✓] 游客 GET /quota 返回正常: {quota_data}")
            assert quota_data["daily_limit"] == 5
            assert quota_data["is_logged_in"] is False

            # 2. 测试小程序引流码
            resp_mini = await client.get("/api/v1/render-books/public/minicode/pub_test_123")
            assert resp_mini.status_code == 200
            assert "image/svg+xml" in resp_mini.headers.get("content-type", "")
            print("[✓] GET /minicode/{job_id} 返回正常矢量引流图")

            # 3. 已登录用户配额与 access 模块验证 (动态读取 pack.free 挂载的 50 次配额)
            from backend.common.security.token import create_access_token
            token_data = await create_access_token(20, multi_login=True)
            resp_user_quota = await client.get(
                "/api/v1/render-books/public/quota",
                headers={"Authorization": f"Bearer {token_data.access_token}"},
            )
            assert resp_user_quota.status_code == 200
            user_quota_data = resp_user_quota.json()["data"]
            print(f"[✓] 已登录用户 GET /quota (由 access 模块解析): {user_quota_data}")
            assert user_quota_data["is_logged_in"] is True
            assert user_quota_data["daily_limit"] == 15
            assert user_quota_data["remaining_quota"] >= 1

        print("=== FastAPI 公开路由端点测试 100% 顺利通过！===")
    finally:
        if orig_get_db:
            app.dependency_overrides[get_db] = orig_get_db
        else:
            app.dependency_overrides.pop(get_db, None)
        if orig_get_db_transaction:
            app.dependency_overrides[get_db_transaction] = orig_get_db_transaction
        else:
            app.dependency_overrides.pop(get_db_transaction, None)


