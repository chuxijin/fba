#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
检查题目是否有选项
"""
import asyncio

from sqlalchemy import select

from backend.app.question_bank.model import Question, QuestionOption
from backend.database.db import async_db_session


async def check_options():
    """检查题目选项"""
    async with async_db_session() as db:
        # 查询前5个启用的题目
        stmt = select(Question).where(Question.is_active == True).limit(5)
        result = await db.execute(stmt)
        questions = result.scalars().all()

        print(f'\n📊 找到 {len(questions)} 个启用的题目\n')

        for q in questions:
            print(f'题目 ID: {q.id}')
            print(f'题干: {q.stem[:50]}...' if len(q.stem) > 50 else f'题干: {q.stem}')
            print(f'题型 ID: {q.type_id}')
            print(f'选择题类型: {q.choice_type}')

            # 查询该题目的选项
            stmt_opt = select(QuestionOption).where(QuestionOption.question_id == q.id)
            result_opt = await db.execute(stmt_opt)
            options = result_opt.scalars().all()

            print(f'选项数量: {len(options)}')
            if options:
                for opt in options:
                    print(f'  - {opt.label}: {opt.content}')
            else:
                print('  ⚠️ 该题目没有选项！')
            print('-' * 60)


if __name__ == '__main__':
    asyncio.run(check_options())
