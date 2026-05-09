#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import asyncio
import sys

from pathlib import Path
from typing import NamedTuple

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.question_bank.model import QuestionChapter, QuestionPlacement
from backend.database.db import async_db_session


QUESTION_TYPE_CHAPTER_NAMES = {
    '单选',
    '单选题',
    '多选',
    '多选题',
    '判断',
    '判断题',
    '填空',
    '填空题',
    '简答',
    '简答题',
}


class RepairCandidate(NamedTuple):
    """待修复题型章节"""

    child_id: int
    child_name: str
    parent_id: int
    parent_name: str
    bank_id: int
    placement_count: int


async def collect_candidates(db: AsyncSession, bank_id: int | None) -> list[RepairCandidate]:
    """
    收集挂载到题型章节的题目

    :param db: 数据库会话
    :param bank_id: 题库 ID
    :return:
    """
    parent = aliased(QuestionChapter)
    stmt = (
        select(
            QuestionChapter.id.label('child_id'),
            QuestionChapter.name.label('child_name'),
            QuestionChapter.parent_id.label('parent_id'),
            parent.id.label('parent_order_id'),
            parent.name.label('parent_name'),
            QuestionChapter.bank_id.label('bank_id'),
            func.count(QuestionPlacement.id).label('placement_count'),
        )
        .join(parent, parent.id == QuestionChapter.parent_id)
        .join(QuestionPlacement, QuestionPlacement.chapter_id == QuestionChapter.id)
        .where(
            QuestionChapter.parent_id.is_not(None),
            QuestionChapter.name.in_(QUESTION_TYPE_CHAPTER_NAMES),
        )
        .group_by(
            QuestionChapter.id,
            QuestionChapter.name,
            QuestionChapter.parent_id,
            parent.id,
            parent.name,
            QuestionChapter.bank_id,
        )
        .order_by(QuestionChapter.bank_id, parent.id, QuestionChapter.id)
    )
    if bank_id is not None:
        stmt = stmt.where(QuestionChapter.bank_id == bank_id)

    rows = (await db.execute(stmt)).all()
    return [
        RepairCandidate(
            child_id=int(row.child_id),
            child_name=str(row.child_name),
            parent_id=int(row.parent_id),
            parent_name=str(row.parent_name),
            bank_id=int(row.bank_id),
            placement_count=int(row.placement_count),
        )
        for row in rows
    ]


async def recalculate_chapter_caches(db: AsyncSession, bank_ids: set[int]) -> None:
    """
    重算章节直接题量缓存

    :param db: 数据库会话
    :param bank_ids: 题库 ID 集合
    """
    count_subquery = (
        select(func.count(QuestionPlacement.id))
        .where(QuestionPlacement.chapter_id == QuestionChapter.id)
        .scalar_subquery()
    )
    await db.execute(
        update(QuestionChapter)
        .where(QuestionChapter.bank_id.in_(bank_ids))
        .values(q_count_cache=count_subquery)
    )


async def delete_empty_type_chapters(db: AsyncSession, child_ids: list[int]) -> int:
    """
    删除已无题目的题型章节

    :param db: 数据库会话
    :param child_ids: 章节 ID 列表
    :return:
    """
    if not child_ids:
        return 0

    children_alias = aliased(QuestionChapter)
    chapters_with_children = (
        select(children_alias.parent_id)
        .where(children_alias.parent_id.in_(child_ids))
        .subquery()
    )
    stmt = (
        delete(QuestionChapter)
        .where(
            QuestionChapter.id.in_(child_ids),
            ~QuestionChapter.id.in_(select(chapters_with_children.c.parent_id)),
            ~QuestionChapter.placements.any(),
        )
        .execution_options(synchronize_session=False)
    )
    result = await db.execute(stmt)
    return int(result.rowcount or 0)


async def repair_question_type_chapters(
    *,
    bank_id: int | None,
    commit: bool,
    delete_empty: bool,
) -> None:
    """
    修复题型章节挂载

    :param bank_id: 题库 ID
    :param commit: 是否提交修改
    :param delete_empty: 是否删除空题型章节
    """
    async with async_db_session() as db:
        candidates = await collect_candidates(db=db, bank_id=bank_id)
        if not candidates:
            print('没有发现挂载到题型章节的题目')
            return

        total = sum(item.placement_count for item in candidates)
        print(f'发现 {len(candidates)} 个题型章节，涉及 {total} 条题目挂载')
        for item in candidates:
            print(
                f'- bank={item.bank_id} {item.parent_name} <- {item.child_name} '
                f'chapter_id={item.child_id} placements={item.placement_count}'
            )

        if not commit:
            print('当前为 dry-run，未写入数据库；确认后追加 --commit 执行修复')
            return

        for item in candidates:
            await db.execute(
                update(QuestionPlacement)
                .where(QuestionPlacement.chapter_id == item.child_id)
                .values(chapter_id=item.parent_id)
            )

        bank_ids = {item.bank_id for item in candidates}
        await recalculate_chapter_caches(db=db, bank_ids=bank_ids)

        deleted_count = 0
        if delete_empty:
            deleted_count = await delete_empty_type_chapters(
                db=db,
                child_ids=[item.child_id for item in candidates],
            )

        await db.commit()
        print(f'修复完成：已迁移 {total} 条挂载，重算 {len(bank_ids)} 个题库的章节题量缓存')
        if delete_empty:
            print(f'已删除 {deleted_count} 个空题型章节')


def parse_args() -> argparse.Namespace:
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description='修复题库中误挂到题型章节的题目')
    parser.add_argument('--bank-id', type=int, default=None, help='只修复指定题库 ID')
    parser.add_argument('--commit', action='store_true', help='提交数据库修改，默认只预览')
    parser.add_argument('--delete-empty', action='store_true', help='迁移后删除空题型章节')
    return parser.parse_args()


async def main() -> None:
    """执行修复脚本"""
    args = parse_args()
    await repair_question_type_chapters(
        bank_id=args.bank_id,
        commit=args.commit,
        delete_empty=args.delete_empty,
    )


if __name__ == '__main__':
    asyncio.run(main())
