#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""录入「AI 自动标注」后台菜单（挂在 qbank-v2 → 标注管理 下）。

幂等：全部用 `WHERE NOT EXISTS`，重复跑不会插重复行。
连哪台库由 backend/.env 决定；pydantic-settings 下环境变量优先于 .env。

⚠️ **schema 差异**：生产库 `sys_menu` 在 `fba` schema 下，dev 库（100.80.0.126）
只有 `public` schema 且表名不带前缀。下面用 `format('{schema}.sys_menu')` 动态拼，
启动时按 `to_regclass` 探测哪个存在，避免在 dev 库上直接报
`relation "{schema}.sys_menu" does not exist`。
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
    pg_get_serial_sequence('{schema}.sys_menu', 'id'),
    COALESCE((SELECT MAX(id) FROM {schema}.sys_menu), 1),
    (SELECT COUNT(*) > 0 FROM {schema}.sys_menu)
);
"""

INSERT_AI_AUTOLABEL_MENU_SQL = """
DO $$
DECLARE
    annotation_menu_id BIGINT;
BEGIN
    -- 标注管理目录（qbank-v2 的子目录，已存在则复用）
    SELECT id INTO annotation_menu_id
    FROM {schema}.sys_menu
    WHERE name = 'QbankV2Annotation' AND deleted = 0
    ORDER BY id
    LIMIT 1;

    IF annotation_menu_id IS NULL THEN
        RAISE EXCEPTION '找不到「标注管理」目录（QbankV2Annotation），请先初始化 qbank-v2 菜单';
    END IF;

    -- 页面菜单：name 必须与前端静态路由 name 完全一致，否则点得进但页面空白
    INSERT INTO {schema}.sys_menu (
        title, name, path, sort, icon, type, component,
        perms, status, display, cache, link, remark, parent_id, created_time
    )
    SELECT
        'AI 自动标注', 'QbankV2AiAutolabel', '/qbank-v2/annotation/ai-autolabel', 3,
        'mdi:auto-fix', 1, '/qbank-v2/annotation/ai-autolabel/index',
        'qbank_v2:autolabel:read', 1, 1, 1, '', 'AI 批量标注知识点', annotation_menu_id, NOW()
    WHERE NOT EXISTS (
        SELECT 1 FROM {schema}.sys_menu WHERE name = 'QbankV2AiAutolabel' AND deleted = 0
    );

    -- 两个权限点
    INSERT INTO {schema}.sys_menu (
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
        SELECT 1 FROM {schema}.sys_menu AS e WHERE e.name = m.name AND e.deleted = 0
    );
END $$;
"""

# 角色授权：默认绑给下面这些角色，用环境变量 AUTOLABEL_ROLES 覆盖（逗号分隔角色名）
# ⚠️ 生产库实测：**没有任何角色绑过 qbank-v2 菜单**（qbank/gongkao 相关绑定数为 0），
# 说明超管走的是通配逻辑。所以这里只绑给明确的管理角色，别绑到普通用户角色上。
# ⚠️ **dev 库 `sys_role_menu` 只有 (id, role_id, menu_id)，没有 `deleted` 列**（生产库有），
# 且 dev 的 qbank-v2 菜单绑给 `基础角色`(id=1) —— 那里 admin 才是超管。所以 deleted 列动态拼。
GRANT_ROLES_SQL = """
INSERT INTO {schema}.sys_role_menu (role_id, menu_id{deleted_col})
SELECT r.id, m.id{deleted_val}
FROM {schema}.sys_menu m
CROSS JOIN {schema}.sys_role r
WHERE m.name IN (
        'QbankV2AiAutolabel',
        'QbankV2AiAutolabelRead',
        'QbankV2AiAutolabelWrite'
    )
  AND m.deleted = 0
  AND r.deleted = 0
  AND r.name = ANY(string_to_array(:roles, ','))
  AND NOT EXISTS (
      SELECT 1 FROM {schema}.sys_role_menu e
      WHERE e.role_id = r.id AND e.menu_id = m.id{deleted_where}
  );
"""

# 探测 sys_role_menu 是否含 deleted 列（dev 库没有）
DETECT_RM_DELETED_SQL = """
SELECT COUNT(*) > 0
FROM information_schema.columns
WHERE table_schema = :schema AND table_name = 'sys_role_menu' AND column_name = 'deleted';
"""

VERIFY_SQL = """
SELECT id, title, name, path, type, perms, parent_id
FROM {schema}.sys_menu
WHERE name IN (
    'QbankV2AiAutolabel',
    'QbankV2AiAutolabelRead',
    'QbankV2AiAutolabelWrite'
)
ORDER BY type, sort, id;
"""


# 探测 sys_menu 到底在哪个 schema：生产库在 fba 下，dev 库只有 public
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


async def detect_schema(db: AsyncSession) -> str:
    """返回 sys_menu 所在 schema 名。生产库='fba'，dev 库='public'。"""
    result = await db.execute(text(DETECT_SCHEMA_SQL))
    return str(result.scalar() or 'public')


async def insert_ai_autolabel_menu(
    db: AsyncSession, *, roles: str
) -> list[dict[str, object]]:
    """录入菜单并绑角色，返回校验结果。"""
    schema = await detect_schema(db)
    rm_has_deleted = bool(
        (
            await db.execute(
                text(DETECT_RM_DELETED_SQL), {'schema': schema}
            )
        ).scalar()
    )
    grant_fmt = {
        'schema': schema,
        'deleted_col': ', deleted' if rm_has_deleted else '',
        'deleted_val': ', 0' if rm_has_deleted else '',
        'deleted_where': ' AND e.deleted = 0' if rm_has_deleted else '',
    }
    print(
        f'[i] sys_menu schema={schema}，'
        f'sys_role_menu 有 deleted 列={rm_has_deleted}'
    )

    await db.execute(text(SYNC_MENU_SEQUENCE_SQL.format(schema=schema)))
    await db.execute(text(INSERT_AI_AUTOLABEL_MENU_SQL.format(schema=schema)))
    await db.execute(text(SYNC_MENU_SEQUENCE_SQL.format(schema=schema)))
    await db.execute(text(GRANT_ROLES_SQL.format(**grant_fmt)), {'roles': roles})
    result = await db.execute(text(VERIFY_SQL.format(schema=schema)))
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
