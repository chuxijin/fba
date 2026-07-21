#!/usr/bin/env python3
# -*- coding: utf-8 -*-
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


SYNC_MENU_SEQUENCE_SQL = """
SELECT setval(
    pg_get_serial_sequence('sys_menu', 'id'),
    COALESCE((SELECT MAX(id) FROM sys_menu), 1),
    (SELECT COUNT(*) > 0 FROM sys_menu)
);
"""

INSERT_STUDY_HANDBOOK_MENU_SQL = """
DO $$
DECLARE
    gongkao_menu_id BIGINT;
BEGIN
    SELECT id
    INTO gongkao_menu_id
    FROM sys_menu
    WHERE name = 'Gongkao'
      AND deleted = 0
    ORDER BY id
    LIMIT 1;

    IF gongkao_menu_id IS NULL THEN
        INSERT INTO sys_menu (
            title, name, path, sort, icon, type, component,
            perms, status, display, cache, link, remark, parent_id, created_time
        ) VALUES (
            '公考管理', 'Gongkao', '/gongkao', 10, 'mdi:school-outline', 0, NULL,
            NULL, 1, 1, 1, '', '公考管理', NULL, NOW()
        )
        RETURNING id INTO gongkao_menu_id;
    END IF;

    INSERT INTO sys_menu (
        title, name, path, sort, icon, type, component,
        perms, status, display, cache, link, remark, parent_id, created_time
    )
    SELECT
        '学习手册', 'GongkaoHandbook', '/gongkao/handbook', 9,
        'mdi:book-open-page-variant-outline', 1, '/gongkao/handbook',
        'sys:category:edit', 1, 1, 1, '', '学习手册分类与 Halo 文档关联管理', gongkao_menu_id, NOW()
    WHERE NOT EXISTS (
        SELECT 1
        FROM sys_menu
        WHERE name = 'GongkaoHandbook'
          AND deleted = 0
    );
END $$;
"""

VERIFY_SQL = """
SELECT id, title, name, path, type, perms, parent_id
FROM sys_menu
WHERE name IN ('Gongkao', 'GongkaoHandbook')
  AND deleted = 0
ORDER BY parent_id NULLS FIRST, sort, id;
"""


async def insert_study_handbook_menu(db: AsyncSession) -> list[dict[str, object]]:
    """录入学习手册后台菜单"""
    await db.execute(text(SYNC_MENU_SEQUENCE_SQL))
    await db.execute(text(INSERT_STUDY_HANDBOOK_MENU_SQL))
    await db.execute(text(SYNC_MENU_SEQUENCE_SQL))
    result = await db.execute(text(VERIFY_SQL))
    return [dict(row._mapping) for row in result.fetchall()]


async def main() -> int:
    """脚本入口"""
    async with async_db_session.begin() as db:
        rows = await insert_study_handbook_menu(db)

    print(f'[OK] study handbook menu rows={len(rows)}')
    for row in rows:
        print(
            f'- id={row["id"]} title={row["title"]} name={row["name"]} '
            f'type={row["type"]} parent_id={row["parent_id"]} perms={row["perms"]}'
        )
    return 0


if __name__ == '__main__':
    raise SystemExit(asyncio.run(main()))
