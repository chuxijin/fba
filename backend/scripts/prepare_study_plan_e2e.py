#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import asyncio
import sys

from datetime import date
from pathlib import Path
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_DIR = Path(__file__).resolve().parent
for path in (PROJECT_ROOT, SCRIPT_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from bind_study_plan_roles import bind_study_plan_roles  # noqa: E402
from backend.app.question_bank.service.user_account_service import user_account_service  # noqa: E402
from backend.app.study_plan.schema.template import InstantiateStudyPlanTemplateParam  # noqa: E402
from backend.app.study_plan.service.template_service import instantiate_template  # noqa: E402
from backend.common.grayscale import check_grayscale  # noqa: E402
from backend.database.db import async_db_session  # noqa: E402
from backend.utils.timezone import timezone  # noqa: E402


SYNC_USER_ROLE_SEQUENCE_SQL = """
SELECT setval(
    pg_get_serial_sequence('fba.sys_user_role', 'id'),
    COALESCE((SELECT MAX(id) FROM fba.sys_user_role), 1),
    (SELECT COUNT(*) > 0 FROM fba.sys_user_role)
);
"""

GET_USER_BY_USERNAME_SQL = """
SELECT id, username, nickname, status, is_superuser, is_staff
FROM fba.sys_user
WHERE username = :username
  AND deleted = 0
ORDER BY id
LIMIT 1;
"""

GET_STUDENT_CANDIDATES_SQL = """
SELECT id, username, nickname, status, is_superuser, is_staff
FROM fba.sys_user
WHERE deleted = 0
  AND (
      username = :username
      OR nickname = :nickname
  )
ORDER BY
    CASE WHEN username = :username THEN 0 ELSE 1 END,
    id;
"""

GET_ROLE_ID_SQL = """
SELECT id
FROM fba.sys_role
WHERE name = :name
  AND deleted = 0
ORDER BY id
LIMIT 1;
"""

ENABLE_MENTOR_STAFF_SQL = """
UPDATE fba.sys_user
SET is_staff = TRUE
WHERE id = :user_id
  AND deleted = 0;
"""

ENABLE_USER_ROLE_SQL = """
UPDATE fba.sys_user_role
SET status = 1,
    valid_from = NULL,
    valid_to = NULL
WHERE user_id = :user_id
  AND role_id = :role_id;
"""

INSERT_USER_ROLE_SQL = """
INSERT INTO fba.sys_user_role (user_id, role_id)
SELECT :user_id, :role_id
WHERE NOT EXISTS (
    SELECT 1
    FROM fba.sys_user_role
    WHERE user_id = :user_id
      AND role_id = :role_id
);
"""

UPSERT_MENTOR_RELATION_SQL = """
WITH updated AS (
    UPDATE fba.study_mentor_student
    SET assigned_by = :assigned_by,
        status = 'active',
        note = :note,
        deleted = 0,
        deleted_time = NULL
    WHERE mentor_id = :mentor_id
      AND student_id = :student_id
    RETURNING id
), inserted AS (
    INSERT INTO fba.study_mentor_student (
        mentor_id, student_id, assigned_by, status, note, assigned_at, created_time
    )
    SELECT :mentor_id, :student_id, :assigned_by, 'active', :note, NOW(), NOW()
    WHERE NOT EXISTS (SELECT 1 FROM updated)
    RETURNING id
)
SELECT id FROM updated
UNION ALL
SELECT id FROM inserted
LIMIT 1;
"""

GET_TEMPLATE_SQL = """
SELECT
    template.id,
    template.name,
    template.duration_days,
    template.domain,
    COUNT(item.id) AS item_count
FROM fba.study_plan_template AS template
JOIN fba.study_plan_template_item AS item
    ON item.template_id = template.id
   AND item.deleted = 0
WHERE template.deleted = 0
  AND template.is_active = TRUE
GROUP BY template.id, template.name, template.duration_days, template.domain
HAVING COUNT(item.id) > 0
ORDER BY
    CASE WHEN template.name = '国考冲刺 · 数量关系 7 天试用' THEN 0 ELSE 1 END,
    template.id DESC
LIMIT 1;
"""

GET_EXISTING_PLAN_SQL = """
SELECT id, title, start_date, end_date, status
FROM fba.study_plan
WHERE user_id = :user_id
  AND template_id = :template_id
  AND start_date = :start_date
  AND status = 'active'
  AND deleted = 0
ORDER BY id DESC
LIMIT 1;
"""

COUNT_PLAN_ITEMS_SQL = """
SELECT COUNT(*)
FROM fba.study_plan_item
WHERE plan_id = :plan_id
  AND deleted = 0;
"""


def build_args() -> argparse.Namespace:
    """构建命令行参数"""
    parser = argparse.ArgumentParser(description='准备学习规划端到端联调数据')
    parser.add_argument('--mentor-username', default='admin', help='导师用户名')
    parser.add_argument('--student-username', default='test123', help='学员用户名')
    parser.add_argument('--student-nickname', default='桥水彼岸', help='学员昵称')
    parser.add_argument('--title', default=None, help='计划标题，默认使用模板名加联调标识')
    parser.add_argument('--start', default=None, help='计划开始日期 YYYY-MM-DD，默认今天')
    return parser.parse_args()


async def get_one_mapping(db: AsyncSession, sql: str, params: dict[str, object]) -> dict[str, Any] | None:
    """
    查询单行映射

    :param db: 数据库会话
    :param sql: SQL 文本
    :param params: 查询参数
    :return:
    """
    result = await db.execute(text(sql), params)
    row = result.mappings().first()
    if row is None:
        return None
    return dict(row)


async def get_all_mappings(db: AsyncSession, sql: str, params: dict[str, object]) -> list[dict[str, Any]]:
    """
    查询多行映射

    :param db: 数据库会话
    :param sql: SQL 文本
    :param params: 查询参数
    :return:
    """
    result = await db.execute(text(sql), params)
    return [dict(row) for row in result.mappings().all()]


async def resolve_mentor(db: AsyncSession, username: str) -> dict[str, Any]:
    """
    解析导师用户

    :param db: 数据库会话
    :param username: 导师用户名
    :return:
    """
    user = await get_one_mapping(db, GET_USER_BY_USERNAME_SQL, {'username': username})
    if user is None:
        raise RuntimeError(f'未找到导师用户 username={username}')
    if user['status'] != 1:
        raise RuntimeError(f'导师用户已停用 user_id={user["id"]}')
    return user


async def resolve_student(db: AsyncSession, username: str, nickname: str) -> dict[str, Any]:
    """
    解析学员用户

    :param db: 数据库会话
    :param username: 学员用户名
    :param nickname: 学员昵称
    :return:
    """
    candidates = await get_all_mappings(
        db,
        GET_STUDENT_CANDIDATES_SQL,
        {'username': username, 'nickname': nickname},
    )
    exact_username = [user for user in candidates if user['username'] == username]
    if len(exact_username) == 1:
        user = exact_username[0]
    elif len(candidates) == 1:
        user = candidates[0]
    elif not candidates:
        raise RuntimeError(f'未找到学员用户 username={username} nickname={nickname}')
    else:
        ids = ','.join(str(user['id']) for user in candidates)
        raise RuntimeError(f'学员条件匹配到多个用户，请确认 username/nickname，candidate_ids={ids}')

    if user['status'] != 1:
        raise RuntimeError(f'学员用户已停用 user_id={user["id"]}')
    return user


async def get_role_id(db: AsyncSession, name: str) -> int:
    """
    获取角色 ID

    :param db: 数据库会话
    :param name: 角色名称
    :return:
    """
    row = await get_one_mapping(db, GET_ROLE_ID_SQL, {'name': name})
    if row is None:
        raise RuntimeError(f'未找到角色 {name}')
    return int(row['id'])


async def ensure_user_role(db: AsyncSession, user_id: int, role_id: int) -> None:
    """
    确保用户拥有角色

    :param db: 数据库会话
    :param user_id: 用户 ID
    :param role_id: 角色 ID
    :return:
    """
    await db.execute(text(SYNC_USER_ROLE_SEQUENCE_SQL))
    await db.execute(text(ENABLE_USER_ROLE_SQL), {'user_id': user_id, 'role_id': role_id})
    await db.execute(text(INSERT_USER_ROLE_SQL), {'user_id': user_id, 'role_id': role_id})
    await db.execute(text(SYNC_USER_ROLE_SEQUENCE_SQL))


async def ensure_accounts(db: AsyncSession, mentor_id: int, student_id: int) -> None:
    """
    确保导师和学员有学习账户

    :param db: 数据库会话
    :param mentor_id: 导师用户 ID
    :param student_id: 学员用户 ID
    :return:
    """
    await user_account_service.ensure_by_sys_user_id(
        db=db,
        sys_user_id=mentor_id,
        register_channel='study_plan_e2e',
    )
    await user_account_service.ensure_by_sys_user_id(
        db=db,
        sys_user_id=student_id,
        register_channel='study_plan_e2e',
    )


async def ensure_mentor_relation(db: AsyncSession, mentor_id: int, student_id: int) -> int:
    """
    确保导师学员关系有效

    :param db: 数据库会话
    :param mentor_id: 导师用户 ID
    :param student_id: 学员用户 ID
    :return:
    """
    row = await get_one_mapping(
        db,
        UPSERT_MENTOR_RELATION_SQL,
        {
            'mentor_id': mentor_id,
            'student_id': student_id,
            'assigned_by': mentor_id,
            'note': 'E2E 联调：admin -> test123',
        },
    )
    if row is None:
        raise RuntimeError('导师学员关系写入失败')
    return int(row['id'])


async def ensure_plan(
    db: AsyncSession, student_id: int, mentor_id: int, title: str | None, start: str | None
) -> dict[str, Any]:
    """
    确保联调计划存在

    :param db: 数据库会话
    :param student_id: 学员用户 ID
    :param mentor_id: 导师用户 ID
    :param title: 计划标题
    :param start: 开始日期
    :return:
    """
    template = await get_one_mapping(db, GET_TEMPLATE_SQL, {})
    if template is None:
        return {
            'created': False,
            'template': None,
            'plan': None,
            'item_count': 0,
        }

    start_date = date.fromisoformat(start) if start else timezone.now().date()
    existing_plan = await get_one_mapping(
        db,
        GET_EXISTING_PLAN_SQL,
        {
            'user_id': student_id,
            'template_id': template['id'],
            'start_date': start_date,
        },
    )
    if existing_plan is not None:
        item_count = await get_plan_item_count(db, int(existing_plan['id']))
        return {
            'created': False,
            'template': template,
            'plan': existing_plan,
            'item_count': item_count,
        }

    plan_title = title or f'{template["name"]} · 联调'
    param = InstantiateStudyPlanTemplateParam(
        template_id=int(template['id']),
        user_id=student_id,
        title=plan_title,
        start_date=start_date,
    )
    plan = await instantiate_template(db, param, creator_id=mentor_id)
    item_count = await get_plan_item_count(db, plan.id)
    return {
        'created': True,
        'template': template,
        'plan': {
            'id': plan.id,
            'title': plan.title,
            'start_date': plan.start_date,
            'end_date': plan.end_date,
            'status': plan.status,
        },
        'item_count': item_count,
    }


async def get_plan_item_count(db: AsyncSession, plan_id: int) -> int:
    """
    获取计划项数量

    :param db: 数据库会话
    :param plan_id: 计划 ID
    :return:
    """
    result = await db.execute(text(COUNT_PLAN_ITEMS_SQL), {'plan_id': plan_id})
    return int(result.scalar_one())


async def clear_user_cache(user_ids: list[int]) -> str | None:
    """
    清理用户缓存

    :param user_ids: 用户 ID 列表
    :return:
    """
    try:
        from backend.app.admin.utils.cache import user_cache_manager

        await user_cache_manager.clear(user_ids)
    except Exception as e:
        return str(e)
    return None


async def main() -> int:
    """脚本入口"""
    args = build_args()

    async with async_db_session.begin() as db:
        await bind_study_plan_roles(db)

        mentor = await resolve_mentor(db, args.mentor_username)
        student = await resolve_student(db, args.student_username, args.student_nickname)

        mentor_id = int(mentor['id'])
        student_id = int(student['id'])

        await ensure_accounts(db, mentor_id, student_id)
        await db.execute(text(ENABLE_MENTOR_STAFF_SQL), {'user_id': mentor_id})

        admin_role_id = await get_role_id(db, '学习规划管理员')
        mentor_role_id = await get_role_id(db, '学习规划导师')
        await ensure_user_role(db, mentor_id, admin_role_id)
        await ensure_user_role(db, mentor_id, mentor_role_id)

        relation_id = await ensure_mentor_relation(db, mentor_id, student_id)
        plan_result = await ensure_plan(db, student_id, mentor_id, args.title, args.start)

    cache_error = await clear_user_cache([mentor_id, student_id])
    whitelist_open = await check_grayscale(student_id, 'study_plan')
    whitelist_tip = 'open'
    if not whitelist_open:
        whitelist_tip = f'missing:{student_id}'

    print('[OK] study plan e2e data prepared')
    print(
        f'- mentor id={mentor_id} username={mentor["username"]} '
        f'nickname={mentor["nickname"]} roles=学习规划管理员,学习规划导师'
    )
    print(
        f'- student id={student_id} username={student["username"]} '
        f'nickname={student["nickname"]} whitelist={whitelist_tip}'
    )
    print(f'- relation id={relation_id} status=active')

    template = plan_result['template']
    plan = plan_result['plan']
    if template is None or plan is None:
        print('[WARN] no active study plan template with items found, plan was not created')
        return 0

    created_label = 'created' if plan_result['created'] else 'reused'
    print(f'- template id={template["id"]} name={template["name"]} items={template["item_count"]}')
    print(
        f'- plan {created_label} id={plan["id"]} title={plan["title"]} '
        f'range={plan["start_date"]}~{plan["end_date"]} '
        f'items={plan_result["item_count"]}'
    )

    if cache_error is not None:
        print(f'[WARN] clear user cache failed: {cache_error}')
    return 0


if __name__ == '__main__':
    raise SystemExit(asyncio.run(main()))
