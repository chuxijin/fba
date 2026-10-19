#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""在「考研政治」知识体系下建 6 科目知识点树（幂等）。

结构（与生产库 2026-10-10 建好的版本一致）：
    政治 (kaoyan_politics, depth=0)
    ├ 马克思主义基本原理概论 (马原)
    ├ 毛泽东思想和中国特色社会主义理论体系概论 (毛中特)
    ├ 新时代中国特色社会主义思想概论 (新思想)
    ├ 中国近现代史纲要 (近病史)
    ├ 思想道德修养与法律基础 (思修)
    └ 形势政策以及当代世界经济与政治 (时政)

用法：
    python -m scripts.seed.apply_kaoyan_knowledge_system            # 干跑，只打印不写库
    python -m scripts.seed.apply_kaoyan_knowledge_system --write     # 真写
    AUTOLABEL_ROLES=... （无用，占位保持与其他 seed 脚本一致）

⚠️ **schema 差异**：生产库表在 `fba` schema 下，dev 库（100.80.0.126）只有 `public`
且表名不带前缀。下面一律用 `{schema}.` 占位符 + 运行时 `pg_class` 探测。
⚠️ 两库的列与约束已核对一致（uq_qbv2_kpoint_code = UNIQUE(system_id, code, deleted)），
   所以同一份 SQL 能在两边跑。
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

VERSION = 'kaoyan'
DOMAIN_CATEGORY_ID = 104  # sys_category.id = 政治（不是 1400 公考）
SYSTEM_CODE = 'kaoyan_politics'
SYSTEM_NAME = '考研政治'
SYSTEM_DESCRIPTION = (
    '考研政治科目知识体系。知识点树按考研政治试卷的实际科目划分（2025 版大纲）：'
    '马原、毛中特、新思想、近病史、思修、时政六个部分。'
    '其中前五个与 sys_category id 1358~1362 对应，时政为新增节点。'
    '题源为 2015–2026 共 12 个真题库 456 题。'
)

# ⚠️ 唯一事实源：加减科目只改这张表，VALUES 由它动态生成
# category_id = sys_category.id，对应科目分类；时政无对应分类故为 None
CHILD_POINTS: list[dict[str, object]] = [
    {
        'code': 'kaoyan_politics_mayuan',
        'name': '马克思主义基本原理概论',
        'description': '简称马原。马克思主义哲学、政治经济学、科学社会主义三部分',
        'category_id': 1358,
    },
    {
        'code': 'kaoyan_politics_maozhongte',
        'name': '毛泽东思想和中国特色社会主义理论体系概论',
        'description': '简称毛中特。毛泽东思想的形成发展、邓小平理论、三个代表、科学发展观等',
        'category_id': 1359,
    },
    {
        'code': 'kaoyan_politics_xinshixiang',
        'name': '新时代中国特色社会主义思想概论',
        'description': '简称新思想。习近平新时代中国特色社会主义思想的核心要义与实践要求',
        'category_id': 1360,
    },
    {
        'code': 'kaoyan_politics_shigang',
        'name': '中国近现代史纲要',
        'description': '简称近病史。从鸦片战争到新时代，按时间轴考查重大事件与历史转折',
        'category_id': 1361,
    },
    {
        'code': 'kaoyan_politics_sixiu',
        'name': '思想道德修养与法律基础',
        'description': '简称思修。理想信念、中国精神、道德与法治',
        'category_id': 1362,
    },
    {
        'code': 'kaoyan_politics_shizheng',
        'name': '形势政策以及当代世界经济与政治',
        'description': (
            '简称时政。年度时政热点与当代世界经济、国际关系；'
            '真题里通常是分析题的最后一道，题块级且时效性强'
        ),
        'category_id': None,
    },
]

ROOT_POINT = {
    'code': SYSTEM_CODE,
    'name': '政治',
    'description': '考研政治科目，包含马原、毛中特、新思想、近病史、思修、时政六个考试部分',
}

# ⚠️ 只写不读的 INSERT CTE 会被 PG 12+ 优化掉 ⇒ 末尾必须 UNION SELECT 真正引用它
UPSERT_SYSTEM_SQL = """
INSERT INTO {schema}.qbank_v2_knowledge_system (
    code, name, version, description, status, domain_category_id,
    created_by, created_time
)
SELECT
    CAST(:code AS VARCHAR), CAST(:name AS VARCHAR), CAST(:version AS VARCHAR),
    CAST(:description AS TEXT), CAST('active' AS VARCHAR),
    CAST(:domain_category_id AS BIGINT), 1, NOW()
WHERE NOT EXISTS (
    SELECT 1 FROM {schema}.qbank_v2_knowledge_system
    WHERE domain_category_id = CAST(:domain_category_id AS BIGINT)
      AND code = CAST(:code AS VARCHAR)
      AND version = CAST(:version AS VARCHAR)
      AND deleted = 0
)
RETURNING id;
"""

# 根节点 + 6 个子节点一次插完；path 先置 NULL，插完再统一 UPDATE 补
UPSERT_POINTS_SQL = """
WITH root AS (
    INSERT INTO {schema}.qbank_v2_knowledge_point (
        system_id, code, name, parent_id, path, depth, sort_order,
        description, created_by, created_time
    )
    SELECT
        CAST(:system_id AS BIGINT), CAST(:root_code AS VARCHAR),
        CAST(:root_name AS VARCHAR), NULL, NULL,
        CAST(0 AS SMALLINT), CAST(0 AS INTEGER),
        CAST(:root_desc AS TEXT), 1, NOW()
    WHERE NOT EXISTS (
        SELECT 1 FROM {schema}.qbank_v2_knowledge_point
        WHERE system_id = CAST(:system_id AS BIGINT)
          AND code = CAST(:root_code AS VARCHAR)
          AND deleted = 0
    )
    RETURNING id, system_id
),
root_final AS (
    SELECT id, system_id FROM root
    UNION ALL
    SELECT kp.id, kp.system_id
    FROM {schema}.qbank_v2_knowledge_point kp
    WHERE kp.system_id = CAST(:system_id AS BIGINT)
      AND kp.code = CAST(:root_code AS VARCHAR)
      AND kp.deleted = 0
),
children AS (
    INSERT INTO {schema}.qbank_v2_knowledge_point (
        system_id, code, name, parent_id, path, depth, sort_order,
        description, created_by, created_time
    )
    SELECT
        r.system_id, v.c_code, v.c_name, r.id, NULL, CAST(1 AS SMALLINT),
        CAST(v.c_sort AS INTEGER), v.c_desc, 1, NOW()
    FROM root_final r
    CROSS JOIN (VALUES {values}) AS v(c_code, c_name, c_desc, c_sort)
    WHERE NOT EXISTS (
        SELECT 1 FROM {schema}.qbank_v2_knowledge_point e
        WHERE e.system_id = r.system_id AND e.code = v.c_code AND e.deleted = 0
    )
    RETURNING id
)
SELECT (SELECT COUNT(*) FROM root_final) AS root_cnt,
       (SELECT COUNT(*) FROM children) AS child_cnt;
"""

# ⚠️ PG 的 UPDATE 子查询读到「语句开始时的快照」⇒ 多级 path 必须跑两轮才收敛
FIX_PATH_SQL = """
UPDATE {schema}.qbank_v2_knowledge_point kp
SET path = COALESCE(
        (SELECT p.path || '.' || CAST(kp.id AS VARCHAR)
           FROM {schema}.qbank_v2_knowledge_point p
          WHERE p.id = kp.parent_id AND p.system_id = kp.system_id),
        CAST(kp.id AS VARCHAR)
    ),
    updated_time = NOW()
WHERE kp.system_id = CAST(:system_id AS BIGINT)
  AND kp.deleted = 0
  AND kp.path IS DISTINCT FROM COALESCE(
        (SELECT p.path || '.' || CAST(kp.id AS VARCHAR)
           FROM {schema}.qbank_v2_knowledge_point p
          WHERE p.id = kp.parent_id AND p.system_id = kp.system_id),
        CAST(kp.id AS VARCHAR)
    );
"""

# 改名/改描述不重插（靠 uq_qbv2_kpoint_code 命中后 UPDATE）
# ⚠️ VALUES 里第 4 列是 int，与前三列（text）混在一个 SELECT 里 PG 推不出统一类型 ⇒
#    子查询只 SELECT 前三列，别用 SELECT *。
SYNC_TEXT_SQL = """
UPDATE {schema}.qbank_v2_knowledge_point kp
SET name = v.c_name, description = v.c_desc, updated_time = NOW()
FROM (
    SELECT CAST(:root_code AS VARCHAR) AS c_code,
           CAST(:root_name AS VARCHAR) AS c_name,
           CAST(:root_desc AS TEXT) AS c_desc
    UNION ALL
    SELECT v2.c_code, v2.c_name, v2.c_desc
    FROM (VALUES {values}) AS v2(c_code, c_name, c_desc, c_sort)
) v
WHERE kp.system_id = CAST(:system_id AS BIGINT)
  AND kp.code = v.c_code
  AND kp.deleted = 0
  AND (kp.name IS DISTINCT FROM v.c_name OR kp.description IS DISTINCT FROM v.c_desc);
"""

# ⚠️ 同一绑定参数在 text/varchar 上类型推断不一致会报 AmbiguousParameterError ⇒ 全部显式 CAST
DETECT_SCHEMA_SQL = """
SELECT COALESCE(
    (SELECT nspname FROM pg_class c
       JOIN pg_namespace n ON n.oid = c.relnamespace
      WHERE c.relname = 'qbank_v2_knowledge_system' AND c.relkind = 'r'
        AND n.nspname IN ('fba', 'public')
      ORDER BY (n.nspname = 'fba') DESC
      LIMIT 1),
    'public'
) AS schema;
"""

SYNC_SEQUENCE_SQL = """
SELECT setval(
    pg_get_serial_sequence('{schema}.qbank_v2_knowledge_point', 'id'),
    GREATEST(
        COALESCE((SELECT MAX(id) FROM {schema}.qbank_v2_knowledge_point), 1),
        COALESCE((SELECT last_value FROM {schema}.qbank_v2_knowledge_point_id_seq), 1)
    ),
    (SELECT COUNT(*) > 0 FROM {schema}.qbank_v2_knowledge_point)
);
"""

PREVIEW_SQL = """
SELECT kp.id, kp.system_id, kp.parent_id, kp.depth, kp.code, kp.name,
       kp.path, kp.sort_order
FROM {schema}.qbank_v2_knowledge_point kp
JOIN {schema}.qbank_v2_knowledge_system ks ON ks.id = kp.system_id
WHERE ks.version = CAST(:version AS VARCHAR) AND kp.deleted = 0
ORDER BY kp.depth, kp.sort_order, kp.id;
"""


def _sql_literal(value: str) -> str:
    """转成 SQL 字符串字面量。单引号翻倍；中文直接原样输出（PG 客户端 UTF-8）。"""
    return "'" + str(value).replace("'", "''") + "'"


def _build_values() -> str:
    """把 CHILD_POINTS 动态拼成 SQL VALUES 字面量（名称/描述内联成字面量）。"""
    items = [
        f"({_sql_literal(child['code'])}, {_sql_literal(child['name'])},"
        f" {_sql_literal(child['description'])}, {idx})"
        for idx, child in enumerate(CHILD_POINTS, start=1)
    ]
    return ',\n           '.join(items)


async def detect_schema(db: AsyncSession) -> str:
    result = await db.execute(text(DETECT_SCHEMA_SQL))
    return str(result.scalar() or 'public')


async def find_system(db: AsyncSession, schema: str) -> int | None:
    """查考研体系 id；不存在返回 None（不写库）。"""
    result = await db.execute(
        text(
            f"""
            SELECT id FROM {schema}.qbank_v2_knowledge_system
            WHERE domain_category_id = CAST(:did AS BIGINT)
              AND code = CAST(:code AS VARCHAR)
              AND version = CAST(:version AS VARCHAR)
              AND deleted = 0
            LIMIT 1
            """
        ),
        {'did': DOMAIN_CATEGORY_ID, 'code': SYSTEM_CODE, 'version': VERSION},
    )
    row = result.scalar()
    return int(row) if row is not None else None


async def get_or_create_system(db: AsyncSession, schema: str) -> int:
    """返回考研体系 id；已存在则复用，否则新建。"""
    existing = await find_system(db, schema)
    if existing is not None:
        return existing

    await db.execute(
        text(UPSERT_SYSTEM_SQL.format(schema=schema)),
        {
            'code': SYSTEM_CODE,
            'name': SYSTEM_NAME,
            'version': VERSION,
            'description': SYSTEM_DESCRIPTION,
            'domain_category_id': DOMAIN_CATEGORY_ID,
        },
    )
    created = await find_system(db, schema)
    if created is None:
        msg = f'创建体系失败：{SYSTEM_NAME}/{VERSION} 创建后仍查不到'
        raise RuntimeError(msg)
    return created


async def apply(db: AsyncSession, *, dry_run: bool) -> int | None:
    schema = await detect_schema(db)
    print(f'[i] qbank_v2_* 所在 schema：{schema}')

    if dry_run:
        # ⚠️ 干跑必须零写入：只查体系是否存在，绝不 INSERT
        system_id = await find_system(db, schema)
        if system_id is None:
            print('[i] 体系尚不存在（将新建 1 个体系 + 1 根 + 6 子）')
            return None
        print(f'[i] 体系已存在 id={system_id}（{SYSTEM_NAME} / version={VERSION}）')
        rows = await db.execute(
            text(PREVIEW_SQL.format(schema=schema)), {'version': VERSION}
        )
        found = rows.fetchall()
        if found:
            print(f'[i] 库里已存在 {len(found)} 个知识点：')
            for r in found:
                print(f'    id={r[0]} depth={r[3]} code={r[4]} name={r[5]} path={r[6]}')
        else:
            print('[i] 知识点为空（将新建 1 根 + 6 子）')
        return system_id

    system_id = await get_or_create_system(db, schema)
    print(f'[i] 体系 id={system_id}（{SYSTEM_NAME} / version={VERSION}）')

    values_sql = _build_values()
    params: dict[str, object] = {
        'system_id': system_id,
        'root_code': ROOT_POINT['code'],
        'root_name': ROOT_POINT['name'],
        'root_desc': ROOT_POINT['description'],
    }
    for idx, child in enumerate(CHILD_POINTS, start=1):
        params[f'c{idx}_code'] = child['code']
        params[f'c{idx}_name'] = child['name']
        params[f'c{idx}_desc'] = child['description']

    # ⚠️ async_db_session() 裸用不 commit，必须由调用方 begin()/commit()
    cnt = await db.execute(
        text(UPSERT_POINTS_SQL.format(schema=schema, values=values_sql)), params
    )
    root_cnt, child_cnt = cnt.first()
    print(f'[i] 新插：根节点 {root_cnt} 个，子节点 {child_cnt} 个')

    await db.execute(text(SYNC_SEQUENCE_SQL.format(schema=schema)))

    # path 两轮才收敛（PG UPDATE 快照语义）
    for round_no in (1, 2):
        res = await db.execute(text(FIX_PATH_SQL.format(schema=schema)), params)
        print(f'[i] path 修正第 {round_no} 轮：{res.rowcount} 行')

    res = await db.execute(
        text(SYNC_TEXT_SQL.format(schema=schema, values=values_sql)), params
    )
    print(f'[i] 名称/描述同步：{res.rowcount} 行')

    await db.execute(text(SYNC_SEQUENCE_SQL.format(schema=schema)))
    return system_id


async def main() -> int:
    dry_run = '--write' not in sys.argv
    print(f'[i] 模式：{"干跑（默认）" if dry_run else "写入（--write）"}')
    async with async_db_session.begin() as db:
        await apply(db, dry_run=dry_run)
        rows = (
            await db.execute(
                text(PREVIEW_SQL.format(schema=await detect_schema(db))),
                {'version': VERSION},
            )
        ).fetchall()

    print(f'\n[OK] {SYSTEM_NAME} 知识体系共 {len(rows)} 个知识点：')
    for r in rows:
        indent = '  ' * int(r[3])
        print(f'  {indent}[{r[3]}] id={r[0]:<4} {r[5]}  (code={r[4]}, path={r[6]})')
    return 0


if __name__ == '__main__':
    raise SystemExit(asyncio.run(main()))
