#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
修复 options_data 中的字符串 'null' 问题

将判断题的 options_data 从字符串 'null' 修正为 NULL
"""
import asyncio
from sqlalchemy import update, select
from backend.database.db import async_db_session
from backend.app.question_bank.model.question import Question


async def fix_null_options_data():
    """修复 options_data = 'null' 字符串的问题"""
    async with async_db_session() as db:
        # 查询所有 options_data 是字符串 'null' 的题目
        stmt = select(Question).where(Question.options_data == 'null')
        result = await db.execute(stmt)
        questions = result.scalars().all()

        print(f'找到 {len(questions)} 道题目的 options_data 是字符串 "null"')

        if questions:
            print('\n这些题目的类型分布：')
            type_count = {}
            for q in questions:
                type_count[q.type] = type_count.get(q.type, 0) + 1
            for qtype, count in type_count.items():
                print(f'  {qtype}: {count} 道')

            # 更新为 NULL
            update_stmt = (
                update(Question)
                .where(Question.options_data == 'null')
                .values(options_data=None)
            )
            await db.execute(update_stmt)
            await db.commit()
            print(f'\n✅ 已将 {len(questions)} 道题目的 options_data 修正为 NULL')
        else:
            print('✅ 没有需要修复的数据')


if __name__ == '__main__':
    asyncio.run(fix_null_options_data())
