#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
词语数据导入脚本

数据来源: https://github.com/pwxcoo/chinese-xinhua ci.json
使用方法: python scripts/import_ciyu.py [--clear]
"""
import argparse
import asyncio
import json
import sys
from pathlib import Path

# 添加项目根目录到 sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text

from backend.database.db import async_engine

# 数据文件路径
DATA_FILE = Path(__file__).parent / 'ci.json'

# 默认创建者 ID（系统管理员）
DEFAULT_CREATED_BY = 1


def load_ciyu_data() -> list[dict]:
    """加载词语数据"""
    with open(DATA_FILE, encoding='utf-8') as f:
        return json.load(f)


async def import_ciyu(clear_existing: bool = False) -> None:
    """
    导入词语数据

    :param clear_existing: 是否清空已有数据
    """
    print('=' * 60)
    print('开始导入词语数据')
    print('=' * 60)

    # 1. 加载数据
    print('\n[1/3] 加载词语数据...')
    raw_data = load_ciyu_data()
    print(f'  总计: {len(raw_data)} 条词语')

    # 2. 转换数据
    print('\n[2/3] 转换数据格式...')

    ciyu_list = []
    for item in raw_data:
        word = item.get('ci', '').strip()
        explanation = item.get('explanation', '').strip()

        # 跳过空词语
        if not word:
            continue

        ciyu_list.append({
            'word': word,
            'meaning': explanation if explanation else None,
            'view_count': 0,
            'created_by': DEFAULT_CREATED_BY,
        })

    # 去重（按 word 字段）
    seen = set()
    unique_ciyu = []
    for item in ciyu_list:
        if item['word'] not in seen:
            seen.add(item['word'])
            unique_ciyu.append(item)

    duplicate_count = len(ciyu_list) - len(unique_ciyu)
    if duplicate_count > 0:
        print(f'  去除重复: {duplicate_count} 条')

    ciyu_list = unique_ciyu
    print(f'  有效数据: {len(ciyu_list)} 条')

    # 3. 写入数据库
    print('\n[3/3] 写入数据库...')

    async with async_engine.begin() as conn:
        if clear_existing:
            # 清空旧数据（PostgreSQL 语法）
            await conn.execute(text('TRUNCATE TABLE gk_ciyu RESTART IDENTITY CASCADE'))
            print('  已清空旧数据')
        else:
            # 查询已存在的词语
            result = await conn.execute(text('SELECT word FROM gk_ciyu'))
            existing_words = {row[0] for row in result.fetchall()}
            print(f'  数据库已有: {len(existing_words)} 条')

            # 过滤掉已存在的词语
            original_count = len(ciyu_list)
            ciyu_list = [item for item in ciyu_list if item['word'] not in existing_words]
            skipped_count = original_count - len(ciyu_list)

            if skipped_count > 0:
                print(f'  跳过已存在: {skipped_count} 条')

            if not ciyu_list:
                print('\n无新数据需要导入')
                return

        print(f'  待导入: {len(ciyu_list)} 条')

        # 批量插入
        insert_sql = text('''
            INSERT INTO gk_ciyu (word, meaning, view_count, created_by, created_time)
            VALUES (:word, :meaning, :view_count, :created_by, NOW())
        ''')

        # 分批插入（每批 5000 条，26万数据约 53 批）
        batch_size = 5000
        total = len(ciyu_list)

        for i in range(0, total, batch_size):
            batch = ciyu_list[i : i + batch_size]
            await conn.execute(insert_sql, batch)
            progress = min(i + batch_size, total)
            percent = progress / total * 100
            print(f'  已插入: {progress:>6}/{total} ({percent:.1f}%)')

    print('\n' + '=' * 60)
    print('词语数据导入完成！')
    print(f'  - 总计导入: {len(ciyu_list)} 条')
    print('=' * 60)


def main() -> None:
    """主函数"""
    parser = argparse.ArgumentParser(description='导入词语数据到数据库')
    parser.add_argument(
        '--clear',
        action='store_true',
        help='清空已有数据后重新导入',
    )
    args = parser.parse_args()

    if not DATA_FILE.exists():
        print(f'错误: 数据文件不存在: {DATA_FILE}')
        print('请先下载 ci.json 到 scripts/ 目录')
        sys.exit(1)

    asyncio.run(import_ciyu(clear_existing=args.clear))


if __name__ == '__main__':
    main()
