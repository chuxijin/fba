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
    pg_get_serial_sequence('fba.sys_menu', 'id'),
    COALESCE((SELECT MAX(id) FROM fba.sys_menu), 1),
    (SELECT COUNT(*) > 0 FROM fba.sys_menu)
);
"""

INSERT_QUESTION_GENERATION_MENU_SQL = """
DO $$
DECLARE
    gongkao_menu_id BIGINT;
    question_generation_menu_id BIGINT;
BEGIN
    INSERT INTO fba.sys_menu (
        title, name, path, sort, icon, type, component,
        perms, status, display, cache, link, remark, parent_id, created_time
    )
    SELECT
        '公考管理', 'Gongkao', '/gongkao', 10, 'mdi:school-outline', 0, NULL,
        NULL, 1, 1, 1, '', '公考管理', NULL, NOW()
    WHERE NOT EXISTS (
        SELECT 1 FROM fba.sys_menu WHERE name = 'Gongkao' AND deleted = 0
    );

    SELECT id
    INTO gongkao_menu_id
    FROM fba.sys_menu
    WHERE name = 'Gongkao'
      AND deleted = 0
    ORDER BY id
    LIMIT 1;

    INSERT INTO fba.sys_menu (
        title, name, path, sort, icon, type, component,
        perms, status, display, cache, link, remark, parent_id, created_time
    )
    SELECT
        'AI 出题管理', 'GongkaoQuestionGeneration', '/gongkao/question-generation', 8,
        'mdi:creation-outline', 1, '/gongkao/question-generation/index',
        'question_generation:material:read', 1, 1, 1, '', '国考言语 AI 出题管理',
        gongkao_menu_id, NOW()
    WHERE NOT EXISTS (
        SELECT 1
        FROM fba.sys_menu
        WHERE name = 'GongkaoQuestionGeneration'
          AND deleted = 0
    );

    SELECT id
    INTO question_generation_menu_id
    FROM fba.sys_menu
    WHERE name = 'GongkaoQuestionGeneration'
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
        question_generation_menu_id,
        NOW()
    FROM (VALUES
        ('素材读取', 'QuestionGenerationMaterialRead', NULL, 1, NULL, 2, NULL,
         'question_generation:material:read', 1, 0, 1, '', 'AI 出题素材读取权限'),
        ('素材写入', 'QuestionGenerationMaterialWrite', NULL, 2, NULL, 2, NULL,
         'question_generation:material:write', 1, 0, 1, '', 'AI 出题素材写入权限'),
        ('素材删除', 'QuestionGenerationMaterialDelete', NULL, 3, NULL, 2, NULL,
         'question_generation:material:delete', 1, 0, 1, '', 'AI 出题素材删除权限'),
        ('任务读取', 'QuestionGenerationTaskRead', NULL, 4, NULL, 2, NULL,
         'question_generation:task:read', 1, 0, 1, '', 'AI 出题任务读取权限'),
        ('任务启动', 'QuestionGenerationTaskStart', NULL, 5, NULL, 2, NULL,
         'question_generation:task:start', 1, 0, 1, '', 'AI 出题任务启动权限'),
        ('任务删除', 'QuestionGenerationTaskDelete', NULL, 6, NULL, 2, NULL,
         'question_generation:task:delete', 1, 0, 1, '', 'AI 出题任务删除权限'),
        ('候选题读取', 'QuestionGenerationCandidateRead', NULL, 7, NULL, 2, NULL,
         'question_generation:candidate:read', 1, 0, 1, '', 'AI 候选题读取权限'),
        ('候选题审核', 'QuestionGenerationCandidateReview', NULL, 8, NULL, 2, NULL,
         'question_generation:candidate:review', 1, 0, 1, '', 'AI 候选题审核权限'),
        ('候选题删除', 'QuestionGenerationCandidateDelete', NULL, 9, NULL, 2, NULL,
         'question_generation:candidate:delete', 1, 0, 1, '', 'AI 候选题删除权限')
    ) AS menu(
        title, name, path, sort, icon, type, component,
        perms, status, display, cache, link, remark
    )
    WHERE NOT EXISTS (
        SELECT 1
        FROM fba.sys_menu AS existing
        WHERE existing.name = menu.name
          AND existing.deleted = 0
    );
END $$;
"""

VERIFY_SQL = """
SELECT id, title, name, path, type, perms, parent_id
FROM fba.sys_menu
WHERE name IN (
    'Gongkao',
    'GongkaoQuestionGeneration',
    'QuestionGenerationMaterialRead',
    'QuestionGenerationMaterialWrite',
    'QuestionGenerationMaterialDelete',
    'QuestionGenerationTaskRead',
    'QuestionGenerationTaskStart',
    'QuestionGenerationTaskDelete',
    'QuestionGenerationCandidateRead',
    'QuestionGenerationCandidateReview',
    'QuestionGenerationCandidateDelete'
)
ORDER BY parent_id NULLS FIRST, sort, id;
"""


async def insert_question_generation_menu(db: AsyncSession) -> list[dict[str, object]]:
    """
    录入 AI 出题后台菜单

    :param db: 数据库会话
    :return:
    """
    await db.execute(text(SYNC_MENU_SEQUENCE_SQL))
    await db.execute(text(INSERT_QUESTION_GENERATION_MENU_SQL))
    await db.execute(text(SYNC_MENU_SEQUENCE_SQL))
    result = await db.execute(text(VERIFY_SQL))
    return [dict(row._mapping) for row in result.fetchall()]


async def main() -> int:
    """脚本入口"""
    async with async_db_session.begin() as db:
        rows = await insert_question_generation_menu(db)

    print(f'[OK] question generation menu rows={len(rows)}')
    for row in rows:
        print(
            f"- id={row['id']} title={row['title']} name={row['name']} "
            f"type={row['type']} parent_id={row['parent_id']} perms={row['perms']}"
        )
    return 0


if __name__ == '__main__':
    raise SystemExit(asyncio.run(main()))
