#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""下架「AI 自动标注」独立页面菜单 —— 功能已融合进「知识点标注」页。

⚠️ **只删页面菜单（type=1），保留两个权限点（type=2）**：
融合后知识点标注页要调 `/autolabels/decision-models`、`/autolabels/candidates`、
`POST /autolabels`，全靠 `qbank_v2:autolabel:read` / `write` 这两个权限。
一并删掉会让融合后的 AI 建议直接 403。type=2 是按钮权限，本来就不渲染成菜单项，
保留它对用户界面零影响。

删除语义与 `menu_dao.delete(logical_deletion=True)` 一致：
  - `sys_menu`         → 逻辑删除，`deleted` 置时间戳（可回滚）
  - `sys_role_menu`    → 物理删除（与后端 dao 行为一致）

用法：
    python -m scripts.seed.remove_ai_autolabel_menu            # 干跑
    python -m scripts.seed.remove_ai_autolabel_menu --write     # 真删

⚠️ schema 差异：生产库在 `fba` 下，dev 库（100.80.0.126）只有 `public`。
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

PAGE_MENU_NAME = 'QbankV2AiAutolabel'
# ⚠️ 这两个必须保留，否则融合后的 AI 建议接口 403
KEEP_PERM_NAMES = ('QbankV2AiAutolabelRead', 'QbankV2AiAutolabelWrite')

DETECT_SCHEMA_SQL = """
SELECT COALESCE(
    (SELECT nspname FROM pg_class c
       JOIN pg_namespace n ON n.oid = c.relnamespace
      WHERE c.relname = 'sys_menu' AND c.relkind = 'r'
        AND n.nspname IN ('fba', 'public')
      ORDER BY (n.nspname = 'fba') DESC
      LIMIT 1),
    'public'
) AS schema;
"""

DETECT_RM_DELETED_SQL = """
SELECT COUNT(*) > 0
FROM information_schema.columns
WHERE table_schema = :schema AND table_name = 'sys_role_menu' AND column_name = 'deleted';
"""

# 干跑/执行都先看清现状
PREVIEW_SQL = """
SELECT id, title, name, type, perms, deleted
FROM {schema}.sys_menu
WHERE name = CAST(:page AS VARCHAR) OR name IN ('QbankV2AiAutolabelRead', 'QbankV2AiAutolabelWrite')
ORDER BY type, id;
"""

# 先删角色绑定（物理删，与 dao 一致），再逻辑删菜单
DELETE_ROLE_MENU_SQL = """
DELETE FROM {schema}.sys_role_menu
WHERE menu_id = (SELECT id FROM {schema}.sys_menu
                 WHERE name = CAST(:page AS VARCHAR) AND deleted = 0);
"""

SOFT_DELETE_MENU_SQL = """
UPDATE {schema}.sys_menu
SET deleted = EXTRACT(EPOCH FROM NOW())::BIGINT,
    deleted_time = NOW()
WHERE name = CAST(:page AS VARCHAR) AND deleted = 0;
"""


async def remove(db: AsyncSession, *, write: bool) -> None:
    schema = str(
        (
            await db.execute(text(DETECT_SCHEMA_SQL))
        ).scalar()
        or 'public'
    )
    rm_has_deleted = bool(
        (
            await db.execute(
                text(DETECT_RM_DELETED_SQL), {'schema': schema}
            )
        ).scalar()
    )
    print(f'[i] schema={schema}，sys_role_menu 有 deleted 列={rm_has_deleted}')

    before = (
        await db.execute(text(PREVIEW_SQL.format(schema=schema)), {'page': PAGE_MENU_NAME})
    ).fetchall()
    print('[i] 当前状态：')
    for r in before:
        flag = '  <-- 将逻辑删除' if r[2] == PAGE_MENU_NAME and r[5] == 0 else ''
        keep = '  <-- 保留（AI 建议接口权限）' if r[2] in KEEP_PERM_NAMES else ''
        print(f'    id={r[0]} type={r[3]} {r[1]} name={r[2]} deleted={r[5]}{flag}{keep}')

    targets = [r for r in before if r[2] == PAGE_MENU_NAME and r[5] == 0]
    if not targets:
        print('[i] 页面菜单已是删除态（或不存在），无需操作')
        return

    if not write:
        print('[i] --write 未加，只干跑')
        return

    n_rm = await db.execute(
        text(DELETE_ROLE_MENU_SQL.format(schema=schema)), {'page': PAGE_MENU_NAME}
    )
    print(f'[i] 清理 sys_role_menu：{n_rm.rowcount} 行')

    n_menu = await db.execute(
        text(SOFT_DELETE_MENU_SQL.format(schema=schema)), {'page': PAGE_MENU_NAME}
    )
    print(f'[i] 逻辑删除 sys_menu：{n_menu.rowcount} 行')

    # ⚠️ 保留的两个权限点也要确保没绑到任何角色，否则是脏数据
    kept = (
        await db.execute(text(PREVIEW_SQL.format(schema=schema)), {'page': PAGE_MENU_NAME})
    ).fetchall()
    print('[i] 处理后状态：')
    for r in kept:
        print(f'    id={r[0]} type={r[3]} {r[1]} name={r[2]} deleted={r[5]}')


async def main() -> int:
    write = '--write' in sys.argv
    print(f'[i] 模式：{"干跑（默认）" if not write else "写入（--write）"}')
    async with async_db_session.begin() as db:
        await remove(db, write=write)
    return 0


if __name__ == '__main__':
    raise SystemExit(asyncio.run(main()))
