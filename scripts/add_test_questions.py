#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
添加测试题目数据
"""
import asyncio
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import select
from backend.database.db import async_db_session
from backend.app.question_bank.model.question import Question
from backend.app.question_bank.model.bank import QuestionBank


async def add_test_questions():
    """
    添加测试题目数据
    """
    async with async_db_session.begin() as db:
        # 检查是否有题库
        result = await db.execute(select(QuestionBank).limit(1))
        bank = result.scalar_one_or_none()

        if not bank:
            print("错误：没有找到题库，请先创建题库")
            return

        print(f"找到题库：{bank.name} (ID: {bank.id})")

        # 检查是否已有题目
        result = await db.execute(
            select(Question).where(Question.bank_id == bank.id).limit(1)
        )
        existing = result.scalar_one_or_none()

        if existing:
            print("题库中已有题目，跳过添加")
            return

        # 添加 50 个测试题目
        questions = []
        for i in range(1, 51):
            question = Question(
                bank_id=bank.id,
                type_id=1,  # 选择题
                stem=f"这是第 {i} 道测试题目，用于测试分页功能。题目内容：{i * 111}",
                score=2.0,
                is_active=True,
                answer_text=f"答案 {i}",
                created_by=1,  # 假设管理员 ID 为 1
            )
            questions.append(question)

        db.add_all(questions)
        await db.commit()

        print(f"成功添加 {len(questions)} 道测试题目")


if __name__ == "__main__":
    asyncio.run(add_test_questions())
