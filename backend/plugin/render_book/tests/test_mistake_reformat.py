# -*- coding: utf-8 -*-
import json
import uuid
import pytest
from pathlib import Path
from unittest.mock import patch
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.plugin.render_book.api.v1.public import router as public_router

# 使用轻量级专享测试 App，杜绝全局无关后台队列与事件循环冲突
test_app = FastAPI()
test_app.include_router(public_router, prefix="/api/v1/render-books/public")
client = TestClient(test_app)


@pytest.fixture(autouse=True)
def isolated_quota():
    """每次测试独立配额命名空间，既走真实 Redis 又永不因累加而超限"""
    with patch("backend.plugin.render_book.api.v1.public._get_quota_key") as mock_key:
        mock_key.side_effect = lambda ip: f"test_quota_{uuid.uuid4().hex}"
        yield


def _get_base_payload():
    dump_file = Path("data/fenbi_dump/capture_1_134169.json")
    if not dump_file.exists():
        pytest.skip("未找到 capture_1_134169.json 真实错题转储文件")

    raw_data = json.loads(dump_file.read_text(encoding="utf-8"))
    return {
        "paper": {
            "title": raw_data.get("name", "公务员行测-错题专项练习"),
            "source_platform": "fenbi",
            "total_questions": 1,
            "sections": [
                {
                    "name": "错题巩固练习",
                    "questions": [
                        {
                            "id": 20421,
                            "question_id": 20421,
                            "order_num": 1,
                            "type": "single",
                            "type_label": "单选题",
                            "stem": raw_data["questions"][0]["content"],
                            "options": [
                                "A. 社会总成本的结构",
                                "B社会总成本的补偿",
                                "C. 社会总成本的支出",
                                "D 社会总成本的收入",
                            ],
                            "answer": "B",
                            "analysis": "从社会总成本角度分析，资本再生产的核心是社会总产品的实现（价值补偿与实物补偿）。",
                        }
                    ],
                }
            ],
            "metadata": {
                "scene": "mistake",
            },
        },
        "options": {
            "include_answer": True,
            "output_format": "pdf",
        },
    }


def test_mistake_reformat_merged():
    """验证模式 1：答案附在卷末 (合为一本 merged)"""
    payload = _get_base_payload()
    payload["options"]["answer_placement"] = "merged"

    res = client.post("/api/v1/render-books/public/reformat", json=payload)
    assert res.status_code == 200, f"接口返回非 200: {res.text}"
    data = res.json()["data"]
    assert data["job_id"].startswith("pub_")
    assert "download_url" in data
    assert "【粉笔错题】" in data["file_name"] and "(共1题)" in data["file_name"], f"期望规范文件名，实际: {data['file_name']}"
    print(f"\n🎉 模式1[合为一本]排版成功: {data['file_name']}, 下载URL: {data['download_url']}")


def test_mistake_reformat_separate():
    """验证模式 2：答案分为另外一个 PDF (分两本 separate)"""
    payload = _get_base_payload()
    payload["options"]["answer_placement"] = "separate"

    res = client.post("/api/v1/render-books/public/reformat", json=payload)
    assert res.status_code == 200, f"接口返回非 200: {res.text}"
    data = res.json()["data"]
    assert data["job_id"].startswith("pub_")
    assert "试题册" in data["file_name"], f"期望主文件含'试题册'，实际: {data['file_name']}"
    assert data.get("extra_files"), "期望返回 extra_files 包含答案解析分册"
    sol_file = data["extra_files"][0]
    assert "答案解析册" in sol_file["file_name"]
    assert "download_url" in sol_file
    print(f"\n🎉 模式2[分立两本]排版成功: 主文件={data['file_name']}, 答案文件={sol_file['file_name']}")


def test_mistake_reformat_none():
    """验证模式 3：不含答案 (仅试卷题本 none)"""
    payload = _get_base_payload()
    payload["options"]["answer_placement"] = "none"
    payload["options"]["include_answer"] = False

    res = client.post("/api/v1/render-books/public/reformat", json=payload)
    assert res.status_code == 200, f"接口返回非 200: {res.text}"
    data = res.json()["data"]
    assert data["job_id"].startswith("pub_")
    assert "纯试卷" in data["file_name"], f"期望文件名含'纯试卷'，实际: {data['file_name']}"
    print(f"\n🎉 模式3[纯试卷]排版成功: {data['file_name']}")

