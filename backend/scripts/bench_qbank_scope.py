#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
qbank 学习领域接口性能对比脚本

用法:
    python backend/scripts/bench_qbank_scope.py
    python backend/scripts/bench_qbank_scope.py --rounds 30
    python backend/scripts/bench_qbank_scope.py --code kaoyan --rounds 50
    python backend/scripts/bench_qbank_scope.py --base http://127.0.0.1:8000 --warmup 5

    并发模拟首屏（同时发起 N 个混合请求，看排队效应）:
    python backend/scripts/bench_qbank_scope.py --concurrent 10 --code kaoyan

聚焦验证以下两个接口的耗时:
    GET /api/v1/qbank/study-domains/scope?code=<code>
    GET /api/v1/qbank/banks?status=1&study_domain=<code>

输出: min / avg / p50 / p95 / max (ms)，并按学习领域 code 分组对比
"""

import argparse
import asyncio
import statistics
import time

import httpx


def percentile(values: list[float], pct: float) -> float:
    """
    计算分位数

    :param values: 数值列表
    :param pct: 百分位 (0-100)
    :return:
    """
    if not values:
        return 0.0
    sorted_values = sorted(values)
    k = (len(sorted_values) - 1) * pct / 100
    f = int(k)
    c = min(f + 1, len(sorted_values) - 1)
    if f == c:
        return sorted_values[f]
    return sorted_values[f] + (sorted_values[c] - sorted_values[f]) * (k - f)


def bench_one(client: httpx.Client, url: str, rounds: int) -> tuple[list[float], int, str]:
    """
    对单个 URL 多次采样

    :param client: 复用的 HTTP 客户端
    :param url: 完整请求地址
    :param rounds: 采样次数
    :return:
    """
    samples: list[float] = []
    last_status = 0
    last_err = ''

    for _ in range(rounds):
        try:
            start = time.perf_counter()
            resp = client.get(url)
            elapsed = (time.perf_counter() - start) * 1000
            samples.append(elapsed)
            last_status = resp.status_code
        except httpx.TimeoutException:
            last_err = 'TIMEOUT'
            break
        except Exception as e:
            last_err = str(e)[:40]
            break

    return samples, last_status, last_err


def fmt_stats(samples: list[float]) -> str:
    """
    格式化分布

    :param samples: 采样毫秒数
    :return:
    """
    if not samples:
        return 'N/A'
    return (
        f'min={min(samples):>6.1f}  '
        f'avg={statistics.mean(samples):>6.1f}  '
        f'p50={percentile(samples, 50):>6.1f}  '
        f'p95={percentile(samples, 95):>6.1f}  '
        f'max={max(samples):>6.1f}'
    )


def run(
    base_url: str,
    codes: list[str],
    rounds: int,
    warmup: int,
    token: str | None,
) -> None:
    """
    执行 benchmark

    :param base_url: API 基础 URL
    :param codes: 学习领域 code 列表
    :param rounds: 每个接口采样次数
    :param warmup: 预热次数（不计入统计）
    :param token: 可选 JWT
    :return:
    """
    headers = {'Authorization': f'Bearer {token}'} if token else {}

    endpoints = [
        ('scope', '/api/v1/qbank/study-domains/scope?code={code}'),
        ('banks', '/api/v1/qbank/banks?status=1&study_domain={code}'),
    ]

    print(f'\n  Base URL:  {base_url}')
    print(f'  Codes:     {", ".join(codes)}')
    print(f'  Rounds:    {rounds}  (warmup {warmup})')
    print(f'  Token:     {"yes" if token else "no"}\n')

    with httpx.Client(timeout=15, headers=headers) as client:
        for code in codes:
            print(f'  ── code = {code} ' + '─' * (60 - len(code)))
            for name, path_tpl in endpoints:
                url = f'{base_url}{path_tpl.format(code=code)}'

                # 预热: 命中代码路径、避开冷启动毛刺
                if warmup:
                    bench_one(client, url, warmup)

                samples, status, err = bench_one(client, url, rounds)
                if err:
                    print(f'    {name:>5} | ERROR {err}')
                    continue
                print(f'    {name:>5} | status={status} | {fmt_stats(samples)}')
            print()


def main() -> None:
    parser = argparse.ArgumentParser(description='qbank 学习领域接口性能对比')
    parser.add_argument('--base', default='http://127.0.0.1:8000', help='API base URL')
    parser.add_argument(
        '--code',
        action='append',
        help='学习领域 code，可多次传入；默认覆盖 cet/kaoyan/gongkao',
    )
    parser.add_argument('--rounds', type=int, default=20, help='每接口采样次数 (default: 20)')
    parser.add_argument('--warmup', type=int, default=3, help='预热次数 (default: 3)')
    parser.add_argument('--token', default=None, help='可选 JWT（接口本身是公开接口）')
    parser.add_argument(
        '--concurrent',
        type=int,
        default=0,
        help='并发模式：一次性同时发起 N 个 scope+banks 请求，模拟首屏抢资源',
    )
    args = parser.parse_args()

    codes = args.code or ['cet', 'kaoyan', 'gongkao']
    token = args.token.replace('Bearer ', '') if args.token else None

    if args.concurrent > 0:
        asyncio.run(
            run_concurrent(
                base_url=args.base,
                code=codes[0],
                concurrent=args.concurrent,
                token=token,
            )
        )
        return

    run(
        base_url=args.base,
        codes=codes,
        rounds=args.rounds,
        warmup=args.warmup,
        token=token,
    )


async def run_concurrent(
    base_url: str,
    code: str,
    concurrent: int,
    token: str | None,
) -> None:
    """
    并发模拟首屏：N 个请求同时打过去，量化排队效应

    :param base_url: API 基础 URL
    :param code: 学习领域 code
    :param concurrent: 并发数
    :param token: 可选 JWT
    :return:
    """
    headers = {'Authorization': f'Bearer {token}'} if token else {}

    scope_url = f'{base_url}/api/v1/qbank/study-domains/scope?code={code}'
    banks_url = f'{base_url}/api/v1/qbank/banks?status=1&study_domain={code}'

    print(f'\n  Concurrent mode: {concurrent} parallel requests (mix of scope + banks)')
    print(f'  Code: {code}\n')

    async with httpx.AsyncClient(timeout=30, headers=headers) as client:
        # 预热一次串行，让缓存/连接池稳定
        await client.get(scope_url)
        await client.get(banks_url)

        async def call(url: str, label: str) -> tuple[str, float, int]:
            start = time.perf_counter()
            try:
                resp = await client.get(url)
                elapsed = (time.perf_counter() - start) * 1000
                return label, elapsed, resp.status_code
            except Exception as e:
                return label, -1.0, 0

        # 一半 scope 一半 banks，模拟首屏
        tasks = []
        for i in range(concurrent):
            if i % 2 == 0:
                tasks.append(call(scope_url, 'scope'))
            else:
                tasks.append(call(banks_url, 'banks'))

        wall_start = time.perf_counter()
        results = await asyncio.gather(*tasks)
        wall_total = (time.perf_counter() - wall_start) * 1000

    scope_times = [t for label, t, _ in results if label == 'scope' and t > 0]
    banks_times = [t for label, t, _ in results if label == 'banks' and t > 0]

    print(f'  Wall total: {wall_total:.1f}ms (all {concurrent} requests done)\n')
    if scope_times:
        print(f'    scope ({len(scope_times)} reqs) | {fmt_stats(scope_times)}')
    if banks_times:
        print(f'    banks ({len(banks_times)} reqs) | {fmt_stats(banks_times)}')
    print()


if __name__ == '__main__':
    main()
