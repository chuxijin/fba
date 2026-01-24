#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
快速刷新指定科目的资源为永久链接

使用方法：
    python scripts/refresh_subject_permanent.py "26考研数学"

或者在 Python 中直接调用：
    from scripts.refresh_subject_permanent import refresh_subject
    import asyncio
    asyncio.run(refresh_subject("26考研数学"))
"""
import asyncio
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from backend.database.db import async_db_session


async def refresh_subject(subject: str) -> dict:
    """
    刷新指定科目的资源为永久链接

    :param subject: 科目名称
    :return: 执行结果
    """
    print(f"🚀 开始刷新科目: {subject}")
    print("-" * 50)

    async with async_db_session() as db:
        from backend.app.coulddrive.service.resource_service import resource_service

        result = await resource_service.refresh_to_permanent(
            db=db,
            subject=subject
        )

        # 打印结果
        print(f"✅ 刷新完成!")
        print(f"   检查资源数: {result.get('checked_resources', 0)}")
        print(f"   刷新成功数: {result.get('refreshed_resources', 0)}")
        print(f"   刷新失败数: {result.get('failed_resources', 0)}")
        print(f"   跳过资源数: {result.get('skipped_resources', 0)}")

        if result.get('error'):
            print(f"❌ 错误: {result['error']}")

        return result


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python scripts/refresh_subject_permanent.py <科目名称>")
        print("示例: python scripts/refresh_subject_permanent.py 26考研数学")
        sys.exit(1)

    subject = sys.argv[1]
    asyncio.run(refresh_subject(subject))
