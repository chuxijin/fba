#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""一次性迁移：把生产环境 2026 国考行测「资料分析」题目/材料/解析同步到开发环境

- 生产库（源）：fba schema
- 开发库（目标）：public schema
- 通过参数化插入搬运，jsonb 以文本读出、::jsonb 写入，跳过 content_vector 向量列
- ON CONFLICT DO NOTHING，可安全重复执行
"""
import asyncio
import re
from pathlib import Path

import asyncpg

BASE = Path(__file__).resolve().parent.parent

# 2026 三套行测试卷（市地级 61 / 副省级 62 / 行政执法 63）在「资料分析」章节 42 的挂载条件
PLACEMENT_BANKS = (61, 62, 63)
CHAPTER_ID = 42


def load_env(path: Path) -> dict[str, str]:
    """解析 .env 文件为字典"""
    env: dict[str, str] = {}
    for line in path.read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, _, val = line.partition('=')
        env[key.strip()] = val.strip().strip('\'"')
    return env


def build_dsn(env: dict[str, str], db_key: str = 'DATABASE_NAME') -> dict:
    """从 env 字典构造 asyncpg 连接参数"""
    return {
        'host': env['DATABASE_HOST'],
        'port': int(env['DATABASE_PORT']),
        'user': env['DATABASE_USER'],
        'password': env.get('DATABASE_PASSWORD', ''),
        'database': env.get('DATABASE_NAME') or env.get('DATABASE_SCHEMA') or 'fba',
    }


async def fetch_target_qids(src: asyncpg.Connection) -> list[int]:
    """取 2026 资料分析去重题目 ID"""
    rows = await src.fetch(
        """
        SELECT DISTINCT question_id AS id
        FROM fba.study_question_placement
        WHERE chapter_id = $1 AND bank_id = ANY($2::bigint[])
        ORDER BY 1
        """,
        CHAPTER_ID,
        list(PLACEMENT_BANKS),
    )
    return [r['id'] for r in rows]


async def copy_table(
    src: asyncpg.Connection,
    dst: asyncpg.Connection,
    label: str,
    select_sql: str,
    select_args: list,
    insert_sql: str,
    columns: list[str],
) -> tuple[int, int]:
    """
    通用搬运：从源库查询、逐行插入目标库

    :param label: 表标签，用于打印
    :param select_sql: 源库查询语句
    :param select_args: 源库查询参数
    :param insert_sql: 目标库插入语句（含 ON CONFLICT）
    :param columns: 按 insert 占位符顺序排列的列名
    :return: (源行数, 实际插入行数)
    """
    rows = await src.fetch(select_sql, *select_args)
    inserted = 0
    for row in rows:
        values = [row[col] for col in columns]
        status = await dst.execute(insert_sql, *values)
        # asyncpg execute 返回形如 'INSERT 0 1'
        if status.endswith('1'):
            inserted += 1
    print(f'  [{label}] 源 {len(rows)} 行 → 新插入 {inserted} 行')
    return len(rows), inserted


async def main() -> None:
    dev_env = load_env(BASE / '.env')
    prod_env = load_env(BASE / '.env.prod')

    src = await asyncpg.connect(**build_dsn(prod_env))
    dst = await asyncpg.connect(**build_dsn(dev_env))
    print('已连接：生产(fba) 与 开发(public)')

    try:
        qids = await fetch_target_qids(src)
        print(f'2026 资料分析去重题目：{len(qids)} 道 → {qids}')
        if not qids:
            print('未找到目标题目，终止')
            return

        # 目标材料 ID（由材料关联推导）
        mat_rows = await src.fetch(
            """
            SELECT DISTINCT material_id AS id
            FROM fba.study_question_material_relation
            WHERE question_id = ANY($1::bigint[])
            ORDER BY 1
            """,
            qids,
        )
        mids = [r['id'] for r in mat_rows]
        print(f'目标材料：{len(mids)} 份 → {mids}')

        async with dst.transaction():
            # 1) 题目（跳过 content_vector）
            await copy_table(
                src, dst, 'study_question',
                """
                SELECT id, type, stem, difficulty::text AS difficulty, default_score::text AS default_score,
                       knowledge_point::text AS knowledge_point, options::text AS options,
                       content_status, created_by, updated_by, created_time, updated_time,
                       deleted, deleted_time
                FROM fba.study_question WHERE id = ANY($1::bigint[])
                """,
                [qids],
                """
                INSERT INTO public.study_question
                    (id, type, stem, difficulty, default_score, knowledge_point, options,
                     content_status, created_by, updated_by, created_time, updated_time, deleted, deleted_time)
                VALUES ($1,$2,$3,$4::numeric,$5::numeric,$6::jsonb,$7::jsonb,$8,$9,$10,$11,$12,$13,$14)
                ON CONFLICT (id) DO NOTHING
                """,
                ['id', 'type', 'stem', 'difficulty', 'default_score', 'knowledge_point', 'options',
                 'content_status', 'created_by', 'updated_by', 'created_time', 'updated_time', 'deleted', 'deleted_time'],
            )

            # 2) 材料
            await copy_table(
                src, dst, 'study_question_material',
                """
                SELECT id, bank_id, title, content, category_id, source, year, sort_order, is_active,
                       created_by, updated_by, created_time, updated_time, deleted, deleted_time
                FROM fba.study_question_material WHERE id = ANY($1::bigint[])
                """,
                [mids],
                """
                INSERT INTO public.study_question_material
                    (id, bank_id, title, content, category_id, source, year, sort_order, is_active,
                     created_by, updated_by, created_time, updated_time, deleted, deleted_time)
                VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15)
                ON CONFLICT (id) DO NOTHING
                """,
                ['id', 'bank_id', 'title', 'content', 'category_id', 'source', 'year', 'sort_order', 'is_active',
                 'created_by', 'updated_by', 'created_time', 'updated_time', 'deleted', 'deleted_time'],
            )

            # 3) 解析
            await copy_table(
                src, dst, 'study_question_analysis',
                """
                SELECT id, question_id, answer_data::text AS answer_data, content, type, version_no,
                       is_default, view_count, helpful_count, unhelpful_count, status,
                       created_by, updated_by, created_time, updated_time, deleted, deleted_time
                FROM fba.study_question_analysis WHERE question_id = ANY($1::bigint[])
                """,
                [qids],
                """
                INSERT INTO public.study_question_analysis
                    (id, question_id, answer_data, content, type, version_no, is_default,
                     view_count, helpful_count, unhelpful_count, status,
                     created_by, updated_by, created_time, updated_time, deleted, deleted_time)
                VALUES ($1,$2,$3::jsonb,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17)
                ON CONFLICT (id) DO NOTHING
                """,
                ['id', 'question_id', 'answer_data', 'content', 'type', 'version_no', 'is_default',
                 'view_count', 'helpful_count', 'unhelpful_count', 'status',
                 'created_by', 'updated_by', 'created_time', 'updated_time', 'deleted', 'deleted_time'],
            )

            # 4) 材料关联（无独立主键，冲突以复合主键判断）
            await copy_table(
                src, dst, 'study_question_material_relation',
                """
                SELECT question_id, material_id, sort_order
                FROM fba.study_question_material_relation WHERE question_id = ANY($1::bigint[])
                """,
                [qids],
                """
                INSERT INTO public.study_question_material_relation (question_id, material_id, sort_order)
                VALUES ($1,$2,$3)
                ON CONFLICT (question_id, material_id) DO NOTHING
                """,
                ['question_id', 'material_id', 'sort_order'],
            )

            # 5) 挂载
            await copy_table(
                src, dst, 'study_question_placement',
                """
                SELECT id, question_id, bank_id, chapter_id, sort_order, is_active, score::text AS score,
                       review_status, scene_mask, created_by, updated_by, created_time, updated_time, deleted, deleted_time
                FROM fba.study_question_placement WHERE chapter_id = $1 AND bank_id = ANY($2::bigint[])
                """,
                [CHAPTER_ID, list(PLACEMENT_BANKS)],
                """
                INSERT INTO public.study_question_placement
                    (id, question_id, bank_id, chapter_id, sort_order, is_active, score, review_status, scene_mask,
                     created_by, updated_by, created_time, updated_time, deleted, deleted_time)
                VALUES ($1,$2,$3,$4,$5,$6,$7::numeric,$8,$9,$10,$11,$12,$13,$14,$15)
                ON CONFLICT (id) DO NOTHING
                """,
                ['id', 'question_id', 'bank_id', 'chapter_id', 'sort_order', 'is_active', 'score', 'review_status', 'scene_mask',
                 'created_by', 'updated_by', 'created_time', 'updated_time', 'deleted', 'deleted_time'],
            )

        print('迁移完成，事务已提交')
    finally:
        await src.close()
        await dst.close()


if __name__ == '__main__':
    asyncio.run(main())
