#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
批��修复题目状态脚本

使用方法：
    python scripts/fix_question_status.py

功能：
    批量将所有题目的状态设置为��
    - is_active = True
    - review_status = 10（已通过）
"""
import asyncio
import sys
from pathlib import Path

# 添加项目路径到 sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import func, select, update

from backend.app.question_bank.model import Question
from backend.database.db_postgresql import async_engine, async_session


async def fix_questions():
    """批量修复题目状态"""
    print('\n' + '=' * 70)
    print('🔧 题目状态批量修复工具')
    print('=' * 70 + '\n')

    async with async_session() as db:
        # 1. 检查需要修复的题目数量
        result = await db.execute(
            select(func.count(Question.id)).where((Question.is_active == False) | (Question.review_status != 10))
        )
        need_fix_count = result.scalar_one()

        if need_fix_count == 0:
            print('✅ 没有需要修复的题目，所有题目状态正常！\n')
            return

        print(f'📝 发现 {need_fix_count} 道题目需要修复\n')

        # 2. 确认是否继续
        response = input('是否继续修复？将批量设置为：启用 + 审核通过 (y/n): ')
        if response.lower() != 'y':
            print('\n❌ 操作已取消\n')
            return

        # 3. 批量更新
        print('\n正在修复...')

        # 更新 is_active=False 的题目
        stmt = update(Question).where(Question.is_active == False).values(is_active=True)
        result = await db.execute(stmt)
        inactive_fixed = result.rowcount

        # 更新 review_status!=10 的题目
        stmt = update(Question).where(Question.review_status != 10).values(review_status=10)
        result = await db.execute(stmt)
        review_fixed = result.rowcount

        await db.commit()

        # 4. 显示结果
        print('\n' + '-' * 70)
        print('✅ 修复完成！\n')
        print(f'  启用状态修复: {inactive_fixed} 道题目')
        print(f'  审核状态修复: {review_fixed} 道题目')
        print('-' * 70 + '\n')

        # 5. 验证修复结果
        result = await db.execute(
            select(func.count(Question.id)).where(Question.is_active == True, Question.review_status == 10)
        )
        available_count = result.scalar_one()

        result = await db.execute(select(func.count(Question.id)))
        total_count = result.scalar_one()

        print('📊 修复后统计：')
        print(f'  题目总数: {total_count}')
        print(f'  可刷题目: {available_count}')
        print(f'  被过滤题目: {total_count - available_count}\n')

        if available_count == total_count:
            print('🎉 所有题目现在都可以在小程序中刷题了！\n')
        else:
            print('⚠️  仍有部分题目被过滤，请运行检查脚本查看详情：')
            print('    python scripts/check_question_status.py\n')


async def main():
    """主函数"""
    try:
        await fix_questions()
    except Exception as e:
        print(f'\n❌ 修复失败: {e}')
        import traceback

        traceback.print_exc()
    finally:
        await async_engine.dispose()


if __name__ == '__main__':
    asyncio.run(main())
