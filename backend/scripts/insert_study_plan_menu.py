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


INSERT_STUDY_PLAN_MENU_SQL = """
DO $$
DECLARE
    study_plan_menu_id BIGINT;
    plan_menu_id BIGINT;
    template_menu_id BIGINT;
    mentor_menu_id BIGINT;
    progress_menu_id BIGINT;
    ability_profile_menu_id BIGINT;
    ability_catalog_menu_id BIGINT;
BEGIN
    INSERT INTO fba.sys_menu (
        title, name, path, sort, icon, type, component,
        perms, status, display, cache, link, remark, parent_id, created_time
    )
    SELECT
        '学习规划', 'StudyPlan', '/study-plan', 11, 'mdi:calendar-check-outline', 0, NULL,
        NULL, 1, 1, 1, '', '学习规划管理', NULL, NOW()
    WHERE NOT EXISTS (
        SELECT 1 FROM fba.sys_menu WHERE name = 'StudyPlan' AND deleted = 0
    );

    SELECT id
    INTO study_plan_menu_id
    FROM fba.sys_menu
    WHERE name = 'StudyPlan'
      AND deleted = 0
    ORDER BY id
    LIMIT 1;

    INSERT INTO fba.sys_menu (
        title, name, path, sort, icon, type, component,
        perms, status, display, cache, link, remark, parent_id, created_time
    )
    SELECT
        '计划管理', 'StudyPlanPlan', '/study-plan/plans', 1, 'mdi:clipboard-list-outline', 1,
        '/study-plan/plan/index', 'study_plan:mentor:read', 1, 1, 1, '', '学习计划管理',
        study_plan_menu_id, NOW()
    WHERE NOT EXISTS (
        SELECT 1 FROM fba.sys_menu WHERE name = 'StudyPlanPlan' AND deleted = 0
    );

    SELECT id
    INTO plan_menu_id
    FROM fba.sys_menu
    WHERE name = 'StudyPlanPlan'
      AND deleted = 0
    ORDER BY id
    LIMIT 1;

    INSERT INTO fba.sys_menu (
        title, name, path, sort, icon, type, component,
        perms, status, display, cache, link, remark, parent_id, created_time
    )
    SELECT
        '模板管理', 'StudyPlanTemplate', '/study-plan/templates', 2, 'mdi:file-document-multiple-outline', 1,
        '/study-plan/template/index', 'study_plan:admin:read', 1, 1, 1, '', '学习计划模板管理',
        study_plan_menu_id, NOW()
    WHERE NOT EXISTS (
        SELECT 1 FROM fba.sys_menu WHERE name = 'StudyPlanTemplate' AND deleted = 0
    );

    SELECT id
    INTO template_menu_id
    FROM fba.sys_menu
    WHERE name = 'StudyPlanTemplate'
      AND deleted = 0
    ORDER BY id
    LIMIT 1;

    INSERT INTO fba.sys_menu (
        title, name, path, sort, icon, type, component,
        perms, status, display, cache, link, remark, parent_id, created_time
    )
    SELECT
        '导师分配', 'StudyPlanMentor', '/study-plan/mentors', 3, 'mdi:account-multiple-check-outline', 1,
        '/study-plan/mentor/index', 'study_plan:admin:read', 1, 1, 1, '', '导师学员分配管理',
        study_plan_menu_id, NOW()
    WHERE NOT EXISTS (
        SELECT 1 FROM fba.sys_menu WHERE name = 'StudyPlanMentor' AND deleted = 0
    );

    SELECT id
    INTO mentor_menu_id
    FROM fba.sys_menu
    WHERE name = 'StudyPlanMentor'
      AND deleted = 0
    ORDER BY id
    LIMIT 1;

    INSERT INTO fba.sys_menu (
        title, name, path, sort, icon, type, component,
        perms, status, display, cache, link, remark, parent_id, created_time
    )
    SELECT
        '进度查看', 'StudyPlanProgress', '/study-plan/progress', 4, 'mdi:chart-donut', 1,
        '/study-plan/progress/index', 'study_plan:mentor:read', 1, 1, 1, '', '学员计划进度查看',
        study_plan_menu_id, NOW()
    WHERE NOT EXISTS (
        SELECT 1 FROM fba.sys_menu WHERE name = 'StudyPlanProgress' AND deleted = 0
    );

    SELECT id
    INTO progress_menu_id
    FROM fba.sys_menu
    WHERE name = 'StudyPlanProgress'
      AND deleted = 0
    ORDER BY id
    LIMIT 1;

    INSERT INTO fba.sys_menu (
        title, name, path, sort, icon, type, component,
        perms, status, display, cache, link, remark, parent_id, created_time
    )
    SELECT
        '能力画像', 'StudyPlanAbilityProfile', '/study-plan/ability-profile', 5,
        'mdi:account-school-outline', 1,
        '/study-plan/ability-profile/index', 'study_plan:mentor:read', 1, 1, 1, '', '学员能力画像查看',
        study_plan_menu_id, NOW()
    WHERE NOT EXISTS (
        SELECT 1 FROM fba.sys_menu WHERE name = 'StudyPlanAbilityProfile' AND deleted = 0
    );

    SELECT id
    INTO ability_profile_menu_id
    FROM fba.sys_menu
    WHERE name = 'StudyPlanAbilityProfile'
      AND deleted = 0
    ORDER BY id
    LIMIT 1;

    INSERT INTO fba.sys_menu (
        title, name, path, sort, icon, type, component,
        perms, status, display, cache, link, remark, parent_id, created_time
    )
    SELECT
        '能力运营', 'StudyPlanAbilityCatalog', '/study-plan/ability-catalog', 6,
        'mdi:vector-link', 1,
        '/study-plan/ability-catalog/index', 'study_plan:admin:read', 1, 1, 1, '', '能力目录与分类绑定运营',
        study_plan_menu_id, NOW()
    WHERE NOT EXISTS (
        SELECT 1 FROM fba.sys_menu WHERE name = 'StudyPlanAbilityCatalog' AND deleted = 0
    );

    SELECT id
    INTO ability_catalog_menu_id
    FROM fba.sys_menu
    WHERE name = 'StudyPlanAbilityCatalog'
      AND deleted = 0
    ORDER BY id
    LIMIT 1;

    INSERT INTO fba.sys_menu (
        title, name, path, sort, icon, type, component,
        perms, status, display, cache, link, remark, parent_id, created_time
    )
    SELECT
        menu.title,
        menu.name,
        menu.path,
        menu.sort,
        menu.icon,
        menu.type,
        menu.component,
        menu.perms,
        menu.status,
        menu.display,
        menu.cache,
        menu.link,
        menu.remark,
        menu.parent_id,
        NOW()
    FROM (VALUES
        ('导师读', 'StudyPlanMentorRead', NULL, 1, NULL, 2, NULL, 'study_plan:mentor:read', 1, 0, 1, '',
         '导师端读取权限', plan_menu_id),
        ('导师写', 'StudyPlanMentorWrite', NULL, 2, NULL, 2, NULL, 'study_plan:mentor:write', 1, 0, 1, '',
         '导师端写入权限', plan_menu_id),
        ('模板读', 'StudyPlanTemplateRead', NULL, 1, NULL, 2, NULL, 'study_plan:admin:read', 1, 0, 1, '',
         '学习规划管理端读取权限', template_menu_id),
        ('模板写', 'StudyPlanTemplateWrite', NULL, 2, NULL, 2, NULL, 'study_plan:admin:write', 1, 0, 1, '',
         '学习规划管理端写入权限', template_menu_id),
        ('分配读', 'StudyPlanMentorAssignRead', NULL, 1, NULL, 2, NULL, 'study_plan:admin:read', 1, 0, 1, '',
         '导师分配读取权限', mentor_menu_id),
        ('分配写', 'StudyPlanMentorAssignWrite', NULL, 2, NULL, 2, NULL, 'study_plan:admin:write', 1, 0, 1, '',
         '导师分配写入权限', mentor_menu_id),
        ('进度读', 'StudyPlanProgressRead', NULL, 1, NULL, 2, NULL, 'study_plan:mentor:read', 1, 0, 1, '',
         '计划进度读取权限', progress_menu_id),
        ('画像读', 'StudyPlanAbilityProfileRead', NULL, 1, NULL, 2, NULL, 'study_plan:mentor:read', 1, 0, 1, '',
         '能力画像读取权限', ability_profile_menu_id),
        ('运营读', 'StudyPlanAbilityCatalogRead', NULL, 1, NULL, 2, NULL, 'study_plan:admin:read', 1, 0, 1, '',
         '能力运营读取权限', ability_catalog_menu_id),
        ('运营写', 'StudyPlanAbilityCatalogWrite', NULL, 2, NULL, 2, NULL, 'study_plan:admin:write', 1, 0, 1, '',
         '能力运营写入权限', ability_catalog_menu_id)
    ) AS menu(
        title, name, path, sort, icon, type, component,
        perms, status, display, cache, link, remark, parent_id
    )
    WHERE NOT EXISTS (
        SELECT 1
        FROM fba.sys_menu AS existing
        WHERE existing.name = menu.name
          AND existing.deleted = 0
    );
END $$;
"""

SYNC_MENU_SEQUENCE_SQL = """
SELECT setval(
    pg_get_serial_sequence('fba.sys_menu', 'id'),
    COALESCE((SELECT MAX(id) FROM fba.sys_menu), 1),
    (SELECT COUNT(*) > 0 FROM fba.sys_menu)
);
"""

VERIFY_SQL = """
SELECT id, title, name, path, type, perms, parent_id
FROM fba.sys_menu
WHERE name IN (
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
ORDER BY parent_id NULLS FIRST, sort, id;
"""


async def insert_study_plan_menu(db: AsyncSession) -> list[dict[str, object]]:
    """
    录入学习规划后台菜单

    :param db: 数据库会话
    :return:
    """
    await db.execute(text(SYNC_MENU_SEQUENCE_SQL))
    await db.execute(text(INSERT_STUDY_PLAN_MENU_SQL))
    await db.execute(text(SYNC_MENU_SEQUENCE_SQL))
    result = await db.execute(text(VERIFY_SQL))
    return [dict(row._mapping) for row in result.fetchall()]


async def main() -> int:
    """脚本入口"""
    async with async_db_session.begin() as db:
        rows = await insert_study_plan_menu(db)

    print(f'[OK] study plan menu rows={len(rows)}')
    for row in rows:
        print(
            f'- id={row["id"]} title={row["title"]} name={row["name"]} '
            f'type={row["type"]} parent_id={row["parent_id"]} perms={row["perms"]}'
        )
    return 0


if __name__ == '__main__':
    raise SystemExit(asyncio.run(main()))
