import hashlib
import json
import time

import requests

BASE_URL = "http://127.0.0.1:8000/api/v1/agiso/webhooks"
APP_SECRET = "gnm26ydsneuredywn642vvc4mbrvcrn6"


def make_sign(json_str: str, timestamp: str, app_secret: str) -> str:
    """阿奇索签名算法: md5(appsecret + 'json' + json + 'timestamp' + timestamp + appsecret)"""
    sign_str = f'{app_secret}json{json_str}timestamp{timestamp}{app_secret}'
    return hashlib.md5(sign_str.encode('utf-8')).hexdigest()


def test_payment_push():
    """测试买家付款推送 (aopic=2097152)"""
    url = f"{BASE_URL}/delivery"

    json_data = json.dumps({
        "Tid": 2067719225654838,
        "Status": "WAIT_SELLER_SEND_GOODS",
        "SellerNick": "168休闲馆",
        "SellerOpenUid": "AAEF_gqxAAShiml5xxxxxxxx",
        "BuyerNick": "碎**",
        "BuyerOpenUid": "AaEL_gqxAAShiml5geo3bVTa",
        "Payment": "3.00",
        "Type": "fixed",
    })

    timestamp = str(int(time.time()))
    sign = make_sign(json_data, timestamp, APP_SECRET) if APP_SECRET else "test_sign"

    params = {
        "timestamp": timestamp,
        "sign": sign,
        "fromPlatform": "TbAlds",
        "aopic": 2097152,
    }

    print("=== 测试买家付款推送 (aopic=2097152) ===")
    try:
        response = requests.post(url, params=params, data={"json": json_data})
        print(f"Status: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), ensure_ascii=False, indent=2)}")
    except Exception as e:
        print(f"Error: {e}")


def test_delivery_push():
    """测试自动发货成功推送 (aopic=2048)"""
    url = f"{BASE_URL}/delivery"

    json_data = json.dumps({
        "Tid": 2067719225654838,
        "BuyerNick": "碎**",
        "BuyerOpenUid": "AaEL_gqxAAShiml5geo3bVTa",
        "Created": "2016-07-11 11:20:09",
        "Num": 1,
        "Payment": "3.00",
        "PayTime": "2016-07-11 11:20:20",
        "Price": "3.00",
        "SellerNick": "168休闲馆",
        "SellerOpenUid": "AAEF_gqxAAShiml5xxxxxxxx",
        "Status": "WAIT_BUYER_CONFIRM_GOODS",
        "TotalFee": "3.00",
        "Type": "fixed",
        "Orders": [
            {
                "Num": 1,
                "NumIid": 45533870790,
                "Oid": 2067719225654838,
                "OuterIid": "ALDS1000",
                "Payment": "3.00",
                "Price": "3.00",
                "Title": "宝贝标题",
                "TotalFee": "3.00",
                "SendCards": [
                    {
                        "CpcId": 123456,
                        "Title": "300元京东卡",
                        "Cards": [
                            {"Card": "125845451212", "Pwd": "125845451212"},
                        ],
                    }
                ],
            }
        ],
    })

    timestamp = str(int(time.time()))
    sign = make_sign(json_data, timestamp, APP_SECRET) if APP_SECRET else "test_sign"

    params = {
        "timestamp": timestamp,
        "sign": sign,
        "fromPlatform": "TbAlds",
        "aopic": 2048,
    }

    print("\n=== 测试自动发货成功推送 (aopic=2048) ===")
    try:
        response = requests.post(url, params=params, data={"json": json_data})
        print(f"Status: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), ensure_ascii=False, indent=2)}")
    except Exception as e:
        print(f"Error: {e}")


def test_activate():
    """测试激活账户"""
    url = "http://127.0.0.1:8000/api/v1/actcode/agiso/activate"

    print("\n=== 测试激活账户 ===")
    try:
        response = requests.post(url, data={
            "order_no": "2067719225654838",
            "username": "test_user_001",
            "password": "Test123456",
        })
        print(f"Status: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), ensure_ascii=False, indent=2)}")
    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    print("=" * 50)
    print("阿奇索推送 + 激活 全流程测试")
    print("=" * 50)

    # 步骤1: 模拟买家付款推送
    test_payment_push()

    # 步骤2: 模拟自动发货成功推送（会创建激活码）
    test_delivery_push()

    # 步骤3: 用订单号激活账户
    test_activate()
