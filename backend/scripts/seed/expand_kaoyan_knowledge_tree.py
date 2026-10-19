#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""扩展「考研政治」知识体系树：在已有的 6 个一级科目下批量导入 52 个二级章节和 153 个三级小节（幂等）。

结构：
    政治 (588, depth=0)
    ├── 马克思主义基本原理概论 (589, depth=1)
    │   ├── 导论 ... (depth=2)
    │   │   ├── 第一节 什么是马克思主义 (depth=3)
    │   │   └── ...
    │   ├── 第一章 世界的物质性及发展规律 (depth=2)
    │   │   ├── 第一节 世界的多样性与物质统一性 (depth=3)
    │   │   └── ...
    └── ...

用法：
    python -m backend.scripts.seed.expand_kaoyan_knowledge_tree            # 默认 dry-run，仅校验并输出统计
    python -m backend.scripts.seed.expand_kaoyan_knowledge_tree --dump-sql # 导出生成好的迁移 SQL
    python -m backend.scripts.seed.expand_kaoyan_knowledge_tree --write    # 连接数据库真实写入
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

DATA_FILE = Path(__file__).resolve().parent / "data" / "kaoyan_politics_tree.json"
SYSTEM_CODE = "kaoyan_politics"
VERSION = "kaoyan"

# 已建立的 6 个科目 code 映射
EXISTING_SUBJECT_CODES = {
    "kaoyan_politics_mayuan",
    "kaoyan_politics_maozhongte",
    "kaoyan_politics_xinshixiang",
    "kaoyan_politics_shigang",
    "kaoyan_politics_sixiu",
    "kaoyan_politics_shizheng",
}


def load_and_validate_data() -> tuple[list[dict], list[dict]]:
    """加载并严格校验拓扑关系。返回 (level2_chapters, level3_sections)。"""
    if not DATA_FILE.exists():
        raise FileNotFoundError(f"数据文件不存在: {DATA_FILE}")

    with open(DATA_FILE, "r", encoding="utf-8") as f:
        items = json.load(f)

    codes_seen = set()
    ch_codes = set()
    sec_codes = set()
    level2_items = []
    level3_items = []

    for idx, item in enumerate(items):
        code = item.get("code")
        name = item.get("name")
        parent_code = item.get("parent_code")
        depth = item.get("depth")

        if not code or not name or not parent_code or depth not in (2, 3):
            raise ValueError(f"节点数据格式异常 (index={idx}): {item}")

        if code in codes_seen:
            raise ValueError(f"存在重复的 code: {code}")
        codes_seen.add(code)

        if depth == 2:
            if parent_code not in EXISTING_SUBJECT_CODES:
                raise ValueError(f"二级章节的 parent_code [{parent_code}] 不在 6 大科目中: {item}")
            ch_codes.add(code)
            level2_items.append(item)
        elif depth == 3:
            if parent_code not in ch_codes:
                raise ValueError(f"三级小节的 parent_code [{parent_code}] 未在二级章节中定义: {item}")
            sec_codes.add(code)
            level3_items.append(item)

    return level2_items, level3_items


def _sql_literal(value: str | None) -> str:
    if value is None:
        return "NULL"
    return "'" + str(value).replace("'", "''") + "'"


def generate_migration_sql(schema: str = "fba") -> str:
    """生成具备完全幂等性的 SQL 语句。"""
    level2_items, level3_items = load_and_validate_data()

    sql_parts = []
    sql_parts.append(f"-- ==========================================================================")
    sql_parts.append(f"-- 考研政治 52 个二级章节与 153 个三级小节增量迁移脚本")
    sql_parts.append(f"-- 架构: 科目(depth=1) -> 章节(depth=2) -> 小节(depth=3)")
    sql_parts.append(f"-- ==========================================================================")
    sql_parts.append("DO $$")
    sql_parts.append("DECLARE")
    sql_parts.append("    v_system_id BIGINT;")
    sql_parts.append("BEGIN")
    sql_parts.append(f"    SELECT id INTO v_system_id FROM {schema}.qbank_v2_knowledge_system WHERE code = '{SYSTEM_CODE}' AND version = '{VERSION}' AND deleted = 0 LIMIT 1;")
    sql_parts.append("    IF v_system_id IS NULL THEN")
    sql_parts.append("        RAISE EXCEPTION '未找到 code=% version=% 的知识体系，请先初始化考研政治根体系', 'kaoyan_politics', 'kaoyan';")
    sql_parts.append("    END IF;")
    sql_parts.append("")
    sql_parts.append("    -- 1. 批量插入二级节点（章节，52 个）")
    for ch in level2_items:
        code_lit = _sql_literal(ch["code"])
        name_lit = _sql_literal(ch["name"])
        desc_lit = _sql_literal(ch.get("description", ""))
        p_code_lit = _sql_literal(ch["parent_code"])
        sort_lit = int(ch.get("sort_order", 0))

        insert_ch_sql = f"""
    INSERT INTO {schema}.qbank_v2_knowledge_point (
        system_id, code, name, parent_id, path, depth, sort_order, description, created_by, created_time, deleted
    )
    SELECT
        v_system_id, {code_lit}, {name_lit}, p.id, NULL, 2, {sort_lit}, {desc_lit}, 1, NOW(), 0
    FROM {schema}.qbank_v2_knowledge_point p
    WHERE p.system_id = v_system_id AND p.code = {p_code_lit} AND p.deleted = 0
      AND NOT EXISTS (
          SELECT 1 FROM {schema}.qbank_v2_knowledge_point e
          WHERE e.system_id = v_system_id AND e.code = {code_lit} AND e.deleted = 0
      );
        """.strip()
        sql_parts.append("    " + insert_ch_sql.replace("\n", "\n    "))

    sql_parts.append("")
    sql_parts.append("    -- 2. 批量插入三级节点（小节/考点，153 个）")
    for sec in level3_items:
        code_lit = _sql_literal(sec["code"])
        name_lit = _sql_literal(sec["name"])
        desc_lit = _sql_literal(sec.get("description", ""))
        p_code_lit = _sql_literal(sec["parent_code"])
        sort_lit = int(sec.get("sort_order", 0))

        insert_sec_sql = f"""
    INSERT INTO {schema}.qbank_v2_knowledge_point (
        system_id, code, name, parent_id, path, depth, sort_order, description, created_by, created_time, deleted
    )
    SELECT
        v_system_id, {code_lit}, {name_lit}, p.id, NULL, 3, {sort_lit}, {desc_lit}, 1, NOW(), 0
    FROM {schema}.qbank_v2_knowledge_point p
    WHERE p.system_id = v_system_id AND p.code = {p_code_lit} AND p.deleted = 0
      AND NOT EXISTS (
          SELECT 1 FROM {schema}.qbank_v2_knowledge_point e
          WHERE e.system_id = v_system_id AND e.code = {code_lit} AND e.deleted = 0
      );
        """.strip()
        sql_parts.append("    " + insert_sec_sql.replace("\n", "\n    "))

    sql_parts.append("")
    sql_parts.append("    -- 3. 递归收敛计算 path 路径（支持多级）")
    sql_parts.append("    FOR i IN 1..4 LOOP")
    sql_parts.append(f"""
        UPDATE {schema}.qbank_v2_knowledge_point kp
        SET path = COALESCE(
                (SELECT p.path || '.' || CAST(kp.id AS VARCHAR)
                   FROM {schema}.qbank_v2_knowledge_point p
                  WHERE p.id = kp.parent_id AND p.system_id = kp.system_id),
                CAST(kp.id AS VARCHAR)
            ),
            updated_time = NOW()
        WHERE kp.system_id = v_system_id
          AND kp.deleted = 0
          AND (
              kp.path IS NULL OR
              kp.path IS DISTINCT FROM COALESCE(
                  (SELECT p.path || '.' || CAST(kp.id AS VARCHAR)
                     FROM {schema}.qbank_v2_knowledge_point p
                    WHERE p.id = kp.parent_id AND p.system_id = kp.system_id),
                  CAST(kp.id AS VARCHAR)
              )
          );
    """.rstrip())
    sql_parts.append("    END LOOP;")
    sql_parts.append("")
    sql_parts.append("    -- 4. 修复主键自增序列")
    sql_parts.append(f"""
    PERFORM setval(
        pg_get_serial_sequence('{schema}.qbank_v2_knowledge_point', 'id'),
        GREATEST(
            COALESCE((SELECT MAX(id) FROM {schema}.qbank_v2_knowledge_point), 1),
            COALESCE((SELECT last_value FROM {schema}.qbank_v2_knowledge_point_id_seq), 1)
        ),
        (SELECT COUNT(*) > 0 FROM {schema}.qbank_v2_knowledge_point)
    );
    """.rstrip())
    sql_parts.append("")
    sql_parts.append("    RAISE NOTICE '考研政治三级知识点拓扑扩展完成！';")
    sql_parts.append("END $$;")
    sql_parts.append("")

    return "\n".join(sql_parts)


def main():
    parser = argparse.ArgumentParser(description="考研政治三级知识点树扩展导入")
    parser.add_argument("--dump-sql", action="store_true", help="输出完整 SQL 脚本到控制台或文件")
    parser.add_argument("--schema", default="fba", help="数据库 schema 名 (生产环境为 fba, 开发环境为 public)")
    parser.add_argument("--write", action="store_true", help="直接连接数据库执行写入")
    args = parser.parse_args()

    level2_items, level3_items = load_and_validate_data()
    print("=" * 60)
    print("考研政治知识点体系拓扑数据校验成功：")
    print(f"  - 二级章节 (Depth=2): {len(level2_items)} 个")
    print(f"  - 三级小节 (Depth=3): {len(level3_items)} 个")
    print(f"  - 增量待导入总计:     {len(level2_items) + len(level3_items)} 个节点")
    print("=" * 60)

    sql_content = generate_migration_sql(schema=args.schema)

    if args.dump_sql:
        out_path = Path(__file__).resolve().parent / "20261017_expand_kaoyan_politics_tree.sql"
        out_path.write_text(sql_content, encoding="utf-8")
        print(f"完整 SQL 脚本已导出至: {out_path}")

        # 生成分步执行 SQL
        dir_path = Path(__file__).resolve().parent
        # Step 1
        s1 = ["DO $$ DECLARE v_system_id BIGINT; BEGIN",
              f"    SELECT id INTO v_system_id FROM {args.schema}.qbank_v2_knowledge_system WHERE code = '{SYSTEM_CODE}' AND version = '{VERSION}' AND deleted = 0 LIMIT 1;"]
        for ch in level2_items:
            s1.append(f"""    INSERT INTO {args.schema}.qbank_v2_knowledge_point (system_id, code, name, parent_id, path, depth, sort_order, description, created_by, created_time, deleted) SELECT v_system_id, {_sql_literal(ch['code'])}, {_sql_literal(ch['name'])}, p.id, NULL, 2, {int(ch.get('sort_order', 0))}, {_sql_literal(ch.get('description', ''))}, 1, NOW(), 0 FROM {args.schema}.qbank_v2_knowledge_point p WHERE p.system_id = v_system_id AND p.code = {_sql_literal(ch['parent_code'])} AND p.deleted = 0 AND NOT EXISTS (SELECT 1 FROM {args.schema}.qbank_v2_knowledge_point e WHERE e.system_id = v_system_id AND e.code = {_sql_literal(ch['code'])} AND e.deleted = 0);""")
        s1.append("END $$;")
        (dir_path / "step1_chapters.sql").write_text("\n".join(s1), encoding="utf-8")

        # Step 2
        s2 = ["DO $$ DECLARE v_system_id BIGINT; BEGIN",
              f"    SELECT id INTO v_system_id FROM {args.schema}.qbank_v2_knowledge_system WHERE code = '{SYSTEM_CODE}' AND version = '{VERSION}' AND deleted = 0 LIMIT 1;"]
        for sec in level3_items:
            s2.append(f"""    INSERT INTO {args.schema}.qbank_v2_knowledge_point (system_id, code, name, parent_id, path, depth, sort_order, description, created_by, created_time, deleted) SELECT v_system_id, {_sql_literal(sec['code'])}, {_sql_literal(sec['name'])}, p.id, NULL, 3, {int(sec.get('sort_order', 0))}, {_sql_literal(sec.get('description', ''))}, 1, NOW(), 0 FROM {args.schema}.qbank_v2_knowledge_point p WHERE p.system_id = v_system_id AND p.code = {_sql_literal(sec['parent_code'])} AND p.deleted = 0 AND NOT EXISTS (SELECT 1 FROM {args.schema}.qbank_v2_knowledge_point e WHERE e.system_id = v_system_id AND e.code = {_sql_literal(sec['code'])} AND e.deleted = 0);""")
        s2.append("END $$;")
        (dir_path / "step2_sections.sql").write_text("\n".join(s2), encoding="utf-8")

        # Step 3
        s3 = ["DO $$ DECLARE v_system_id BIGINT; BEGIN",
              f"    SELECT id INTO v_system_id FROM {args.schema}.qbank_v2_knowledge_system WHERE code = '{SYSTEM_CODE}' AND version = '{VERSION}' AND deleted = 0 LIMIT 1;",
              f"""    FOR i IN 1..4 LOOP
        UPDATE {args.schema}.qbank_v2_knowledge_point kp
        SET path = COALESCE(
                (SELECT p.path || '.' || CAST(kp.id AS VARCHAR)
                   FROM {args.schema}.qbank_v2_knowledge_point p
                  WHERE p.id = kp.parent_id AND p.system_id = kp.system_id),
                CAST(kp.id AS VARCHAR)
            ),
            updated_time = NOW()
        WHERE kp.system_id = v_system_id
          AND kp.deleted = 0
          AND (
              kp.path IS NULL OR
              kp.path IS DISTINCT FROM COALESCE(
                  (SELECT p.path || '.' || CAST(kp.id AS VARCHAR)
                     FROM {args.schema}.qbank_v2_knowledge_point p
                    WHERE p.id = kp.parent_id AND p.system_id = kp.system_id),
                  CAST(kp.id AS VARCHAR)
              )
          );
    END LOOP;

    PERFORM setval(
        pg_get_serial_sequence('{args.schema}.qbank_v2_knowledge_point', 'id'),
        GREATEST(
            COALESCE((SELECT MAX(id) FROM {args.schema}.qbank_v2_knowledge_point), 1),
            COALESCE((SELECT last_value FROM {args.schema}.qbank_v2_knowledge_point_id_seq), 1)
        ),
        (SELECT COUNT(*) > 0 FROM {args.schema}.qbank_v2_knowledge_point)
    );
END $$;"""]
        (dir_path / "step3_path.sql").write_text("\n".join(s3), encoding="utf-8")
        print(f"分步 SQL 脚本已导出至 step1_chapters.sql, step2_sections.sql, step3_path.sql")
        return

    if not args.write:
        print("\n[Dry-run 模式完成] 数据校验 100% 通过。如需真写，请加上 --write 参数或导出 SQL 执行。")
        return

    # 若需要本地直接连库
    try:
        import asyncio
        from backend.database.db import async_db_session
        from sqlalchemy import text

        async def _run():
            async with async_db_session() as session:
                await session.execute(text(sql_content))
                await session.commit()
            print("数据库直接执行成功！")

        asyncio.run(_run())
    except Exception as e:
        print(f"本地直连执行失败 ({e})，建议使用导出的 SQL 通过数据库管理工具/MCP 导入。")


if __name__ == "__main__":
    main()
