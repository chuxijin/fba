#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OC 数据迁移脚本
从 OC 数据库复制数据到 FBA 数据库

使用前修改下方 SOURCE_DB 和 TARGET_DB 的连接信息
"""
import asyncio
import sys

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

# ===== 配置区域 =====
# 源数据库（OC）
SOURCE_DB = 'postgresql+asyncpg://user:password@localhost:5432/oc_database'
# 目标数据库（FBA）
TARGET_DB = 'postgresql+asyncpg://user:password@localhost:5432/fba_database'

# 需要迁移的表（按依赖顺序）
TABLES = [
    'oc_campus_recruit',
    'oc_intern_recruit',
    'oc_resource',
    'oc_formatter_field',
    'oc_formatter_embedding',
    'oc_formatter_mapping',
    'oc_referral_code',
    'oc_feedback',
    'oc_user_resume',
    'oc_user_application',  # 有外键依赖，放最后
]


async def migrate_table(source_session, target_session, table_name):
    """迁移单张表的数据"""
    # 读取源数据
    result = await source_session.execute(text(f'SELECT * FROM {table_name}'))
    rows = result.fetchall()
    if not rows:
        print(f'  {table_name}: 无数据，跳过')
        return

    # 获取列名
    columns = result.keys()
    cols_str = ', '.join(columns)
    placeholders = ', '.join([f':{col}' for col in columns])

    # 清空目标表（避免冲突）
    await target_session.execute(text(f'TRUNCATE TABLE {table_name} CASCADE'))

    # 批量插入
    inserted = 0
    for row in rows:
        data = {col: val for col, val in zip(columns, row)}
        await target_session.execute(
            text(f'INSERT INTO {table_name} ({cols_str}) VALUES ({placeholders})'),
            data
        )
        inserted += 1

    print(f'  {table_name}: 迁移 {inserted} 条记录')


async def main():
    source_engine = create_async_engine(SOURCE_DB)
    target_engine = create_async_engine(TARGET_DB)

    source_factory = async_sessionmaker(source_engine, class_=AsyncSession)
    target_factory = async_sessionmaker(target_engine, class_=AsyncSession)

    print('=' * 50)
    print('OC 数据迁移开始')
    print('=' * 50)

    async with target_factory() as target_session:
        async with source_factory() as source_session:
            for table in TABLES:
                try:
                    await migrate_table(source_session, target_session, table)
                    await target_session.commit()
                except Exception as e:
                    print(f'  {table}: 迁移失败 - {e}')
                    await target_session.rollback()

    await source_engine.dispose()
    await target_engine.dispose()

    print('=' * 50)
    print('迁移完成！')
    print('=' * 50)


if __name__ == '__main__':
    asyncio.run(main())
