#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
飞书表导出配置：建表 + 首次落「公考」配置（幂等，可重复执行）

为什么不用 alembic：
  本仓库 alembic 版本链与数据库现状不一致（alembic_version 指向仓库中不存在的 revision），
  `alembic current/upgrade` 会直接报 `Can't locate revision identified by '...'`。
  同时 `fba alembic` 子命令在仓库根目录执行时 script_location 解析失败。
  而应用启动统一走 `MappedBase.metadata.create_all()`（backend/core/registrar.py），
  所以这里用同等口径建表并补种子数据，dev / 生产都可直接使用。

对应迁移文件（供 alembic 恢复可用后对齐）：
  backend/alembic/versions/2026-09-19-20_30_00-a7c1e9d2b435_add_feishu_sheet_export_config.py

用法（在仓库根目录执行，使用项目 venv）:
    python scripts/apply_feishu_sheet_config.py           # 建表 + 落配置（幂等）
    python scripts/apply_feishu_sheet_config.py --check   # 只读体检，不改动任何数据
"""

from __future__ import annotations

import argparse
import asyncio
import importlib.util
import sys

from pathlib import Path
from typing import Any

import sqlalchemy as sa

from sqlalchemy import select

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.mydrive.model.feishu import FeishuSheetConfig, FeishuSheetTask  # noqa: E402
from backend.core.conf import settings  # noqa: E402
from backend.database.db import async_db_session, async_engine  # noqa: E402

MIGRATION_PATH = (
    ROOT / 'backend' / 'alembic' / 'versions' / '2026-09-19-20_30_00-a7c1e9d2b435_add_feishu_sheet_export_config.py'
)
CONFIG_NAME = '公考'

# 迁移尚在搬运阶段时 settings 中存在的字段；配置迁完后这些字段会被移除
MIGRATION_FIELDS = (
    'GONGKAO_FEISHU_SYNC_ENABLED',
    'GONGKAO_FEISHU_SHEET_MAP',
    'GONGKAO_FEISHU_CATEGORY_APP_CODE',
    'GONGKAO_FEISHU_CATEGORY_TYPE',
    'GONGKAO_FEISHU_CATEGORY_OPTIONS',
    'GONGKAO_FEISHU_SOURCE_WEIGHTS',
    'GONGKAO_FEISHU_PAID_SHEETS',
)

# 落种子用的默认值（迁移常量即唯一来源，避免两处维护）
SEED_CRON = '0 3 * * *'


def load_migration() -> Any:
    """按文件路径加载迁移模块，用于比对常量与 settings 原值"""
    spec = importlib.util.spec_from_file_location('migration_feishu_sheet_config', MIGRATION_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f'无法加载迁移文件: {MIGRATION_PATH}')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def parse_pairs(items: list[str]) -> dict[str, str]:
    """解析 ['键=值'] 形式的配置项"""
    result: dict[str, str] = {}
    for item in items:
        key, _, value = str(item).partition('=')
        key, value = key.strip(), value.strip()
        if key and value:
            result[key] = value
    return result


def settings_values() -> dict[str, Any]:
    """从 settings（plugin.toml / .env）读出的当前值，作为搬运前的「原值」基准"""
    return {
        'name': CONFIG_NAME,
        'app_code': settings.GONGKAO_FEISHU_CATEGORY_APP_CODE,
        'category_type': settings.GONGKAO_FEISHU_CATEGORY_TYPE,
        'sheet_url': settings.FEISHU_SHEET_URL,
        'sheet_map': parse_pairs(settings.GONGKAO_FEISHU_SHEET_MAP),
        'category_options': list(settings.GONGKAO_FEISHU_CATEGORY_OPTIONS),
        'source_weights': {
            key: int(value) for key, value in parse_pairs(settings.GONGKAO_FEISHU_SOURCE_WEIGHTS).items()
        },
        'paid_sheets': list(settings.GONGKAO_FEISHU_PAID_SHEETS),
        'is_enabled': bool(settings.GONGKAO_FEISHU_SYNC_ENABLED),
    }


def compare_with_migration() -> bool:
    """
    校验迁移文件里硬编码的常量与 settings 原值是否逐字一致

    注意：配置已迁入 feishu_sheet_config 表后，`settings.GONGKAO_FEISHU_*` 已被移除
    （plugin.toml 与 core/conf.py 均不再声明），此校验只在迁移尚未落地时才有意义。
    因此找不到这些字段时直接跳过，不视为失败。

    :return: 是否一致（跳过时为 True）
    """
    migration = load_migration()
    missing = [field for field in MIGRATION_FIELDS if not hasattr(settings, field)]
    if missing:
        print('== 配置搬运核对 ==')
        print(f'  settings 中已不存在 {missing}')
        print('  -> 说明配置已完全迁入 feishu_sheet_config 表，跳过搬运核对\n')
        return True

    current = settings_values()
    expected = {
        'name': migration.GONGKAO_NAME,
        'app_code': migration.GONGKAO_APP_CODE,
        'category_type': migration.GONGKAO_CATEGORY_TYPE,
        'sheet_url': migration.GONGKAO_SHEET_URL,
        'sheet_map': migration.GONGKAO_SHEET_MAP,
        'category_options': migration.GONGKAO_CATEGORY_OPTIONS,
        'source_weights': migration.GONGKAO_SOURCE_WEIGHTS,
        'paid_sheets': migration.GONGKAO_PAID_SHEETS,
        'is_enabled': True,
    }

    print('== 配置搬运核对（迁移常量 vs settings 原值）==')
    ok = True
    for key in expected:
        left, right = expected[key], current[key]
        same = left == right
        ok = ok and same
        print(f'  [{"OK " if same else "差异"}] {key}: 迁移={left!r} settings={right!r}')
    print(f'  -> {"完全一致" if ok else "存在差异，请修正迁移常量"}\n')
    return ok


async def table_exists(name: str) -> bool:
    """判断表是否存在"""
    async with async_engine.connect() as conn:
        tables = await conn.run_sync(lambda c: sa.inspect(c).get_table_names())
    return name in tables


async def create_tables() -> list[str]:
    """按 metadata 建表（已存在则跳过），与应用启动口径一致"""
    created: list[str] = []
    async with async_engine.begin() as conn:
        for table in (FeishuSheetConfig.__table__, FeishuSheetTask.__table__):
            exists = await conn.run_sync(lambda c, t=table: sa.inspect(c).has_table(t.name))
            if not exists:
                await conn.run_sync(lambda c, t=table: t.create(c))
                created.append(table.name)
    return created


async def seed_config() -> str:
    """落「公考」配置；已存在则原样保留，不覆盖人工改动"""
    migration = load_migration()
    async with async_db_session.begin() as db:
        stmt = select(FeishuSheetConfig).where(FeishuSheetConfig.name == CONFIG_NAME)
        existing = (await db.execute(stmt)).scalars().first()
        if existing is not None:
            return f'已存在 id={existing.id}，未改动'
        config = FeishuSheetConfig(
            name=migration.GONGKAO_NAME,
            description='公考资源同步到飞书表格（自 plugin.toml 迁移）',
            app_code=migration.GONGKAO_APP_CODE,
            category_type=migration.GONGKAO_CATEGORY_TYPE,
            sheet_url=migration.GONGKAO_SHEET_URL,
            sheet_map=migration.GONGKAO_SHEET_MAP,
            category_options=migration.GONGKAO_CATEGORY_OPTIONS,
            source_weights=migration.GONGKAO_SOURCE_WEIGHTS,
            paid_sheets=migration.GONGKAO_PAID_SHEETS,
            is_enabled=True,
            cron=SEED_CRON,
        )
        db.add(config)
        await db.flush()
        return f'已写入 id={config.id}'


async def report() -> None:
    """打印当前配置表内容"""
    async with async_db_session() as db:
        rows = (await db.execute(select(FeishuSheetConfig).order_by(FeishuSheetConfig.id))).scalars().all()

    print('== feishu_sheet_config ==')
    if not rows:
        print('  （空）')
    for row in rows:
        print(f'  id={row.id} name={row.name} app_code={row.app_code} cron={row.cron!r} enabled={row.is_enabled}')
        print(f'    sheet_url={row.sheet_url}')
        print(f'    sheet_map={row.sheet_map}')
        print(f'    category_options={row.category_options}')
        print(f'    source_weights={row.source_weights} paid_sheets={row.paid_sheets}')
        print(f'    last_synced_at={row.last_synced_at}')

    print('\n== 表存在性 ==')
    for name in ('feishu_sheet_config', 'feishu_sheet_task'):
        print(f'  {name}: {await table_exists(name)}')


async def main() -> int:
    parser = argparse.ArgumentParser(description='飞书表导出配置：建表 + 落种子')
    parser.add_argument('--check', action='store_true', help='只读体检，不建表不写数据')
    args = parser.parse_args()

    consistent = compare_with_migration()

    if args.check:
        await report()
        return 0 if consistent else 1

    created = await create_tables()
    print(f'== 建表 ==\n  {"新建: " + ", ".join(created) if created else "两张表均已存在，跳过"}\n')
    print(f'== 落配置 ==\n  {await seed_config()}\n')
    await report()
    return 0 if consistent else 1


if __name__ == '__main__':
    raise SystemExit(asyncio.run(main()))
