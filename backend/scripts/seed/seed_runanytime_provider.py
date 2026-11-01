#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""给生产库（或 dev）新增 RunAnyTime 对话模型供应商。

背景：用户 2026-10-31 给了新的 OpenAI 兼容网关
`https://runanytime.hxi.me`（new-api 类），可用模型：
gpt-5.5 / gpt-4o / gpt-4o-mini / gpt-4 / gpt-4-32k / gpt-5.6-sol / gpt-6-astra。

⚠️ **API Key 不写进本文件**：从环境变量 `RUNANYTIME_API_KEY` 读，缺了直接退出。
   早期 seed 脚本把 key 写在常量里，结果 key 会跟着 git 到处跑。

⚠️ `api_host` 只存**根地址**（不带 `/v1`）—— `ChatService` 会自己补：
   `base_url = f'{host}/v1' if not host.endswith('/v1') else host`。

用法（默认干跑，加 --write 才真写）：
    cd backend
    RUNANYTIME_API_KEY=sk-xxx \
      ../.venv/Scripts/python.exe scripts/seed/seed_runanytime_provider.py
    RUNANYTIME_API_KEY=sk-xxx \
      ../.venv/Scripts/python.exe scripts/seed/seed_runanytime_provider.py --write

连接哪个库由 `DATABASE_HOST/PORT/USER/PASSWORD` 环境变量决定（默认取 backend/.env）。
"""

from __future__ import annotations

import asyncio
import os
import sys

from pathlib import Path

import asyncpg

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

PROVIDER_NAME = 'RunAnyTime'
API_HOST = 'https://runanytime.hxi.me'
# 只放两个用户点名的模型；需要别的（gpt-4o-mini 等）在后台页面加即可
MODELS = ('gpt-5.5', 'gpt-4o')
OWNED_BY = 'openai'
# type=0 是普通对话模型；11 是决策模型（Jev），别混
PROVIDER_TYPE = 0


def _dsn() -> str:
    """连接串只认标准式 postgresql://user:pass@host:port/db。"""
    host = os.getenv('DATABASE_HOST', '127.0.0.1')
    port = os.getenv('DATABASE_PORT', '5432')
    user = os.getenv('DATABASE_USER', 'postgres')
    password = os.getenv('DATABASE_PASSWORD', '')
    database = os.getenv('DATABASE_NAME', 'fba')
    return f'postgresql://{user}:{password}@{host}:{port}/{database}'


async def _detect_schema(conn: asyncpg.Connection) -> str:
    """生产表在 fba，dev 只有 public —— 不能硬编码。"""
    row = await conn.fetchrow(
        """
        SELECT table_schema FROM information_schema.tables
        WHERE table_name = 'ai_provider'
        ORDER BY (table_schema = 'fba') DESC
        LIMIT 1
        """
    )
    if row is None:
        msg = '找不到 ai_provider 表，检查连接的库'
        raise SystemExit(msg)
    return row['table_schema']


async def main(*, write: bool) -> int:
    api_key = (os.getenv('RUNANYTIME_API_KEY') or '').strip()
    if not api_key:
        print('[x] 缺环境变量 RUNANYTIME_API_KEY')
        return 2

    conn = await asyncpg.connect(_dsn(), timeout=30)
    try:
        schema = await _detect_schema(conn)
        print(f'[i] schema={schema}  write={write}')

        existing = await conn.fetchrow(
            f'SELECT id, name, status, deleted FROM {schema}.ai_provider '
            'WHERE api_host = $1 ORDER BY deleted, id LIMIT 1',
            API_HOST,
        )

        if existing is not None:
            provider_id = existing['id']
            print(
                f"[=] 已存在 provider id={provider_id} name={existing['name']} "
                f"status={existing['status']} deleted={existing['deleted']}"
            )
        else:
            print(f'[+] 将新增 provider: {PROVIDER_NAME} / {API_HOST}')
            if not write:
                print('[dry-run] 不写库，加 --write 执行')
                return 0
            provider_id = await conn.fetchval(
                f"""
                INSERT INTO {schema}.ai_provider
                    (name, type, api_key, api_host, status, remark, created_time, deleted)
                VALUES
                    ($1, $2, $3, $4, 1, $5, now(), 0)
                RETURNING id
                """,
                PROVIDER_NAME,
                PROVIDER_TYPE,
                api_key,
                API_HOST,
                '2026-10-31 新增；模型 gpt-5.5 / gpt-4o',
            )
            print(f'[OK] provider id={provider_id}')

        for model_id in MODELS:
            row = await conn.fetchrow(
                f'SELECT id, status, deleted FROM {schema}.ai_model '
                'WHERE provider_id = $1 AND model_id = $2 ORDER BY deleted, id LIMIT 1',
                provider_id,
                model_id,
            )
            if row is not None:
                print(
                    f'[=] model {model_id} 已存在 id={row["id"]} '
                    f'status={row["status"]} deleted={row["deleted"]}'
                )
                continue
            print(f'[+] 将新增 model {model_id}')
            if not write:
                continue
            mid = await conn.fetchval(
                f"""
                INSERT INTO {schema}.ai_model
                    (provider_id, model_id, owned_by, status, created_time, deleted)
                VALUES ($1, $2, $3, 1, now(), 0)
                RETURNING id
                """,
                provider_id,
                model_id,
                OWNED_BY,
            )
            print(f'[OK] model {model_id} id={mid}')

        # 幂等收尾：provider 若被逻辑删过，恢复成可用；key 变了同步更新
        if write:
            await conn.execute(
                f'UPDATE {schema}.ai_provider '
                'SET status = 1, deleted = 0, deleted_time = NULL, '
                'api_key = $2, updated_time = now() WHERE id = $1',
                provider_id,
                api_key,
            )
            print('[OK] provider 状态/key 已同步（status=1, deleted=0）')

        rows = await conn.fetch(
            f"""
            SELECT p.id AS pid, p.name, p.status, p.deleted,
                   m.id AS mid, m.model_id, m.status AS mstatus, m.deleted AS mdeleted
            FROM {schema}.ai_provider p
            LEFT JOIN {schema}.ai_model m ON m.provider_id = p.id
            WHERE p.id = $1 ORDER BY m.id
            """,
            provider_id,
        )
        print('--- 当前状态 ---')
        for r in rows:
            print(
                f"provider {r['pid']} {r['name']} status={r['status']} "
                f"deleted={r['deleted']} | model {r['mid']} {r['model_id']} "
                f"status={r['mstatus']} deleted={r['mdeleted']}"
            )
    finally:
        await conn.close()
    return 0


if __name__ == '__main__':
    sys.exit(asyncio.run(main(write='--write' in sys.argv)))
