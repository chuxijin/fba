#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
导出 OpenAPI 3.x JSON, 用于驱动前端 SDK 自动生成 (hey-api/openapi-ts)

特性:
1. 不启动 uvicorn / 不触发 lifespan, 避免连 Redis / 雪花 ID 等副作用
2. 通过 build_final_router() 聚合所有路由(含插件), 构造最小 FastAPI 实例后调用 app.openapi()
3. 默认输出到 packages/api-sdk/openapi.json (跨包路径), 支持 --output 覆盖
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT = PROJECT_ROOT / 'packages' / 'api-sdk' / 'openapi.json'

sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / 'backend'))

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from fastapi import FastAPI  # noqa: E402

from backend.core.conf import settings  # noqa: E402
from backend.plugin.router import build_final_router  # noqa: E402
from backend.utils.openapi import ensure_unique_route_names, simplify_operation_ids  # noqa: E402


def build_minimal_app() -> FastAPI:
    """构造仅含路由的 FastAPI 实例, 跳过中间件/插件/lifespan"""
    app = FastAPI(
        title=settings.FASTAPI_TITLE,
        version='1.0.0',
        description=settings.FASTAPI_DESCRIPTION,
    )
    final_router = build_final_router()
    app.include_router(final_router)
    # 与 register_app() 保持一致: 让 operation_id 等于函数名 (snake_case),
    # hey-api 会自动转 camelCase (例如 get_quest_list -> getQuestList)
    ensure_unique_route_names(app)
    simplify_operation_ids(app)
    return app


def dump(output: Path) -> None:
    app = build_minimal_app()
    schema = app.openapi()

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(schema, indent=2, ensure_ascii=False),
        encoding='utf-8',
    )

    paths = schema.get('paths', {})
    op_count = sum(
        1
        for methods in paths.values()
        for method in methods
        if method.lower() in {'get', 'post', 'put', 'delete', 'patch'}
    )
    schema_count = len(schema.get('components', {}).get('schemas', {}))

    print(f'[OK] OpenAPI schema written: {output}')
    print(f'     paths      : {len(paths)}')
    print(f'     operations : {op_count}')
    print(f'     schemas    : {schema_count}')


def main() -> None:
    parser = argparse.ArgumentParser(description='Dump OpenAPI schema for SDK codegen')
    parser.add_argument(
        '--output',
        '-o',
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f'Output path (default: {DEFAULT_OUTPUT})',
    )
    args = parser.parse_args()
    dump(args.output)


if __name__ == '__main__':
    main()
