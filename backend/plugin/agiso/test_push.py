#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import hashlib
import json
import time

import requests

BASE_URL = "http://127.0.0.1:8000/api/v1/agiso/webhooks"
ACTIVATE_URL = "http://127.0.0.1:8000/api/v1/actcode/agiso/activate"
APP_SECRET = "gnm26ydsneuredywn642vvc4mbrvcrn6"
REQUEST_TIMEOUT = 10


def make_sign(json_str: str, timestamp: str, app_secret: str) -> str:
    """生成签名"""
    sign_str = f'{app_secret}json{json_str}timestamp{timestamp}{app_secret}'
    return hashlib.md5(sign_str.encode('utf-8'), usedforsecurity=False).hexdigest()


# =============================================
# 淘宝平台 (TbAlds) 测试
# =============================================

def test_tb_payment():
    """测试淘宝买家付款推送"""
    json_data = json.dumps({
        "Tid": "2067719225654838",
        "Status": "WAIT_SELLER_SEND_GOODS",
        "BuyerNick": "test_buyer",
        "Payment": "99.00",
        "SellerNick": "test_seller",
        "SellerOpenUid": "seller123",
        "BuyerOpenUid": "buyer456",
        "Type": "fixed"
    }, ensure_ascii=False)

    timestamp = str(int(time.time()))
    sign = make_sign(json_data, timestamp, APP_SECRET)

    print("\n=== [淘宝] 测试买家付款推送 (aopic=2097152) ===")
    try:
        response = requests.post(
            f"{BASE_URL}/delivery",
            data={"json": json_data},
            params={
                "timestamp": timestamp,
                "sign": sign,
                "fromPlatform": "TbAlds",
                "aopic": 2097152,
            },
            timeout=REQUEST_TIMEOUT,
        )
        print(f"Status: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), ensure_ascii=False, indent=2)}")
    except Exception as e:
        print(f"Error: {e}")


def test_tb_delivery():
    """测试淘宝自动发货推送"""
    json_data = json.dumps({
        "Tid": "2067719225654838",
        "Status": "WAIT_BUYER_CONFIRM_GOODS",
        "BuyerNick": "test_buyer",
        "Payment": "99.00",
        "SellerNick": "test_seller",
        "SellerOpenUid": "seller123",
        "BuyerOpenUid": "buyer456",
        "Type": "fixed"
    }, ensure_ascii=False)

    timestamp = str(int(time.time()))
    sign = make_sign(json_data, timestamp, APP_SECRET)

    print("\n=== [淘宝] 测试自动发货成功推送 (aopic=2048) ===")
    try:
        response = requests.post(
            f"{BASE_URL}/delivery",
            data={"json": json_data},
            params={
                "timestamp": timestamp,
                "sign": sign,
                "fromPlatform": "TbAlds",
                "aopic": 2048,
            },
            timeout=REQUEST_TIMEOUT,
        )
        print(f"Status: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), ensure_ascii=False, indent=2)}")
    except Exception as e:
        print(f"Error: {e}")


# =============================================
# 小红书平台 (AldsXhs) 测试
# =============================================

def test_xhs_payment():
    """测试小红书买家付款推送"""
    json_data = json.dumps({
        "sellerId": "6837071ec0f93b0015e8db73",
        "orderId": "P999000000000000002",
        "orderStatus": 4,
        "updateTime": 1771086554138
    }, ensure_ascii=False)

    timestamp = str(int(time.time()))
    sign = make_sign(json_data, timestamp, APP_SECRET)

    print("\n=== [小红书] 测试买家付款推送 (aopic=4) ===")
    try:
        response = requests.post(
            f"{BASE_URL}/delivery",
            data={"json": json_data},
            params={
                "timestamp": timestamp,
                "sign": sign,
                "fromPlatform": "AldsXhs",
                "aopic": 4,
            },
            timeout=REQUEST_TIMEOUT,
        )
        print(f"Status: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), ensure_ascii=False, indent=2)}")
    except Exception as e:
        print(f"Error: {e}")


def test_xhs_delivery():
    """测试小红书自动发货推送"""
    json_data = json.dumps({
        "Tid": "P999000000000000002",
        "PlatformShopId": "6837071ec0f93b0015e8db73",
        "AldsType": 1,
        "CreateTime": "2026-02-22T12:00:00",
        "PayTime": "2026-02-22T12:00:10",
        "Status": "4",
        "Orders": [{
            "Num": 1,
            "GoodsName": "公考知识库备考资料等内容链接学习指导",
            "GoodsId": "69704355306dc500012c9ea1",
            "OuterGoodsId": None,
            "SkuId": "69704355306dc500012c9ea1",
            "OuterSkuId": None,
            "Oid": "P999000000000000002",
            "SpType": 3,
            "SpecName": "",
            "SendCards": []
        }]
    }, ensure_ascii=False)

    timestamp = str(int(time.time()))
    sign = make_sign(json_data, timestamp, APP_SECRET)

    print("\n=== [小红书] 测试自动发货成功推送 (aopic=1) ===")
    try:
        response = requests.post(
            f"{BASE_URL}/delivery",
            data={"json": json_data},
            params={
                "timestamp": timestamp,
                "sign": sign,
                "fromPlatform": "AldsXhs",
                "aopic": 1,
            },
            timeout=REQUEST_TIMEOUT,
        )
        print(f"Status: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), ensure_ascii=False, indent=2)}")
    except Exception as e:
        print(f"Error: {e}")


def test_xhs_duplicate():
    """测试小红书重复推送（应被去重忽略）"""
    json_data = json.dumps({
        "sellerId": "6837071ec0f93b0015e8db73",
        "orderId": "P999000000000000002",
        "orderStatus": 4,
        "updateTime": 1771086554138
    }, ensure_ascii=False)

    timestamp = str(int(time.time()))
    sign = make_sign(json_data, timestamp, APP_SECRET)

    print("\n=== [小红书] 测试重复付款推送（应被去重忽略） ===")
    try:
        response = requests.post(
            f"{BASE_URL}/delivery",
            data={"json": json_data},
            params={
                "timestamp": timestamp,
                "sign": sign,
                "fromPlatform": "AldsXhs",
                "aopic": 4,
            },
            timeout=REQUEST_TIMEOUT,
        )
        print(f"Status: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), ensure_ascii=False, indent=2)}")
    except Exception as e:
        print(f"Error: {e}")


def test_xhs_refund():
    """测试小红书退款推送（应删除对应激活码）"""
    json_data = json.dumps({
        "sellerId": "6837071ec0f93b0015e8db73",
        "returnsId": "R9990000000000001",
        "orderId": "P999000000000000002",
        "returnType": 4,
        "request_from": 0,
        "refundFee": 9.9,
        "updateTime": 1771086600000
    }, ensure_ascii=False)

    timestamp = str(int(time.time()))
    sign = make_sign(json_data, timestamp, APP_SECRET)

    print("\n=== [小红书] 测试退款推送 (aopic=16) ===")
    try:
        response = requests.post(
            f"{BASE_URL}/delivery",
            data={"json": json_data},
            params={
                "timestamp": timestamp,
                "sign": sign,
                "fromPlatform": "AldsXhs",
                "aopic": 16,
            },
            timeout=REQUEST_TIMEOUT,
        )
        print(f"Status: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), ensure_ascii=False, indent=2)}")
    except Exception as e:
        print(f"Error: {e}")


# =============================================
# 激活测试
# =============================================

def test_activate():
    """测试激活账户"""
    print("\n=== 测试激活账户（小红书订单号） ===")
    try:
        response = requests.post(ACTIVATE_URL, data={
            "order_input": "P999000000000000002",
            "username": "test_xhs_user",
            "password": "Test123456",
        }, timeout=REQUEST_TIMEOUT)
        print(f"Status: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), ensure_ascii=False, indent=2)}")
    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    print("=" * 60)
    print("阿奇索推送 全平台测试")
    print("=" * 60)

    # 淘宝平台测试
    print("\n" + "─" * 60)
    print("📦 淘宝平台 (TbAlds)")
    print("─" * 60)
    test_tb_payment()
    time.sleep(1)
    test_tb_delivery()

    # 小红书平台测试
    print("\n" + "─" * 60)
    print("📕 小红书平台 (AldsXhs)")
    print("─" * 60)
    test_xhs_payment()
    time.sleep(1)
    test_xhs_delivery()

    # 去重测试
    print("\n" + "─" * 60)
    print("🔁 去重测试")
    print("─" * 60)
    test_xhs_duplicate()

    # 退款测试（应删除上面创建的激活码）
    print("\n" + "─" * 60)
    print("💰 退款测试")
    print("─" * 60)
    time.sleep(1)
    test_xhs_refund()

    # 激活测试
    print("\n" + "─" * 60)
    print("🔑 激活测试")
    print("─" * 60)
    test_activate()

    print("\n" + "=" * 60)
    print("全部测试完成")
    print("=" * 60)
