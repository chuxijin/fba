#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json

import requests

BASE_URL = "http://127.0.0.1:8000/api/v1/notify"
REQUEST_TIMEOUT = 10


def test_send_basic():
    """测试基本发送（使用默认渠道优先级）"""
    print("\n=== 测试基本发送（默认优先级） ===")
    try:
        response = requests.post(
            f"{BASE_URL}/send",
            json={
                "title": "测试通知",
                "content": "这是一条来自 notify 插件的测试通知，如果你看到了说明 Server 酱通道正常工作！",
            },
            timeout=REQUEST_TIMEOUT,
        )
        print(f"Status: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), ensure_ascii=False, indent=2)}")
    except Exception as e:
        print(f"Error: {e}")


def test_send_with_tags():
    """测试带 tags 的发送"""
    print("\n=== 测试带 tags 发送 ===")
    try:
        response = requests.post(
            f"{BASE_URL}/send",
            json={
                "title": "告警测试",
                "content": "这是一条带 tags 的测试通知",
                "options": {"tags": "测试|通知"},
            },
            timeout=REQUEST_TIMEOUT,
        )
        print(f"Status: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), ensure_ascii=False, indent=2)}")
    except Exception as e:
        print(f"Error: {e}")


def test_send_specify_channel():
    """测试指定渠道发送"""
    print("\n=== 测试指定渠道发送（serverchan） ===")
    try:
        response = requests.post(
            f"{BASE_URL}/send",
            json={
                "title": "指定渠道测试",
                "content": "这条通知指定了 serverchan 渠道",
                "channels": ["serverchan"],
            },
            timeout=REQUEST_TIMEOUT,
        )
        print(f"Status: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), ensure_ascii=False, indent=2)}")
    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    print("=" * 60)
    print("Notify 插件测试")
    print("=" * 60)

    test_send_basic()
    test_send_with_tags()
    test_send_specify_channel()

    print("\n" + "=" * 60)
    print("全部测试完成")
    print("=" * 60)
