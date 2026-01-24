#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
百度网盘 OAuth 测试脚本

使用方法:
1. 确保 .env 中配置了 BAIDUPAN_APP_KEY, BAIDUPAN_SECRET_KEY, BAIDUPAN_REDIRECT_URI
2. 启动 FastAPI 服务: python main.py
3. 运行此脚本: python scripts/test_baidupan_oauth.py
"""
import webbrowser

import httpx

# 配置
BASE_URL = 'http://127.0.0.1:8000/api/v1'


def test_get_authorize_url():
    """测试获取授权 URL"""
    print('=' * 60)
    print('步骤 1: 获取授权 URL')
    print('=' * 60)

    response = httpx.post(
        f'{BASE_URL}/baidupan/oauth/authorize',
        json={},  # 使用默认配置
    )

    if response.status_code != 200:
        print(f'❌ 请求失败: {response.status_code}')
        print(response.text)
        return None

    data = response.json()
    if data.get('code') != 200:
        print(f'❌ 业务错误: {data}')
        return None

    authorize_url = data['data']['authorize_url']
    state = data['data']['state']

    print(f'✅ 获取成功!')
    print(f'📎 授权 URL: {authorize_url}')
    print(f'🔑 State: {state}')
    print()

    return authorize_url, state


def test_callback(code: str, state: str):
    """测试回调换取 token"""
    print('=' * 60)
    print('步骤 3: 用 code 换取 token')
    print('=' * 60)

    response = httpx.get(
        f'{BASE_URL}/baidupan/oauth/callback',
        params={'code': code, 'state': state},
    )

    if response.status_code != 200:
        print(f'❌ 请求失败: {response.status_code}')
        print(response.text)
        return None

    data = response.json()
    if data.get('code') != 200:
        print(f'❌ 业务错误: {data}')
        return None

    token_data = data['data']
    print(f'✅ 换取成功!')
    print(f'🎫 Access Token: {token_data["access_token"][:50]}...')
    print(f'⏰ 有效期: {token_data["expires_in"]} 秒 ({token_data["expires_in"] // 86400} 天)')
    print(f'🔄 Refresh Token: {token_data["refresh_token"][:50]}...')
    print(f'📋 Scope: {token_data["scope"]}')
    print()

    return token_data


def test_refresh_token(refresh_token: str):
    """测试刷新 token"""
    print('=' * 60)
    print('步骤 4: 刷新 token')
    print('=' * 60)

    response = httpx.post(
        f'{BASE_URL}/baidupan/oauth/refresh',
        json={'refresh_token': refresh_token},
    )

    if response.status_code != 200:
        print(f'❌ 请求失败: {response.status_code}')
        print(response.text)
        return None

    data = response.json()
    if data.get('code') != 200:
        print(f'❌ 业务错误: {data}')
        return None

    token_data = data['data']
    print(f'✅ 刷新成功!')
    print(f'🎫 新 Access Token: {token_data["access_token"][:50]}...')
    print(f'🔄 新 Refresh Token: {token_data["refresh_token"][:50]}...')
    print()

    return token_data


def main():
    print()
    print('🚀 百度网盘 OAuth 测试')
    print()

    # 步骤 1: 获取授权 URL
    result = test_get_authorize_url()
    if not result:
        return

    authorize_url, state = result

    # 步骤 2: 打开浏览器让用户授权
    print('=' * 60)
    print('步骤 2: 用户授权')
    print('=' * 60)
    print('即将打开浏览器进行授权...')
    print('授权后，百度会重定向到你的回调地址')
    print()

    open_browser = input('是否打开浏览器? (y/n): ').strip().lower()
    if open_browser == 'y':
        webbrowser.open(authorize_url)
        print('✅ 浏览器已打开，请完成授权')
    else:
        print(f'请手动访问: {authorize_url}')

    print()
    print('授权完成后，请从回调 URL 中复制 code 参数')
    print('例如: http://127.0.0.1:8000/api/v1/baidupan/oauth/callback?code=XXXXXX&state=XXXXXX')
    print()

    # 步骤 3: 输入 code 换取 token
    code = input('请输入 code: ').strip()
    if not code:
        print('❌ code 不能为空')
        return

    token_data = test_callback(code, state)
    if not token_data:
        return

    # 步骤 4: 测试刷新 token
    test_refresh = input('是否测试刷新 token? (y/n): ').strip().lower()
    if test_refresh == 'y':
        test_refresh_token(token_data['refresh_token'])

    print('=' * 60)
    print('🎉 测试完成!')
    print('=' * 60)


if __name__ == '__main__':
    main()
