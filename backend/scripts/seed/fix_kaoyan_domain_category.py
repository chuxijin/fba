#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把考研政治体系的 domain_category_id 从「政治(104)」改挂到「考研(1)」。

## 为什么改

前端「所属领域」下拉的数据源是 `sys_category` 里 `type='product_catalog'` 的分类，
用户选「考研」传上来的是 **id=1**。而后端 `get_systems_select` 对
`domain_category_id` 是**精确匹配**（`== 104`），不做跨树回溯。

于是考研体系原本挂的 104（它在 `knowledge_point` 树：101 考研 → 104 政治）
永远匹配不上下拉传来的 1 ⇒ **页面上选不出考研体系**。

公考那 4 个体系挂的是 1400（`product_catalog` 的「公考」），正好能匹配上 ——
这就是参照做法。考研体系按同样的规则挂 1（`product_catalog` 的「考研」）。

## 影响

- 只改 `qbank_v2_knowledge_system.domain_category_id` 一列，**不动知识点、不动标注**。
- 唯一键 `(domain_category_id, code, version, deleted)`：dev/prod 的 domain=1 都是空的，
  脚本会先探测冲突再改。
- ⚠️ 改完后**考研体系算「政治」还是「考研」**由 domain 决定（=考研）；
  科目层面的归属仍靠知识点自身的名字与 sys_category 1358~1362，不受影响。

用法：
    python -m scripts.seed.fix_kaoyan_domain_category            # 干跑
    python -m scripts.seed.fix_kaoyan_domain_category --write     # 真改
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
OLD_DOMAIN_ID = 104  # sys_category: 政治（type='knowledge_point'，前端下拉里没有）
NEW_DOMAIN_ID = 1  # sys_category: 考研（type='product_catalog'，前端下拉第一项）

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

# 目标 domain 必须是 product_catalog 才有意义（前端下拉只出这一类）
CHECK_NEW_DOMAIN_SQL = """
SELECT id, name, type FROM {schema}.sys_category
WHERE id = CAST(:did AS BIGINT) AND deleted = 0;
"""

PREVIEW_SQL = """
SELECT ks.id, ks.code, ks.name, ks.version, ks.status,
       ks.domain_category_id AS old_domain, cat.name AS old_domain_name,
       (SELECT COUNT(*) FROM {schema}.qbank_v2_knowledge_point kp
         WHERE kp.system_id = ks.id AND kp.deleted = 0) AS point_count
FROM {schema}.qbank_v2_knowledge_system ks
LEFT JOIN {schema}.sys_category cat ON cat.id = ks.domain_category_id
WHERE ks.version = CAST(:version AS VARCHAR) AND ks.deleted = 0
ORDER BY ks.id;
"""

# 唯一键冲突探测：(NEW_DOMAIN_ID, code, version, 0) 上不能已有别的行
CHECK_CONFLICT_SQL = """
SELECT ks.id, ks.name, ks.version
FROM {schema}.qbank_v2_knowledge_system ks
WHERE ks.domain_category_id = CAST(:new_did AS BIGINT)
  AND ks.version = CAST(:version AS VARCHAR)
  AND ks.deleted = 0
  AND ks.id <> CAST(:exclude_id AS BIGINT);
"""

UPDATE_SQL = """
UPDATE {schema}.qbank_v2_knowledge_system
SET domain_category_id = CAST(:new_did AS BIGINT), updated_time = NOW()
WHERE id = CAST(:sid AS BIGINT) AND deleted = 0;
"""


async def fix(db: AsyncSession, *, write: bool) -> None:
    schema = str((await db.execute(text(DETECT_SCHEMA_SQL))).scalar() or 'public')
    print(f'[i] qbank_v2_knowledge_system 所在 schema：{schema}')

    target = (
        await db.execute(
            text(CHECK_NEW_DOMAIN_SQL.format(schema=schema)), {'did': NEW_DOMAIN_ID}
        )
    ).first()
    if target is None:
        msg = f'sys_category id={NEW_DOMAIN_ID} 不存在，无法改挂'
        raise RuntimeError(msg)
    tgt_id, tgt_name, tgt_type = target
    print(f'[i] 目标 domain：id={tgt_id} name={tgt_name} type={tgt_type}')
    if tgt_type != 'product_catalog':
        msg = (
            f'目标 domain id={tgt_id} 的 type 是 {tgt_type}，'
            f'不是 product_catalog ⇒ 前端领域下拉里依然选不到，别改'
        )
        raise RuntimeError(msg)

    rows = (
        await db.execute(
            text(PREVIEW_SQL.format(schema=schema)), {'version': VERSION}
        )
    ).fetchall()
    if not rows:
        print(f'[i] 没有 version={VERSION} 的体系，无需处理')
        return

    print(f'[i] 待处理 {len(rows)} 个体系：')
    for r in rows:
        same = r[5] == NEW_DOMAIN_ID
        print(
            f'    id={r[0]} {r[2]} · {r[3]}  domain={r[5]}({r[6]}) → '
            f'{NEW_DOMAIN_ID}({tgt_name})  知识点 {r[7]} 个'
            + ('  [已是目标值]' if same else '')
        )

    if not write:
        print('[i] --write 未加，只干跑')
        return

    changed = 0
    for r in rows:
        sid = r[0]
        if r[5] == NEW_DOMAIN_ID:
            continue
        conflicts = (
            await db.execute(
                text(CHECK_CONFLICT_SQL.format(schema=schema)),
                {'exclude_id': sid, 'new_did': NEW_DOMAIN_ID, 'version': VERSION},
            )
        ).fetchall()
        if conflicts:
            names = ', '.join(f'id={c[0]}({c[1]})' for c in conflicts)
            msg = f'体系 id={sid} 改挂到 domain={NEW_DOMAIN_ID} 会撞唯一键：{names}'
            raise RuntimeError(msg)
        await db.execute(
            text(UPDATE_SQL.format(schema=schema)),
            {'new_did': NEW_DOMAIN_ID, 'sid': sid},
        )
        changed += 1
    print(f'[i] 已更新 {changed} 个体系')

    after = (
        await db.execute(
            text(PREVIEW_SQL.format(schema=schema)), {'version': VERSION}
        )
    ).fetchall()
    print('[i] 改后状态：')
    for r in after:
        print(f'    id={r[0]} {r[2]} · {r[3]}  domain={r[5]}({r[6]})  知识点 {r[7]} 个')


async def main() -> int:
    write = '--write' in sys.argv
    print(f'[i] 模式：{"干跑（默认）" if not write else "写入（--write）"}')
    async with async_db_session.begin() as db:
        await fix(db, write=write)
    return 0


if __name__ == '__main__':
    raise SystemExit(asyncio.run(main()))
