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


SYNC_ROLE_SEQUENCE_SQL = """
SELECT setval(
    pg_get_serial_sequence('fba.sys_role', 'id'),
    COALESCE((SELECT MAX(id) FROM fba.sys_role), 1),
    (SELECT COUNT(*) > 0 FROM fba.sys_role)
);
"""

SYNC_ROLE_MENU_SEQUENCE_SQL = """
SELECT setval(
    pg_get_serial_sequence('fba.sys_role_menu', 'id'),
    COALESCE((SELECT MAX(id) FROM fba.sys_role_menu), 1),
    (SELECT COUNT(*) > 0 FROM fba.sys_role_menu)
);
"""

BIND_STUDY_PLAN_ROLE_SQL = """
DO $$
DECLARE
    study_plan_admin_role_id BIGINT;
    study_plan_mentor_role_id BIGINT;
BEGIN
    INSERT INTO fba.sys_role (name, status, is_filter_scopes, remark, created_time)
    SELECT '学习规划管理员', 1, TRUE, '学习规划管理端全量权限', NOW()
    WHERE NOT EXISTS (
        SELECT 1
        FROM fba.sys_role
        WHERE name = '学习规划管理员'
          AND deleted = 0
    );

    INSERT INTO fba.sys_role (name, status, is_filter_scopes, remark, created_time)
    SELECT '学习规划导师', 1, TRUE, '学习规划导师端计划维护权限', NOW()
    WHERE NOT EXISTS (
        SELECT 1
        FROM fba.sys_role
        WHERE name = '学习规划导师'
          AND deleted = 0
    );

    SELECT id
    INTO study_plan_admin_role_id
    FROM fba.sys_role
    WHERE name = '学习规划管理员'
      AND deleted = 0
    ORDER BY id
    LIMIT 1;

    SELECT id
    INTO study_plan_mentor_role_id
    FROM fba.sys_role
    WHERE name = '学习规划导师'
      AND deleted = 0
    ORDER BY id
    LIMIT 1;

    INSERT INTO fba.sys_role_menu (role_id, menu_id)
    SELECT study_plan_admin_role_id, menu.id
    FROM fba.sys_menu AS menu
    WHERE menu.name IN (
        'StudyPlan',
        'StudyPlanPlan',
        'StudyPlanTemplate',
        'StudyPlanMentor',
        'StudyPlanProgress',
        'StudyPlanAbilityProfile',
        'StudyPlanAbilityCatalog',
        'StudyPlanMentorRead',
        'StudyPlanMentorWrite',
        'StudyPlanTemplateRead',
        'StudyPlanTemplateWrite',
        'StudyPlanMentorAssignRead',
        'StudyPlanMentorAssignWrite',
        'StudyPlanProgressRead',
        'StudyPlanAbilityProfileRead',
        'StudyPlanAbilityCatalogRead',
        'StudyPlanAbilityCatalogWrite'
    )
      AND menu.deleted = 0
      AND NOT EXISTS (
          SELECT 1
          FROM fba.sys_role_menu AS relation
          WHERE relation.role_id = study_plan_admin_role_id
            AND relation.menu_id = menu.id
      );

    INSERT INTO fba.sys_role_menu (role_id, menu_id)
    SELECT study_plan_mentor_role_id, menu.id
    FROM fba.sys_menu AS menu
    WHERE menu.name IN (
        'StudyPlan',
        'StudyPlanPlan',
        'StudyPlanTemplate',
        'StudyPlanProgress',
        'StudyPlanAbilityProfile',
        'StudyPlanMentorRead',
        'StudyPlanMentorWrite',
        'StudyPlanTemplateRead',
        'StudyPlanProgressRead',
        'StudyPlanAbilityProfileRead'
    )
      AND menu.deleted = 0
      AND NOT EXISTS (
          SELECT 1
          FROM fba.sys_role_menu AS relation
          WHERE relation.role_id = study_plan_mentor_role_id
            AND relation.menu_id = menu.id
      );
END $$;
"""

CLEAR_STUDY_PLAN_USER_CACHE_SQL = """
SELECT DISTINCT user_role.user_id
FROM fba.sys_user_role AS user_role
JOIN fba.sys_role AS role ON role.id = user_role.role_id
WHERE role.name IN ('学习规划管理员', '学习规划导师')
  AND role.deleted = 0;
"""

VERIFY_SQL = """
SELECT
    role.id AS role_id,
    role.name AS role_name,
    menu.id AS menu_id,
    menu.name AS menu_name,
    menu.title AS menu_title,
    menu.type AS menu_type,
    menu.perms AS menu_perms
FROM fba.sys_role AS role
LEFT JOIN fba.sys_role_menu AS relation ON relation.role_id = role.id
LEFT JOIN fba.sys_menu AS menu
    ON menu.id = relation.menu_id
   AND menu.deleted = 0
WHERE role.name IN ('学习规划管理员', '学习规划导师')
  AND role.deleted = 0
  AND (
      menu.name IS NULL
      OR menu.name IN (
          'StudyPlan',
          'StudyPlanPlan',
          'StudyPlanTemplate',
          'StudyPlanMentor',
          'StudyPlanProgress',
          'StudyPlanAbilityProfile',
          'StudyPlanAbilityCatalog',
          'StudyPlanMentorRead',
          'StudyPlanMentorWrite',
          'StudyPlanTemplateRead',
          'StudyPlanTemplateWrite',
          'StudyPlanMentorAssignRead',
          'StudyPlanMentorAssignWrite',
          'StudyPlanProgressRead',
          'StudyPlanAbilityProfileRead',
          'StudyPlanAbilityCatalogRead',
          'StudyPlanAbilityCatalogWrite'
      )
  )
ORDER BY role.id, menu.parent_id NULLS FIRST, menu.sort, menu.id;
"""


async def bind_study_plan_roles(db: AsyncSession) -> list[dict[str, object]]:
    """
    绑定学习规划角色菜单

    :param db: 数据库会话
    :return:
    """
    await db.execute(text(SYNC_ROLE_SEQUENCE_SQL))
    await db.execute(text(SYNC_ROLE_MENU_SEQUENCE_SQL))
    await db.execute(text(BIND_STUDY_PLAN_ROLE_SQL))
    await db.execute(text(SYNC_ROLE_SEQUENCE_SQL))
    await db.execute(text(SYNC_ROLE_MENU_SEQUENCE_SQL))
    result = await db.execute(text(VERIFY_SQL))
    return [dict(row._mapping) for row in result.fetchall()]


async def clear_study_plan_user_cache(db: AsyncSession) -> tuple[list[int], str | None]:
    """
    清理学习规划角色用户缓存

    :param db: 数据库会话
    :return:
    """
    from backend.app.admin.utils.cache import user_cache_manager

    result = await db.execute(text(CLEAR_STUDY_PLAN_USER_CACHE_SQL))
    user_ids = [int(user_id) for user_id in result.scalars().all()]
    try:
        await user_cache_manager.clear(user_ids)
    except Exception as e:
        return user_ids, str(e)
    return user_ids, None


async def main() -> int:
    """脚本入口"""
    async with async_db_session.begin() as db:
        rows = await bind_study_plan_roles(db)
        cleared_user_ids, cache_error = await clear_study_plan_user_cache(db)

    role_map: dict[int, dict[str, object]] = {}
    for row in rows:
        role_id = int(row['role_id'])
        role = role_map.setdefault(
            role_id,
            {
                'role_name': row['role_name'],
                'menus': [],
            },
        )
        if row['menu_id'] is not None:
            role['menus'].append(row)

    print(f'[OK] study plan roles={len(role_map)} cleared_user_cache={len(cleared_user_ids)}')
    for role_id, role in role_map.items():
        menus = role['menus']
        print(f'- role_id={role_id} role_name={role["role_name"]} menu_count={len(menus)}')
        for menu in menus:
            print(
                f'  - menu_id={menu["menu_id"]} name={menu["menu_name"]} '
                f'type={menu["menu_type"]} perms={menu["menu_perms"]}'
            )

    if cleared_user_ids:
        print(f'- cleared_user_ids={",".join(str(user_id) for user_id in cleared_user_ids)}')
    if cache_error is not None:
        print(f'[WARN] clear user cache failed: {cache_error}')
    return 0


if __name__ == '__main__':
    raise SystemExit(asyncio.run(main()))
