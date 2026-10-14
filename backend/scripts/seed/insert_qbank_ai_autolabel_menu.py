#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""录入「AI 自动标注」后台菜单（挂在 qbank-v2 → 标注管理 下）。

幂等：全部用 `WHERE NOT EXISTS`，重复跑不会插重复行。
连哪台库由 backend/.env 决定；pydantic-settings 下环境变量优先于 .env。
"""

from __future__ import annotations

import asyncio
import os
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

SYNC_MENU_SEQUENCE_SQL = """
SELECT setval(
    pg_get_serial_sequence('fba.sys_menu', 'id'),
    COALESCE((SELECT MAX(id) FROM fba.sys_menu), 1),
    (SELECT COUNT(*) > 0 FROM fba.sys_menu)
);
"""

INSERT_AI_AUTOLABEL_MENU_SQL = """
DO $$
DECLARE
    annotation_menu_id BIGINT;
BEGIN
    -- 标注管理目录（qbank-v2 的子目录，已存在则复用）
    SELECT id INTO annotation_menu_id
    FROM fba.sys_menu
    WHERE name = 'QbankV2Annotation' AND deleted = 0
    ORDER BY id
    LIMIT 1;

    IF annotation_menu_id IS NULL THEN
        RAISE EXCEPTION '找不到「标注管理」目录（QbankV2Annotation），请先初始化 qbank-v2 菜单';
    END IF;

    -- 页面菜单：name 必须与前端静态路由 name 完全一致，否则点得进但页面空白
    INSERT INTO fba.sys_menu (
        title, name, path, sort, icon, type, component,
        perms, status, display, cache, link, remark, parent_id, created_time
    )
    SELECT
        'AI 自动标注', 'QbankV2AiAutolabel', '/qbank-v2/annotation/ai-autolabel', 3,
        'mdi:auto-fix', 1, '/qbank-v2/annotation/ai-autolabel/index',
        'qbank_v2:autolabel:read', 1, 1, 1, '', 'AI 批量标注知识点', annotation_menu_id, NOW()
    WHERE NOT EXISTS (
        SELECT 1 FROM fba.sys_menu WHERE name = 'QbankV2AiAutolabel' AND deleted = 0
    );

    -- 两个权限点
    INSERT INTO fba.sys_menu (
        title, name, path, sort, icon, type, component,
        perms, status, display, cache, link, remark, parent_id, created_time
    )
    SELECT
        m.title, m.name, NULL, m.sort, NULL, 2, NULL,
        m.perms, 1, 0, 1, '', m.remark, annotation_menu_id, NOW()
    FROM (VALUES
        ('查看自动标注', 'QbankV2AiAutolabelRead', 1,
         'qbank_v2:autolabel:read', '查看候选知识点与预览命中数'),
        ('执行自动标注', 'QbankV2AiAutolabelWrite', 2,
         'qbank_v2:autolabel:write', '执行 AI 标注（会写库）')
    ) AS m(title, name, sort, perms, remark)
    WHERE NOT EXISTS (
        SELECT 1 FROM fba.sys_menu AS e WHERE e.name = m.name AND e.deleted = 0
    );
END $$;
"""

# 角色授权：默认绑给下面这些角色，用环境变量 AUTOLABEL_ROLES 覆盖（逗号分隔角色名）
# ⚠️ 生产库实测：**没有任何角色绑过 qbank-v2 菜单**（qbank/gongkao 相关绑定数为 0），
# 说明超管走的是通配逻辑。所以这里只绑给明确的管理角色，别绑到普通用户角色上。
GRANT_ROLES_SQL = """
INSERT INTO fba.sys_role_menu (role_id, menu_id, deleted)
SELECT r.id, m.id, 0
FROM fba.sys_menu m
CROSS JOIN fba.sys_role r
WHERE m.name IN (
        'QbankV2AiAutolabel',
        'QbankV2AiAutolabelRead',
        'QbankV2AiAutolabelWrite'
    )
  AND m.deleted = 0
  AND r.deleted = 0
  AND r.name = ANY(string_to_array(:roles, ','))
  AND NOT EXISTS (
      SELECT 1 FROM fba.sys_role_menu e
      WHERE e.role_id = r.id AND e.menu_id = m.id AND e.deleted = 0
  );
"""

VERIFY_SQL = """
SELECT id, title, name, path, type, perms, parent_id
FROM fba.sys_menu
WHERE name IN (
    'QbankV2AiAutolabel',
    'QbankV2AiAutolabelRead',
    'QbankV2AiAutolabelWrite'
)
ORDER BY type, sort, id;
"""


async def insert_ai_autolabel_menu(
    db: AsyncSession, *, roles: str
) -> list[dict[str, object]]:
    """录入菜单并绑角色，返回校验结果。"""
    await db.execute(text(SYNC_MENU_SEQUENCE_SQL))
    await db.execute(text(INSERT_AI_AUTOLABEL_MENU_SQL))
    await db.execute(text(SYNC_MENU_SEQUENCE_SQL))
    await db.execute(text(GRANT_ROLES_SQL), {'roles': roles})
    result = await db.execute(text(VERIFY_SQL))
    return [dict(row._mapping) for row in result.fetchall()]


async def main() -> int:
    roles = os.getenv('AUTOLABEL_ROLES', '有岸上SVIP')
    print(f'[i] 绑定的角色：{roles}')
    async with async_db_session.begin() as db:
        rows = await insert_ai_autolabel_menu(db, roles=roles)

    print(f'[OK] AI 自动标注菜单 rows={len(rows)}')
    for row in rows:
        print(
            f'- id={row["id"]} title={row["title"]} name={row["name"]} '
            f'type={row["type"]} perms={row["perms"]}'
        )
    return 0


if __name__ == '__main__':
    raise SystemExit(asyncio.run(main()))
