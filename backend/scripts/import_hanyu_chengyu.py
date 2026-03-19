#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import asyncio
import json
from pathlib import Path

from sqlalchemy import select

from backend.app.gongkao.model import GkHanyu
from backend.database.db import async_db_session


async def import_chengyu_from_json(json_file: str, batch_size: int = 100):
    """
    从 JSON 文件导入成语数据

    :param json_file: JSON 文件路径
    :param batch_size: 批量插入大小
    """
    file_path = Path(json_file)
    if not file_path.exists():
        print(f'❌ 文件不存在: {json_file}')
        return

    print(f'📖 读取文件: {json_file}')
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    if not isinstance(data, list):
        print('❌ JSON 数据格式错误，应该是数组')
        return

    print(f'📊 共读取 {len(data)} 条成语数据')

    async with async_db_session.begin() as db:
        existing_names = set()
        stmt = select(GkHanyu.name).where(GkHanyu.type == '成语')
        result = await db.execute(stmt)
        existing_names = {row[0] for row in result.all()}
        print(f'📌 数据库中已存在 {len(existing_names)} 条成语')

        batch = []
        created_count = 0
        skipped_count = 0

        for idx, item in enumerate(data, 1):
            name = item.get('word') or item.get('name') or item.get('成语')
            if not name:
                print(f'⚠️  第 {idx} 条数据缺少名称字段，跳过')
                skipped_count += 1
                continue

            if name in existing_names:
                skipped_count += 1
                continue

            hanyu = GkHanyu(
                name=name,
                type='成语',
                frequency=0,
                created_by=1,
            )
            batch.append(hanyu)
            existing_names.add(name)

            if len(batch) >= batch_size:
                db.add_all(batch)
                await db.flush()
                created_count += len(batch)
                print(f'✅ 已导入 {created_count} 条成语 ({idx}/{len(data)})')
                batch = []

        if batch:
            db.add_all(batch)
            await db.flush()
            created_count += len(batch)

        await db.commit()

    print(f'\n🎉 导入完成！')
    print(f'   ✅ 成功导入: {created_count} 条')
    print(f'   ⏭️  跳过重复: {skipped_count} 条')


async def import_chengyu_simple(names: list[str]):
    """
    简单导入成语名称列表

    :param names: 成语名称列表
    """
    print(f'📊 准备导入 {len(names)} 条成语')

    async with async_db_session.begin() as db:
        existing_names = set()
        stmt = select(GkHanyu.name).where(GkHanyu.type == '成语')
        result = await db.execute(stmt)
        existing_names = {row[0] for row in result.all()}
        print(f'📌 数据库中已存在 {len(existing_names)} 条成语')

        batch = []
        created_count = 0
        skipped_count = 0

        for name in names:
            if not name or name in existing_names:
                skipped_count += 1
                continue

            hanyu = GkHanyu(
                name=name,
                type='成语',
                frequency=0,
                created_by=1,
            )
            batch.append(hanyu)
            existing_names.add(name)

        if batch:
            db.add_all(batch)
            await db.flush()
            created_count = len(batch)

        await db.commit()

    print(f'\n🎉 导入完成！')
    print(f'   ✅ 成功导入: {created_count} 条')
    print(f'   ⏭️  跳过重复: {skipped_count} 条')


async def main():
    """主函数"""
    print('=' * 60)
    print('成语数据导入工具')
    print('=' * 60)

    script_dir = Path(__file__).parent
    json_file = script_dir / 'chinese-xinhua' / 'data' / 'idiom.json'

    await import_chengyu_from_json(str(json_file), batch_size=500)


if __name__ == '__main__':
    asyncio.run(main())
