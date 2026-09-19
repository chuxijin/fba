#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""录入「我的网盘 / 飞书表导出」后台菜单（幂等）

背景：前端菜单是「文件路由」+「数据库菜单」并存的模式。
`frontend/apps/web-antdv-next/src/router/routes/modules/mydrive.ts` 里已有
静态路由，但若 `sys_menu` 中没有对应记录，菜单在后端驱动的侧边栏里不会出现，
且角色也无法被授权。本脚本为既有目录补一条子菜单记录。

用法（在 backend 目录或仓库根均可）：
    ../.venv/Scripts/python.exe -m scripts.insert_feishu_sheets_menu
"""
from __future__ import annotations

import asyncio
import sys

from pathlib import Path

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.database.db import async_db_session  # noqa: E402


MENU_NAME = 'MyDriveFeishuSheets'
MENU_TITLE = '飞书表导出'
MENU_PATH = '/mydrive/feishu-sheets'
MENU_ICON = 'mdi:table-arrow-right'

SYNC_MENU_SEQUENCE_SQL = """
SELECT setval(
    pg_get_serial_sequence('sys_menu', 'id'),
    COALESCE((SELECT MAX(id) FROM sys_menu), 1),
    (SELECT COUNT(*) > 0 FROM sys_menu)
);
"""

# 父级优先找已有「我的网盘」目录；找不到就在 sys_menu 里补一个目录节点。
INSERT_FEISHU_SHEETS_MENU_SQL = """
DO $$
DECLARE
    parent_menu_id BIGINT;
BEGIN
    SELECT id
    INTO parent_menu_id
    FROM sys_menu
    WHERE name = 'MyDrive'
      AND deleted = 0
    ORDER BY id
    LIMIT 1;

    IF parent_menu_id IS NULL THEN
        INSERT INTO sys_menu (
            title, name, path, sort, icon, type, component,
            perms, status, display, cache, link, remark, parent_id, created_time
        ) VALUES (
            '我的网盘', 'MyDrive', '/mydrive', 2, 'mdi:cloud-outline', 0, NULL,
            NULL, 1, 1, 1, '', '我的网盘', NULL, NOW()
        )
        RETURNING id INTO parent_menu_id;
    END IF;

    INSERT INTO sys_menu (
        title, name, path, sort, icon, type, component,
        perms, status, display, cache, link, remark, parent_id, created_time
    )
    SELECT
        '飞书表导出', 'MyDriveFeishuSheets', '/mydrive/feishu-sheets', 5,
        'mdi:table-arrow-right', 1, '/mydrive/feishu-sheets/index',
        NULL, 1, 1, 1, '', '飞书表导出配置与执行记录', parent_menu_id, NOW()
    WHERE NOT EXISTS (
        SELECT 1
        FROM sys_menu
        WHERE name = 'MyDriveFeishuSheets'
          AND deleted = 0
    );
END $$;
"""

VERIFY_SQL = """
SELECT id, title, name, path, type, component, parent_id
FROM sys_menu
WHERE name IN ('MyDrive', 'MyDriveFeishuSheets')
  AND deleted = 0
ORDER BY parent_id NULLS FIRST, sort, id;
"""


async def insert_feishu_sheets_menu(db: AsyncSession) -> list[dict[str, object]]:
    """录入飞书表导出后台菜单"""
    await db.execute(text(SYNC_MENU_SEQUENCE_SQL))
    await db.execute(text(INSERT_FEISHU_SHEETS_MENU_SQL))
    await db.execute(text(SYNC_MENU_SEQUENCE_SQL))
    result = await db.execute(text(VERIFY_SQL))
    return [dict(row._mapping) for row in result.fetchall()]


async def main() -> int:
    """脚本入口"""
    async with async_db_session.begin() as db:
        rows = await insert_feishu_sheets_menu(db)

    print(f'[OK] feishu sheets menu rows={len(rows)}')
    for row in rows:
        print(
            f'- id={row["id"]} title={row["title"]} name={row["name"]} '
            f'type={row["type"]} path={row["path"]} '
            f'component={row["component"]} parent_id={row["parent_id"]}'
        )
    return 0


if __name__ == '__main__':
    raise SystemExit(asyncio.run(main()))
