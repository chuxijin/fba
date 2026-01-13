#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
调试答案判断问题

模拟前后端的完整流程，找出答案判断错误的根源
"""
import asyncio
from sqlalchemy import select
from backend.database.db import async_db_session
from backend.app.question_bank.model.question import Question, QuestionAnalysis


async def debug_answer_checking():
    """调试答案判断流程"""
    async with async_db_session() as db:
        # 查询 ID=4 的判断题
        stmt = (
            select(Question, QuestionAnalysis)
            .join(QuestionAnalysis, Question.id == QuestionAnalysis.question_id)
            .where(Question.id == 4)
        )
        result = await db.execute(stmt)
        row = result.first()

        if not row:
            print('❌ 未找到 ID=4 的题目')
            return

        q, a = row

        print('=' * 60)
        print(f'题目 ID: {q.id}')
        print(f'题型: {q.type}')
        print(f'题干: {q.stem[:50]}...')
        print('=' * 60)

        # 1. 检查 options_data 的类型和值
        print('\n【步骤1】检查 options_data:')
        print(f'  类型: {type(q.options_data)}')
        print(f'  值: {repr(q.options_data)}')
        if isinstance(q.options_data, str):
            print('  ❌ WARNING: options_data 是字符串而不是 dict/None!')
        print('=' * 60)

        # 2. 检查 answer_data
        print('\n【步骤2】检查 answer_data:')
        print(f'  原始数据: {a.answer_data}')
        correct_answer = a.answer_data.get('correct')
        print(f'  正确答案: {repr(correct_answer)} (类型: {type(correct_answer).__name__})')
        print('=' * 60)

        # 3. 模拟后端 API 返回
        print('\n【步骤3】模拟后端 getSolution API 返回:')

        # 模拟 options 转换（存在bug的版本）
        if q.options_data:
            print(f'  q.options_data 为真值: {bool(q.options_data)}')
            if isinstance(q.options_data, dict):
                options_list = list(q.options_data.values())
                print(f'  options_list (dict转换): {options_list}')
            elif isinstance(q.options_data, str):
                print(f'  ❌ ERROR: 尝试对字符串 "{q.options_data}" 调用 .values() 会报错!')
                print(f'  Object.values() 会返回: {list(q.options_data)}')  # Python模拟JS的Object.values
        else:
            print(f'  q.options_data 为假值，options_list = None')

        print('\n  后端返回的 QuestionSolution:')
        solution_data = {
            'question_id': q.id,
            'content': q.stem,
            'type': q.type,
            'options': None,  # 判断题可能是 None
            'correct_answer': correct_answer,
            'analysis': a.content,
        }
        print(f'  {solution_data}')
        print('=' * 60)

        # 4. 模拟前端适配器
        print('\n【步骤4】模拟前端适配器 (question-adapter-v2.ts):')
        print(f'  题型检测: type === "judgement" → {q.type == "judgement"}')

        if q.type == 'judgement':
            print('  固定选项生成:')
            options = [
                {'label': 'A', 'content': '正确', 'is_correct': correct_answer == 'A'},
                {'label': 'B', 'content': '错误', 'is_correct': correct_answer == 'B'},
            ]
            for opt in options:
                print(f'    {opt}')

            print(f'\n  转换后的 baseQuestion.answer: {repr(correct_answer)}')
        print('=' * 60)

        # 5. 模拟用户答题
        print('\n【步骤5】模拟用户选择 A 选项:')
        user_answer = 'A'
        print(f'  用户答案: {repr(user_answer)}')
        print(f'  正确答案: {repr(correct_answer)}')

        # 模拟前端判题逻辑
        print('\n  前端判题逻辑 (checkAnswer):')
        print(f'    userAnswer.trim(): "{user_answer.strip()}"')
        print(f'    correctAnswer.trim(): "{correct_answer.strip() if correct_answer else None}"')

        if correct_answer:
            is_correct = user_answer.strip().upper() == correct_answer.strip().upper()
            print(f'    比较结果: {is_correct}')
            print(f'    判定: {"✅ 正确" if is_correct else "❌ 错误"}')
        else:
            print(f'    ❌ ERROR: correctAnswer 是 None/undefined!')
        print('=' * 60)


if __name__ == '__main__':
    asyncio.run(debug_answer_checking())
