#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""测试汉语词汇频次统计任务"""

import asyncio
import sys

from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from backend.app.task.tasks.gongkao.tasks import update_hanyu_frequency


async def main():
    """主函数"""
    print('=' * 60)
    print('汉语词汇频次统计任务测试')
    print('=' * 60)
    print()
    print('⏳ 开始执行任务...')
    print()

    result = await update_hanyu_frequency()

    print()
    print('=' * 60)
    print('执行结果')
    print('=' * 60)
    print(f'✅ 执行状态: {"成功" if result["success"] else "失败"}')
    print(f'📊 成语总数: {result["total_count"]}')
    print(f'🔄 更新记录: {result["updated_count"]}')
    print(f'❌ 错误数量: {result["error_count"]}')
    print(f'⏱️  执行耗时: {result["elapsed_seconds"]} 秒')
    print()
    print(f'💬 消息: {result["message"]}')
    print('=' * 60)


if __name__ == '__main__':
    asyncio.run(main())
