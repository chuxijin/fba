#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
阿奇索推送测试脚本

使用方法:
    python scripts/test_agiso_push.py
"""
import hashlib
import json
import time

import httpx


def generate_signature(json_data: dict, timestamp: str, app_secret: str) -> str:
    """
    生成阿奇索签名

    :param json_data: JSON 数据
    :param timestamp: 时间戳
    :param app_secret: AppSecret
    :return:
    """
    json_str = json.dumps(json_data, separators=(',', ':'), ensure_ascii=False)
    sign_str = f'{app_secret}json{json_str}timestamp{timestamp}{app_secret}'
    return hashlib.md5(sign_str.encode('utf-8')).hexdigest()


def test_payment_push():
    """测试支付推送"""
    print('=' * 60)
    print('测试阿奇索支付推送')
    print('=' * 60)

    # 配置
    base_url = 'http://127.0.0.1:8000'
    app_secret = input('请输入 AGISO_APP_SECRET: ').strip()

    if not app_secret:
        print('❌ AppSecret 不能为空')
        return

    # 推送数据
    push_data = {
        'Tid': int(time.time() * 1000),
        'Status': 'WAIT_SELLER_SEND_GOODS',
        'SellerNick': '测试店铺',
        'SellerOpenUid': 'SELLER_TEST_001',
        'BuyerNick': '测试买家',
        'BuyerOpenUid': 'BUYER_TEST_001',
        'Payment': '99.00',
        'Type': 'fixed',
    }

    timestamp = str(int(time.time()))
    json_str = json.dumps(push_data, separators=(',', ':'), ensure_ascii=False)

    # 生成签名
    sign = generate_signature(push_data, timestamp, app_secret)

    print(f'\n📦 推送数据:')
    print(json.dumps(push_data, indent=2, ensure_ascii=False))
    print(f'\n🔐 时间戳: {timestamp}')
    print(f'🔐 签名: {sign}')
    print(f'\n💡 识别逻辑: 包含 Payment 字段 → 支付推送')

    # 发送请求（统一接口）
    url = f'{base_url}/api/v1/agiso/webhooks/delivery'
    params = {
        'timestamp': timestamp,
        'sign': sign,
        'fromPlatform': 'TbAlds',
        'aopic': 2097152,
    }
    data = {'json': json_str}

    print(f'\n🚀 发送请求到: {url}')

    try:
        response = httpx.post(url, params=params, data=data, timeout=10.0)
        print(f'\n📊 响应状态码: {response.status_code}')
        print(f'📊 响应内容:')
        print(json.dumps(response.json(), indent=2, ensure_ascii=False))

        if response.status_code == 200:
            print('\n✅ 支付推送测试成功！')
        else:
            print('\n❌ 支付推送测试失败！')

    except Exception as e:
        print(f'\n❌ 请求失败: {e}')


def test_delivery_push():
    """测试发卡推送"""
    print('=' * 60)
    print('测试阿奇索发卡推送')
    print('=' * 60)

    # 配置
    base_url = 'http://127.0.0.1:8000'
    app_secret = input('请输入 AGISO_APP_SECRET: ').strip()

    if not app_secret:
        print('❌ AppSecret 不能为空')
        return

    # 推送数据
    push_data = {
        'Tid': int(time.time() * 1000),
        'Status': 'TRADE_FINISHED',
        'BuyerNick': '测试买家',
        'BuyerOpenUid': 'BUYER_TEST_001',
        'Cards': [
            {
                'card_no': 'CARD20260123001',
                'card_pwd': 'PWD123456',
                'card_value': '100',
            },
            {
                'card_no': 'CARD20260123002',
                'card_pwd': 'PWD789012',
                'card_value': '100',
            },
        ],
    }

    timestamp = str(int(time.time()))
    json_str = json.dumps(push_data, separators=(',', ':'), ensure_ascii=False)

    # 生成签名
    sign = generate_signature(push_data, timestamp, app_secret)

    print(f'\n📦 推送数据:')
    print(json.dumps(push_data, indent=2, ensure_ascii=False))
    print(f'\n🔐 时间戳: {timestamp}')
    print(f'🔐 签名: {sign}')
    print(f'\n💡 识别逻辑: 包含 Cards 字段 → 发卡推送')

    # 发送请求（统一接口）
    url = f'{base_url}/api/v1/agiso/webhooks/delivery'
    params = {
        'timestamp': timestamp,
        'sign': sign,
        'fromPlatform': 'TbAlds',
    }
    data = {'json': json_str}

    print(f'\n🚀 发送请求到: {url}')

    try:
        response = httpx.post(url, params=params, data=data, timeout=10.0)
        print(f'\n📊 响应状态码: {response.status_code}')
        print(f'📊 响应内容:')
        print(json.dumps(response.json(), indent=2, ensure_ascii=False))

        if response.status_code == 200:
            print('\n✅ 发卡推送测试成功！')
        else:
            print('\n❌ 发卡推送测试失败！')

    except Exception as e:
        print(f'\n❌ 请求失败: {e}')


def main():
    """主函数"""
    print('\n阿奇索推送测试工具')
    print('=' * 60)
    print('1. 测试支付推送')
    print('2. 测试发卡推送')
    print('3. 退出')
    print('=' * 60)

    choice = input('\n请选择测试类型 (1-3): ').strip()

    if choice == '1':
        test_payment_push()
    elif choice == '2':
        test_delivery_push()
    elif choice == '3':
        print('👋 退出测试')
    else:
        print('❌ 无效的选择')


if __name__ == '__main__':
    main()
