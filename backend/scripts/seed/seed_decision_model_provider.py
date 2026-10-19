#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""给 dev 库补一条「决策模型」通道配置（结构对齐生产库，api_key 留空）。

背景：`/autolabels/decision-models` 只返回 `ai_provider.type = decision_model(11)`
且 `status=1`、`ai_model.status=1` 的通道。dev 库原本一条都没有 ⇒ 页面上模型下拉为空。

⚠️ **api_key 故意留空**：不把生产密钥搬进 dev。填完空字符串后，
`decision-models` 接口能返回该通道（下拉就有选项了），但真正调用会 401，
需要你到「AI 供应商」管理页把百炼的 api_key 填进去。
若 dev 后端进程的环境变量里有 `DASHSCOPE_API_KEY`，也能直接生效。

幂等：靠 (type=11) 判断是否已存在；已存在则只更新非密钥字段。
连哪台库由 backend/.env 决定；pydantic-settings 下环境变量优先于 .env。
"""

from __future__ import annotations

import asyncio
import sys

from pathlib import Path
from typing import TYPE_CHECKING

from sqlalchemy import text

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.database.db import async_db_session  # noqa: E402

PROVIDER_NAME = '阿里云百炼决策模型'
API_HOST = (
    'https://ws-72im6229rwe2na8f.cn-beijing.maas.aliyuncs.com'
    '/compatible-mode/v1/systemone'
)
MODEL_ID = 'decision-model-preview'
REMARK = 'System One 协议（决策模型）；api_host 存到完整 endpoint'

DETECT_SCHEMA_SQL = """
SELECT COALESCE(
    (SELECT nspname FROM pg_class c
       JOIN pg_namespace n ON n.oid = c.relnamespace
      WHERE c.relname = 'ai_provider' AND c.relkind = 'r'
        AND n.nspname IN ('fba', 'public')
      ORDER BY (n.nspname = 'fba') DESC
      LIMIT 1),
    'public'
) AS schema;
"""

# ⚠️ 只在决策模型行不存在时插入；已存在则把 status 恢复为 1（不碰 api_key）
UPSERT_PROVIDER_SQL = """
INSERT INTO {schema}.ai_provider (
    name, type, api_key, api_host, status, remark, created_time
)
SELECT CAST(:name AS VARCHAR), CAST(:ptype AS SMALLINT), CAST('' AS VARCHAR),
       CAST(:api_host AS VARCHAR), CAST(1 AS SMALLINT), CAST(:remark AS TEXT), NOW()
WHERE NOT EXISTS (
    SELECT 1 FROM {schema}.ai_provider
    WHERE type = CAST(:ptype AS SMALLINT) AND deleted = 0
)
RETURNING id;
"""

ENABLE_PROVIDER_SQL = """
UPDATE {schema}.ai_provider
SET status = 1, api_host = CAST(:api_host AS VARCHAR),
    remark = CAST(:remark AS TEXT), updated_time = NOW()
WHERE type = CAST(:ptype AS SMALLINT) AND deleted = 0
RETURNING id;
"""

UPSERT_MODEL_SQL = """
INSERT INTO {schema}.ai_model (
    provider_id, model_id, owned_by, status, remark, created_time
)
SELECT CAST(:provider_id AS BIGINT), CAST(:model_id AS VARCHAR),
       CAST('aliyun' AS VARCHAR), CAST(1 AS SMALLINT), NULL, NOW()
WHERE NOT EXISTS (
    SELECT 1 FROM {schema}.ai_model
    WHERE provider_id = CAST(:provider_id AS BIGINT)
      AND model_id = CAST(:model_id AS VARCHAR)
      AND deleted = 0
)
RETURNING id;
"""

ENABLE_MODEL_SQL = """
UPDATE {schema}.ai_model
SET status = 1, updated_time = NOW()
WHERE provider_id = CAST(:provider_id AS BIGINT)
  AND model_id = CAST(:model_id AS VARCHAR)
  AND deleted = 0
RETURNING id;
"""

# 与 list_decision_models() 的 WHERE 完全一致，用来自检
VERIFY_SQL = """
SELECT p.id AS provider_id, p.name AS provider_name, p.api_host,
       m.model_id, m.id AS model_id_pk
FROM {schema}.ai_model m
JOIN {schema}.ai_provider p ON p.id = m.provider_id
WHERE p.type = CAST(:ptype AS SMALLINT) AND p.status = 1 AND p.deleted = 0
  AND m.status = 1 AND m.deleted = 0
ORDER BY p.id, m.id;
"""


async def seed(db: AsyncSession, *, write: bool) -> None:
    schema = str((await db.execute(text(DETECT_SCHEMA_SQL))).scalar() or 'public')
    ptype = 11  # AIProviderType.decision_model
    print(f'[i] ai_provider 所在 schema：{schema}')

    params = {
        'api_host': API_HOST,
        'model_id': MODEL_ID,
        'name': PROVIDER_NAME,
        'ptype': ptype,
        'remark': REMARK,
    }

    if not write:
        print('[i] --write 未加，只干跑')
        return

    # provider 已存在（含被停用的）就只恢复，不重复插
    res = await db.execute(text(UPSERT_PROVIDER_SQL.format(schema=schema)), params)
    created = res.scalar()
    res = await db.execute(text(ENABLE_PROVIDER_SQL.format(schema=schema)), params)
    provider_id = res.scalar()
    if provider_id is None:
        msg = '决策模型 provider 插入/启用失败'
        raise RuntimeError(msg)
    print(
        f'[i] provider id={provider_id}'
        f'{"（新建）" if created is not None else "（已存在，恢复启用）"}'
    )

    mres = await db.execute(
        text(UPSERT_MODEL_SQL.format(schema=schema)),
        {**params, 'provider_id': provider_id},
    )
    mcreated = mres.scalar()
    mres = await db.execute(
        text(ENABLE_MODEL_SQL.format(schema=schema)),
        {**params, 'provider_id': provider_id},
    )
    model_pk = mres.scalar()
    print(
        f'[i] model id={model_pk}'
        f'{"（新建）" if mcreated is not None else "（已存在，恢复启用）"}'
    )

    rows = (await db.execute(text(VERIFY_SQL.format(schema=schema)), params)).fetchall()
    print(f'\n[OK] decision-models 接口将返回 {len(rows)} 条：')
    for r in rows:
        print(f'  provider_id={r[0]} {r[1]} · {r[3]}  ({r[2]})')
    if rows:
        print('\n[!] api_key 是空的 —— 下拉能出选项，但真正调用会 401。')
        print('    请到「AI 供应商」页给这条填 api_key，或给后端进程设 DASHSCOPE_API_KEY。')


async def main() -> int:
    write = '--write' in sys.argv
    print(f'[i] 模式：{"干跑（默认）" if not write else "写入（--write）"}')
    async with async_db_session.begin() as db:
        await seed(db, write=write)
    return 0


if __name__ == '__main__':
    raise SystemExit(asyncio.run(main()))
