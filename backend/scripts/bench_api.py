#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
API 接口响应时间批量检测脚本

用法:
    python backend/scripts/bench_api.py --token <JWT_TOKEN>
    python backend/scripts/bench_api.py --token <JWT_TOKEN> --base http://127.0.0.1:8000
    python backend/scripts/bench_api.py --token <JWT_TOKEN> --rounds 3
    python backend/scripts/bench_api.py --token <JWT_TOKEN> --slow 200

提示:
    JWT token 可从浏览器 DevTools → Network → 任意请求的 Authorization header 中复制
"""
import argparse
import sys
import time

import httpx

# ============ 待测接口列表 ============
# 格式: (HTTP方法, 路径, 描述, 查询参数/请求体)
# 路径中的 {pk} 等占位符会在运行时替换

ENDPOINTS: list[tuple[str, str, str, dict | None]] = [
    # ---- 首页 ----
    ('GET', '/api/v1/qbank/home/dashboard', '首页 Dashboard', None),
    ('GET', '/api/v1/qbank/home/rank?rank_type=practice_count', '排行榜', None),

    # ---- 题库 ----
    ('GET', '/api/v1/qbank/banks/recommend', '推荐题库', None),
    ('GET', '/api/v1/qbank/banks?page=1&size=10', '题库列表', None),

    # ---- 个人数据 ----
    ('GET', '/api/v1/qbank/questions/favorites?page=1&size=10', '收藏列表', None),
    ('GET', '/api/v1/qbank/questions/notes?page=1&size=10', '笔记列表', None),
    ('GET', '/api/v1/qbank/wrong-questions?page=1&size=10', '错题列表', None),
    ('GET', '/api/v1/qbank/wrong-questions/statistics', '错题统计', None),
    ('GET', '/api/v1/qbank/favorites/statistics', '收藏统计', None),
    ('GET', '/api/v1/qbank/notes/statistics', '笔记统计', None),

    # ---- 会话 ----
    ('GET', '/api/v1/qbank/sessions?page=1&size=10&status=in_progress', '进行中会话', None),
    ('GET', '/api/v1/qbank/sessions?page=1&size=10&status=completed', '已完成会话', None),
    ('GET', '/api/v1/qbank/sessions/records?page=1&size=10', '答题记录列表', None),

    # ---- 用户 ----
    ('GET', '/api/v1/qbank/auth/me', '用户信息', None),
    ('GET', '/api/v1/qbank/settings/study-preference', '学习偏好', None),
    ('GET', '/api/v1/qbank/home/check-in-calendar?year=2026&month=4', '打卡日历', None),
]


def run_benchmark(
    base_url: str,
    token: str,
    rounds: int = 1,
    slow_threshold: int = 200,
) -> None:
    """
    执行基准测试

    :param base_url: API 基础 URL
    :param token: JWT token
    :param rounds: 测试轮数（取平均值）
    :param slow_threshold: 慢接口阈值 (ms)
    """
    headers = {'Authorization': f'Bearer {token}'}

    results: list[dict] = []

    print(f'\n  Base URL:  {base_url}')
    print(f'  Rounds:    {rounds}')
    print(f'  Endpoints: {len(ENDPOINTS)}')
    print(f'  Slow threshold: {slow_threshold}ms\n')

    for method, path, desc, body in ENDPOINTS:
        url = f'{base_url}{path}'
        times: list[float] = []
        status = 0
        error_msg = ''

        for _ in range(rounds):
            try:
                start = time.perf_counter()
                with httpx.Client(timeout=10, headers=headers) as client:
                    if method == 'GET':
                        resp = client.get(url)
                    else:
                        resp = client.post(url, json=body or {})
                elapsed = (time.perf_counter() - start) * 1000
                times.append(elapsed)
                status = resp.status_code
            except httpx.TimeoutException:
                error_msg = 'TIMEOUT'
                break
            except Exception as e:
                error_msg = str(e)[:30]
                break

        avg_ms = sum(times) / len(times) if times else 0
        results.append({
            'method': method,
            'path': path.split('?')[0],
            'desc': desc,
            'avg_ms': avg_ms,
            'status': status,
            'error': error_msg,
        })

        # 实时进度
        tag = 'SLOW' if avg_ms > slow_threshold else 'OK'
        if error_msg:
            tag = 'ERR'
        status_display = error_msg if error_msg else status
        print(f'  [{tag:>4}] {avg_ms:>7.1f}ms  {status_display:<5} {method:>4} {desc}')

    # ---- 汇总报告 ----
    results.sort(key=lambda r: r['avg_ms'], reverse=True)

    print('\n' + '=' * 72)
    print('  RESULTS (sorted by response time, slowest first)')
    print('=' * 72)
    print(f'  {"ms":>8}  {"status":>6}  {"method":>6}  {"description":<16}  path')
    print('-' * 72)

    total_ms = 0
    slow_count = 0
    for r in results:
        ms = r['avg_ms']
        total_ms += ms
        is_slow = ms > slow_threshold
        if is_slow:
            slow_count += 1
        marker = ' !!!' if is_slow else ('  X ' if r['error'] else '    ')
        status_display = r['error'] if r['error'] else r['status']
        print(f'{marker}{ms:>7.1f}ms  {status_display:>6}  {r["method"]:>6}  {r["desc"]:<16}  {r["path"]}')

    print('-' * 72)
    print(f'  Total: {total_ms:.0f}ms  |  Avg: {total_ms / len(results):.0f}ms  |  Slow (>{slow_threshold}ms): {slow_count}/{len(results)}')
    print()


def main() -> None:
    parser = argparse.ArgumentParser(description='API 接口响应时间批量检测')
    parser.add_argument('--token', required=True, help='JWT Bearer token')
    parser.add_argument('--base', default='http://127.0.0.1:8000', help='API base URL (default: http://127.0.0.1:8000)')
    parser.add_argument('--rounds', type=int, default=1, help='测试轮数，取平均值 (default: 1)')
    parser.add_argument('--slow', type=int, default=200, help='慢接口阈值 ms (default: 200)')
    args = parser.parse_args()

    token = args.token.replace('Bearer ', '')
    run_benchmark(base_url=args.base, token=token, rounds=args.rounds, slow_threshold=args.slow)


if __name__ == '__main__':
    main()
