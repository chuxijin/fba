#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
题目全量向量化脚本

将 study_question 中所有 content_vector IS NULL 的题目向量化（题干 + 选项）。
支持断点续跑、进度显示、限速控制。

用法:
    cd backend
    python -m scripts.qbank_vectorize_questions                # 全量
    python -m scripts.qbank_vectorize_questions --limit 1000   # 只跑 1000 题
    python -m scripts.qbank_vectorize_questions --dry-run      # 预览，不写入
"""
import argparse
import asyncio
import logging
import re
import sys
import time

from pathlib import Path

from sqlalchemy import text

# 确保项目根目录在 sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.database.db import async_db_session
from backend.utils.embedding import batch_embed

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S',
)
log = logging.getLogger('vectorize')

# ============ 常量 ============

# 单次 Embedding API 调用的文本条数
EMBED_BATCH_SIZE = 100

# 单次从数据库取多少题 → 清洗 → 调 API → 批量 UPDATE → commit
DB_BATCH_SIZE = 500

# API 调用间隔（秒），用于控制速率
API_INTERVAL = 0.2

# HTML 标签清洗正则
HTML_TAG_RE = re.compile(r'<[^>]+>')
MULTI_SPACE_RE = re.compile(r'\s+')


# ============ 工具函数 ============

def strip_html(html: str) -> str:
    """
    清洗 HTML 标签，提取纯文本

    :param html: 含 HTML 标签的字符串
    :return:
    """
    if not html:
        return ''
    cleaned = HTML_TAG_RE.sub(' ', html)
    cleaned = MULTI_SPACE_RE.sub(' ', cleaned).strip()
    return cleaned


def build_embed_text(stem: str, options: list[str] | None) -> str:
    """
    拼接题干 + 选项为 Embedding 输入文本

    :param stem: 原始题干（含 HTML）
    :param options: 选项内容列表（含 HTML），可为空
    :return:
    """
    parts = [strip_html(stem)]
    if options:
        for i, opt in enumerate(options):
            label = chr(65 + i)  # A, B, C, D ...
            parts.append(f'{label}. {strip_html(opt)}')
    return '\n'.join(parts)


# ============ 核心逻辑 ============

async def fetch_pending_batch(db, limit: int) -> list[dict]:
    """
    获取一批未向量化的题目（含选项）

    :param db: 数据库会话
    :param limit: 最多取多少题
    :return:
    """
    result = await db.execute(text("""
        SELECT
            q.id,
            q.stem,
            array_agg(option_item.content ORDER BY option_item.sort_order, option_item.option_code)
                FILTER (WHERE option_item.content IS NOT NULL) AS options
        FROM study_question q
        LEFT JOIN LATERAL (
            SELECT
                item ->> 'option_code' AS option_code,
                item ->> 'content' AS content,
                COALESCE((item ->> 'sort_order')::int, 0) AS sort_order
            FROM jsonb_array_elements(COALESCE(q.options, '[]'::jsonb)) AS item
            WHERE COALESCE((item ->> 'is_active')::boolean, true) = true
        ) AS option_item ON true
        WHERE q.content_vector IS NULL
        GROUP BY q.id, q.stem
        ORDER BY q.id
        LIMIT :limit
    """), {'limit': limit})

    return [
        {'id': row[0], 'stem': row[1], 'options': row[2]}
        for row in result.all()
    ]


async def update_vectors(db, id_vector_pairs: list[tuple[int, list[float]]]) -> int:
    """
    批量更新题目向量

    :param db: 数据库会话
    :param id_vector_pairs: [(question_id, vector), ...]
    :return:
    """
    if not id_vector_pairs:
        return 0

    # 逐条更新（pgvector 的 vector 类型不支持 executemany 批量绑定）
    for qid, vec in id_vector_pairs:
        vec_str = '[' + ','.join(str(v) for v in vec) + ']'
        await db.execute(
            text('UPDATE study_question SET content_vector = :vec WHERE id = :qid'),
            {'vec': vec_str, 'qid': qid},
        )

    return len(id_vector_pairs)


async def process_batch(db, questions: list[dict], dry_run: bool = False) -> dict:
    """
    处理一个批次的题目：清洗 → Embedding → 写入

    :param db: 数据库会话
    :param questions: 题目列表
    :param dry_run: 是否只预览不写入
    :return:
    """
    stats = {'total': len(questions), 'success': 0, 'skipped': 0, 'failed': 0}

    # 1. 清洗文本
    texts = []
    valid_questions = []
    for q in questions:
        embed_text = build_embed_text(q['stem'], q['options'])
        if len(embed_text.strip()) < 5:
            log.warning(f'题目 id={q["id"]} 清洗后文本过短，跳过')
            stats['skipped'] += 1
            continue
        texts.append(embed_text)
        valid_questions.append(q)

    if not texts:
        return stats

    if dry_run:
        for q, t in zip(valid_questions, texts):
            log.info(f'[DRY-RUN] id={q["id"]}: {t[:80]}...')
        stats['success'] = len(texts)
        return stats

    # 2. 调 Embedding API（内部按 EMBED_BATCH_SIZE 分批）
    try:
        vectors = await batch_embed(texts, batch_size=EMBED_BATCH_SIZE)
    except Exception as e:
        log.error(f'Embedding API 调用失败: {e}')
        stats['failed'] = len(texts)
        return stats

    # 3. 验证维度
    expected_dim = 1536
    id_vector_pairs = []
    for q, vec in zip(valid_questions, vectors):
        if len(vec) != expected_dim:
            log.error(f'题目 id={q["id"]} 向量维度异常: {len(vec)} != {expected_dim}')
            stats['failed'] += 1
            continue
        id_vector_pairs.append((q['id'], vec))

    # 4. 写入数据库
    try:
        updated = await update_vectors(db, id_vector_pairs)
        stats['success'] = updated
    except Exception as e:
        log.error(f'数据库写入失败: {e}')
        stats['failed'] += len(id_vector_pairs)

    return stats


async def get_progress(db) -> dict:
    """查询向量化进度"""
    result = await db.execute(text("""
        SELECT
            COUNT(*) AS total,
            COUNT(content_vector) AS done,
            COUNT(*) - COUNT(content_vector) AS pending
        FROM study_question
    """))
    row = result.one()
    return {'total': row[0], 'done': row[1], 'pending': row[2]}


async def main(limit: int | None = None, dry_run: bool = False) -> None:
    """
    主入口：分批处理所有未向量化的题目

    :param limit: 最多处理多少题（None 表示全量）
    :param dry_run: 是否只预览不写入
    :return:
    """
    start_time = time.time()

    async with async_db_session() as db:
        # 初始进度
        progress = await get_progress(db)
        log.info(
            f'题目总量: {progress["total"]}, '
            f'已完成: {progress["done"]}, '
            f'待处理: {progress["pending"]}'
        )

        if progress['pending'] == 0:
            log.info('所有题目已完成向量化，无需处理')
            return

        remaining = limit or progress['pending']
        total_success = 0
        total_skipped = 0
        total_failed = 0
        batch_no = 0

        while remaining > 0:
            batch_size = min(DB_BATCH_SIZE, remaining)
            questions = await fetch_pending_batch(db, batch_size)

            if not questions:
                log.info('没有更多待处理的题目')
                break

            batch_no += 1
            log.info(
                f'--- 批次 {batch_no} ---  '
                f'本批 {len(questions)} 题  '
                f'(id {questions[0]["id"]} ~ {questions[-1]["id"]})'
            )

            stats = await process_batch(db, questions, dry_run=dry_run)
            total_success += stats['success']
            total_skipped += stats['skipped']
            total_failed += stats['failed']
            remaining -= len(questions)

            if not dry_run:
                await db.commit()

            elapsed = time.time() - start_time
            done_so_far = total_success + total_skipped + total_failed
            speed = done_so_far / elapsed if elapsed > 0 else 0
            log.info(
                f'累计: 成功={total_success}, 跳过={total_skipped}, 失败={total_failed}  '
                f'速度: {speed:.0f} 题/秒  '
                f'剩余: {remaining}'
            )

            # API 限速间隔
            await asyncio.sleep(API_INTERVAL)

    elapsed = time.time() - start_time
    log.info(
        f'\n====== 完成 ======\n'
        f'总耗时: {elapsed:.1f}s\n'
        f'成功: {total_success}\n'
        f'跳过: {total_skipped}\n'
        f'失败: {total_failed}'
    )


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='题目全量向量化脚本')
    parser.add_argument('--limit', type=int, default=None, help='最多处理多少题（默认全量）')
    parser.add_argument('--dry-run', action='store_true', help='只预览不写入')
    args = parser.parse_args()

    asyncio.run(main(limit=args.limit, dry_run=args.dry_run))
