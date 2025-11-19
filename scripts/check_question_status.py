#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
检查题目状态脚本 - 排查刷题界面题目不显示问题

使用方法：
    python scripts/check_question_status.py

功能：
    1. 检查数据���中的题目总数
    2. 检查每个题库的题目数量和状态分布
    3. 找出被过滤掉的题目（is_active=False 或 review_status!=10）
    4. 提供批量修复建议
"""
import asyncio
import sys
from pathlib import Path

# 添加项目路径到 sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import func, select

from backend.app.question_bank.model import Question, QuestionBank
from backend.database.db_postgresql import async_engine
from backend.database.db_postgresql import async_session


async def check_questions():
    """检查题目状态"""
    print('\n' + '=' * 70)
    print('📊 题目状态检查工具')
    print('=' * 70 + '\n')

    async with async_session() as db:
        # 1. 统计所有题目
        result = await db.execute(select(func.count(Question.id)))
        total_count = result.scalar_one()

        print(f'📝 数据库中题目总数: {total_count}')

        if total_count == 0:
            print('\n❌ 数据库中没有任何题目！')
            print('💡 请先通过管理端创建题目。\n')
            return

        # 2. 统计可用题目（is_active=True AND review_status=10）
        result = await db.execute(
            select(func.count(Question.id)).where(Question.is_active == True, Question.review_status == 10)
        )
        available_count = result.scalar_one()

        print(f'✅ 可刷题目数量: {available_count}')
        print(f'⚠️  被过滤题目数量: {total_count - available_count}\n')

        # 3. 按题库统计
        print('-' * 70)
        print('📚 各题库题目统计：\n')

        # 获取所有题库
        result = await db.execute(select(QuestionBank).where(QuestionBank.is_active == True))
        banks = result.scalars().all()

        for bank in banks:
            # 统计该题库的题目
            result = await db.execute(select(func.count(Question.id)).where(Question.bank_id == bank.id))
            bank_total = result.scalar_one()

            # 统计可用题目
            result = await db.execute(
                select(func.count(Question.id)).where(
                    Question.bank_id == bank.id, Question.is_active == True, Question.review_status == 10
                )
            )
            bank_available = result.scalar_one()

            status = '✅' if bank_available > 0 else '❌'
            print(f'{status} 题库 [{bank.id}] {bank.name}')
            print(f'   总题目: {bank_total}, 可刷题: {bank_available}, 被过滤: {bank_total - bank_available}')

        # 4. 统计被过滤的原因
        print('\n' + '-' * 70)
        print('🔍 被过滤题目详情：\n')

        # 统计 is_active=False 的题目
        result = await db.execute(select(func.count(Question.id)).where(Question.is_active == False))
        inactive_count = result.scalar_one()

        # 统计 review_status!=10 的题目
        result = await db.execute(select(func.count(Question.id)).where(Question.review_status != 10))
        not_reviewed_count = result.scalar_one()

        print(f'❌ is_active = False 的题目: {inactive_count}')
        print(f'⏳ review_status != 10 的题目: {not_reviewed_count}')

        # 5. 显示具体被过滤的题目
        if total_count - available_count > 0:
            print('\n' + '-' * 70)
            print('📋 被过滤题目列表（前 10 条）：\n')

            # 查询被过滤的题目
            stmt = (
                select(Question)
                .where((Question.is_active == False) | (Question.review_status != 10))
                .limit(10)
            )
            result = await db.execute(stmt)
            filtered_questions = result.scalars().all()

            for q in filtered_questions:
                active_status = '✅ 已启用' if q.is_active else '❌ 已禁用'
                review_statuses = {0: '⏳ 待审核', 10: '✅ 已通过', 20: '❌ 已拒绝'}
                review_status = review_statuses.get(q.review_status, f'❓ 未知({q.review_status})')

                stem_preview = q.stem[:50] + '...' if len(q.stem) > 50 else q.stem

                print(f'题目 ID: {q.id}')
                print(f'  题干: {stem_preview}')
                print(f'  状态: {active_status} | 审核: {review_status}')
                print()

        # 6. 提供修复建议
        if total_count - available_count > 0:
            print('-' * 70)
            print('🔧 修复建议：\n')
            print('方式 1: 使用修复脚本（推荐）')
            print('  python scripts/fix_question_status.py\n')
            print('方式 2: 手动修复（适合少量题目）')
            print('  通过管理端逐个编辑题目，设置：')
            print('  - 启用状态��是')
            print('  - 审核状态：已通过\n')
        else:
            print('\n' + '=' * 70)
            print('🎉 所有题目状态正常！')
            print('=' * 70 + '\n')

            print('💡 如果小程序仍然看不到题目，请检查：')
            print('  1. 小程序是否已登录（测试登录或微信登录）')
            print('  2. 浏览器控制台是否有错误信息')
            print('  3. 后端日志是否有异常')
            print('  4. 传递的 bankId 参数是否正确\n')


async def main():
    """主函数"""
    try:
        await check_questions()
    except Exception as e:
        print(f'\n❌ 检查失败: {e}')
        import traceback

        traceback.print_exc()
    finally:
        await async_engine.dispose()


if __name__ == '__main__':
    asyncio.run(main())
