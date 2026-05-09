#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SDK 覆盖率与有效性检查

通过 import FastAPI app router 拿到后端真实路由清单,
再静态扫 packages/api-sdk/src/modules/*.ts 抽出 request.<method>('/path') 调用,
归一化路径模板后做集合 diff。

输出三类问题:
1. missing  : 后端有 / SDK 无 (漏写)
2. invalid  : SDK 有 / 后端无 (路径写错或后端已删)
3. unparsed : SDK 中无法静态解析的动态调用 (拼接变量等)
"""
from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = PROJECT_ROOT / 'backend'
SDK_MODULES_DIR = PROJECT_ROOT / 'packages' / 'api-sdk' / 'src' / 'modules'
OUTPUT_PATH = BACKEND_ROOT / 'scripts' / 'outputs' / 'sdk_coverage_report.json'

sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(BACKEND_ROOT))

# 强制 stdout 用 UTF-8, 避免 Windows GBK 控制台编码错误
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# 仅 import 路由聚合器, 不启动整个 app, 避免触发 lifespan
from fastapi.routing import APIRoute  # noqa: E402

from backend.app.router import router as backend_router  # noqa: E402
from backend.core.conf import settings  # noqa: E402

API_PREFIX = settings.FASTAPI_API_V1_PATH  # /api/v1
PATH_PARAM_RE = re.compile(r'\{[^}]+\}')
SDK_TPL_RE = re.compile(r'\$\{[^}]+\}')

# 匹配 request.get<X>('/path', ...) / request.post(`/path/${id}`, ...) 等
SDK_CALL_RE = re.compile(
    r"""request\s*\.\s*(get|post|put|delete|patch)\s*"""
    r"""(?:<[^>(]*>)?"""              # 可选 TypeScript 泛型
    r"""\s*\(\s*"""
    r"""(?P<quote>[`'\"])"""
    r"""(?P<path>[^`'\"]+)"""
    r"""(?P=quote)""",
    re.MULTILINE,
)
# 匹配动态拼接调用, 如 request.get(somePath) — 用于报告 unparsed
SDK_DYN_RE = re.compile(
    r"""request\s*\.\s*(get|post|put|delete|patch)\s*"""
    r"""(?:<[^>(]*>)?"""
    r"""\s*\(\s*(?![`'\"])(?P<expr>[A-Za-z_$][\w$]*)""",
    re.MULTILINE,
)
# 匹配 createScopedClient(client, '/prefix') 或 createScopedClient(client, "")
SDK_PREFIX_RE = re.compile(
    r"""createScopedClient\s*\(\s*\w+\s*,\s*['"`](?P<prefix>[^'"`]*)['"`]\s*\)""",
)


def normalize_backend(path: str) -> str:
    """后端路径归一化: 剥离 /api/v1 前缀, 占位符统一为 {x}"""
    if path.startswith(API_PREFIX):
        path = path[len(API_PREFIX):] or '/'
    return PATH_PARAM_RE.sub('{x}', path)


def normalize_sdk(path: str) -> str:
    """SDK 路径归一化: 模板表达式 ${...} 统一为 {x}"""
    return SDK_TPL_RE.sub('{x}', path)


def collect_backend_routes() -> dict[tuple[str, str], list[str]]:
    """收集后端 (METHOD, NORMALIZED_PATH) -> [endpoint qualified name]"""
    routes: dict[tuple[str, str], list[str]] = defaultdict(list)
    for r in backend_router.routes:
        if not isinstance(r, APIRoute):
            continue
        norm = normalize_backend(r.path)
        endpoint_qual = f'{r.endpoint.__module__}.{r.endpoint.__name__}'
        for method in sorted(r.methods - {'HEAD', 'OPTIONS'}):
            routes[(method.upper(), norm)].append(endpoint_qual)
    return routes


def collect_sdk_routes() -> tuple[
    dict[tuple[str, str], list[str]],
    list[dict[str, str]],
]:
    """收集 SDK (METHOD, NORMALIZED_PATH) -> [file:line], 同时返回无法解析的动态调用"""
    routes: dict[tuple[str, str], list[str]] = defaultdict(list)
    unparsed: list[dict[str, str]] = []

    if not SDK_MODULES_DIR.exists():
        print(f'[!] SDK 目录不存在: {SDK_MODULES_DIR}', file=sys.stderr)
        return routes, unparsed

    for ts in sorted(SDK_MODULES_DIR.glob('*.ts')):
        if ts.name.startswith('_'):
            continue
        text = ts.read_text(encoding='utf-8')
        # 解析当前文件的 scoped client 前缀; 没有则视为空
        prefix_match = SDK_PREFIX_RE.search(text)
        scope_prefix = prefix_match.group('prefix') if prefix_match else ''
        if scope_prefix and not scope_prefix.startswith('/'):
            scope_prefix = '/' + scope_prefix
        # 静态字面量调用
        for m in SDK_CALL_RE.finditer(text):
            method = m.group(1).upper()
            raw_path = m.group('path')
            if not raw_path.startswith('/'):
                raw_path = '/' + raw_path
            full_path = scope_prefix + raw_path if scope_prefix else raw_path
            norm_path = normalize_sdk(full_path)
            line_no = text[:m.start()].count('\n') + 1
            routes[(method, norm_path)].append(f'{ts.name}:{line_no}')
        # 动态变量调用
        for m in SDK_DYN_RE.finditer(text):
            line_no = text[:m.start()].count('\n') + 1
            unparsed.append({
                'file': f'{ts.name}:{line_no}',
                'method': m.group(1).upper(),
                'expr': m.group('expr'),
            })
    return routes, unparsed


def main() -> None:
    print(f'[i] 后端路由源: backend.app.router (前缀 {API_PREFIX})')
    print(f'[i] SDK 模块目录: {SDK_MODULES_DIR}')
    print()

    backend_routes = collect_backend_routes()
    sdk_routes, unparsed = collect_sdk_routes()

    backend_keys = set(backend_routes.keys())
    sdk_keys = set(sdk_routes.keys())

    missing = sorted(backend_keys - sdk_keys)
    invalid = sorted(sdk_keys - backend_keys)
    covered = sorted(backend_keys & sdk_keys)

    print('=' * 72)
    print(f'后端路由总数: {len(backend_keys)}')
    print(f'SDK 调用总数: {len(sdk_keys)}')
    print(f'已覆盖: {len(covered)}  '
          f'未覆盖(missing): {len(missing)}  '
          f'无效(invalid): {len(invalid)}  '
          f'动态(unparsed): {len(unparsed)}')
    print('=' * 72)

    if missing:
        print('\n--- [MISSING] 后端有, SDK 无 ---')
        for method, path in missing:
            endpoints = backend_routes[(method, path)]
            print(f'  {method:6s} {path}    -> {endpoints[0]}')

    if invalid:
        print('\n--- [INVALID] SDK 有, 后端无 (路径错或接口已删) ---')
        for method, path in invalid:
            locs = sdk_routes[(method, path)]
            print(f'  {method:6s} {path}    @ {", ".join(locs)}')

    if unparsed:
        print('\n--- [UNPARSED] SDK 中动态拼接, 无法静态校验 ---')
        for item in unparsed:
            print(f'  {item["method"]:6s} <var:{item["expr"]}>    @ {item["file"]}')

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    report = {
        'summary': {
            'backend_total': len(backend_keys),
            'sdk_total': len(sdk_keys),
            'covered': len(covered),
            'missing': len(missing),
            'invalid': len(invalid),
            'unparsed': len(unparsed),
        },
        'missing': [
            {'method': m, 'path': p, 'endpoint': backend_routes[(m, p)]}
            for m, p in missing
        ],
        'invalid': [
            {'method': m, 'path': p, 'locations': sdk_routes[(m, p)]}
            for m, p in invalid
        ],
        'unparsed': unparsed,
        'covered': [{'method': m, 'path': p} for m, p in covered],
    }
    OUTPUT_PATH.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')
    print(f'\n[✓] 完整报告已写入: {OUTPUT_PATH}')


if __name__ == '__main__':
    main()
