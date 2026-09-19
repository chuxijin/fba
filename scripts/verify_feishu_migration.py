#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
校验飞书表导出配置的 alembic 迁移脚本（不触碰任何真实表）

做法：在目标库里建一个临时 schema（默认 mig_verify），把 search_path 切过去，
再对迁移模块单独执行 upgrade -> 重复 upgrade -> downgrade，全程断言结构；
结束时整体 ROLLBACK，库中不留任何痕迹。

之所以单独跑：本仓库 alembic 版本链与数据库现状不一致（alembic_version 指向仓库中
不存在的 revision），`alembic upgrade` 无法执行，迁移脚本得不到常规途径的验证。

用法（在仓库根目录）:
    python scripts/verify_feishu_migration.py
"""

from __future__ import annotations

import asyncio
import importlib.util
import sys

from pathlib import Path
from typing import Any

import sqlalchemy as sa

from alembic.migration import MigrationContext
from alembic.operations import Operations

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.mydrive.model.feishu import FeishuSheetConfig, FeishuSheetTask  # noqa: E402
from backend.database.db import async_engine  # noqa: E402

MIGRATION_PATH = (
    ROOT / 'backend' / 'alembic' / 'versions' / '2026-09-19-20_30_00-a7c1e9d2b435_add_feishu_sheet_export_config.py'
)
SCRATCH_SCHEMA = 'mig_verify'

failures: list[str] = []


def check(label: str, condition: bool, detail: str = '') -> None:
    """记录一条断言结果"""
    print(f'  [{"OK " if condition else "FAIL"}] {label}{"" if condition else "  <- " + detail}')
    if not condition:
        failures.append(label)


def load_migration() -> Any:
    """按文件路径加载迁移模块"""
    spec = importlib.util.spec_from_file_location('migration_under_verify', MIGRATION_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f'无法加载迁移文件: {MIGRATION_PATH}')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def table_exists(conn: sa.Connection, name: str) -> bool:
    """
    判断临时 schema 中是否存在指定表

    每次新建 Inspector：`Inspector.has_table` 带缓存，同一实例在 DDL 前后会返回陈旧结果。
    """
    return sa.inspect(conn).has_table(name)


def verify(conn: sa.Connection, migration: Any) -> None:
    """在临时 schema 内执行迁移并断言结果"""
    conn.execute(sa.text(f'DROP SCHEMA IF EXISTS {SCRATCH_SCHEMA} CASCADE'))
    conn.execute(sa.text(f'CREATE SCHEMA {SCRATCH_SCHEMA}'))
    conn.execute(sa.text(f'SET search_path TO {SCRATCH_SCHEMA}'))
    print(f'临时 schema 就绪: {SCRATCH_SCHEMA}')

    inspector = sa.inspect(conn)
    operations = Operations(MigrationContext.configure(conn))
    migration.op = operations  # 迁移模块内是 `from alembic import op`，这里替换为绑定到临时 schema 的实例

    # ---- 1. upgrade ----
    print('\n== 1. upgrade() ==')
    migration.upgrade()
    for name in ('feishu_sheet_config', 'feishu_sheet_task'):
        check(f'表已创建 {name}', table_exists(conn, name))

    config_columns = {col['name'] for col in inspector.get_columns('feishu_sheet_config')}
    expected_columns = {column.name for column in FeishuSheetConfig.__table__.columns}
    check(
        'feishu_sheet_config 列与模型一致',
        config_columns == expected_columns,
        f'迁移={sorted(config_columns)} 模型={sorted(expected_columns)}',
    )

    task_columns = {col['name'] for col in inspector.get_columns('feishu_sheet_task')}
    expected_task_columns = {column.name for column in FeishuSheetTask.__table__.columns}
    check(
        'feishu_sheet_task 列与模型一致',
        task_columns == expected_task_columns,
        f'迁移={sorted(task_columns)} 模型={sorted(expected_task_columns)}',
    )

    config_uniques = {u['name'] for u in inspector.get_unique_constraints('feishu_sheet_config')}
    check('唯一约束 uq_feishu_sheet_config_name', 'uq_feishu_sheet_config_name' in config_uniques, str(config_uniques))

    config_indexes = {i['name'] for i in inspector.get_indexes('feishu_sheet_config')}
    check(
        '索引 idx_feishu_sheet_config_enabled',
        'idx_feishu_sheet_config_enabled' in config_indexes,
        str(config_indexes),
    )

    task_checks = {c['name'] for c in inspector.get_check_constraints('feishu_sheet_task')}
    check('检查约束 ck_feishu_sheet_task_status', 'ck_feishu_sheet_task_status' in task_checks, str(task_checks))

    task_fks = inspector.get_foreign_keys('feishu_sheet_task')
    check(
        '外键 feishu_sheet_task.config_id -> feishu_sheet_config.id',
        any(fk['referred_table'] == 'feishu_sheet_config' for fk in task_fks),
        str(task_fks),
    )

    rows = conn.execute(
        sa.text(f'SELECT id, name, app_code, cron, is_enabled FROM {SCRATCH_SCHEMA}.feishu_sheet_config')
    ).all()
    check('种子数据写入 1 条', len(rows) == 1, str(rows))
    if rows:
        row = rows[0]
        check('种子 name=公考', row[1] == '公考', str(row))
        check('种子 app_code=youanshang', row[2] == 'youanshang', str(row))
        check("种子 cron='0 3 * * *'", row[3] == '0 3 * * *', str(row))
        check('种子 is_enabled=True', row[4] is True, str(row))

    # ---- 2. 重复 upgrade（幂等） ----
    print('\n== 2. 重复 upgrade()（幂等）==')
    try:
        migration.upgrade()
        repeated_ok = True
        error = ''
    except Exception as exc:  # noqa: BLE001
        repeated_ok = False
        error = repr(exc)
    check('重复 upgrade 不报错', repeated_ok, error)
    count = conn.execute(sa.text(f'SELECT count(*) FROM {SCRATCH_SCHEMA}.feishu_sheet_config')).scalar_one()
    check('重复 upgrade 后仍只有 1 条种子', count == 1, f'count={count}')

    # ---- 3. downgrade ----
    print('\n== 3. downgrade() ==')
    migration.downgrade()
    for name in ('feishu_sheet_config', 'feishu_sheet_task'):
        check(f'表已删除 {name}', not table_exists(conn, name))


async def main() -> int:
    migration = load_migration()
    print(f'迁移文件: {MIGRATION_PATH.name}')
    print(f"revision={migration.revision} down_revision={migration.down_revision}\n")

    async with async_engine.connect() as conn:
        transaction = await conn.begin()
        try:
            await conn.run_sync(lambda sync_conn: verify(sync_conn, migration))
        finally:
            await transaction.rollback()
            print('\n已回滚，临时 schema 未落库')

    print('\n== 结论 ==')
    if failures:
        print(f'  {len(failures)} 项未通过: {failures}')
        return 1
    print('  迁移脚本 upgrade / 幂等 / downgrade 全部通过')
    return 0


if __name__ == '__main__':
    raise SystemExit(asyncio.run(main()))
