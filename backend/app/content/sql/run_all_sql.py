#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
批量执行 content/sql 目录下所有 SQL 文件

用法：
    python run_all_sql.py          # 执行所有 .sql 文件
    python run_all_sql.py --dry    # 仅预览，不执行
    python run_all_sql.py kp_xingce_data_term  # 只执行文件名包含该关键词的
"""
import argparse
import asyncio
import sys
import time

from pathlib import Path

import asyncpg


def load_env() -> dict[str, str]:
    """从 .env 文件加载数据库配置"""
    env_path = Path(__file__).resolve().parents[3] / '.env'
    env_vars: dict[str, str] = {}
    if not env_path.exists():
        print(f'❌ 找不到 .env 文件: {env_path}')
        sys.exit(1)

    with open(env_path, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            if '=' in line:
                key, _, value = line.partition('=')
                env_vars[key.strip()] = value.strip().strip("'\"")
    return env_vars


async def run(sql_files: list[Path], dry: bool) -> None:
    """批量执行 SQL 文件"""
    print(f'📄 共发现 {len(sql_files)} 个 SQL 文件\n')

    if dry:
        for i, f in enumerate(sql_files, 1):
            print(f'  [{i:02d}] {f.name} ({f.stat().st_size / 1024:.1f} KB)')
        print(f'\n🔍 预览模式，未执行任何操作')
        return

    env_vars = load_env()
    db_schema = env_vars.get('DATABASE_SCHEMA', 'fba')
    host = env_vars['DATABASE_HOST']
    port = int(env_vars['DATABASE_PORT'])
    user = env_vars['DATABASE_USER']
    password = env_vars['DATABASE_PASSWORD']

    print(f'🔗 连接数据库: {host}:{port}/{db_schema}\n')

    conn = await asyncpg.connect(
        host=host,
        port=port,
        user=user,
        password=password,
        database=db_schema,
    )

    success_count = 0
    fail_count = 0
    total_start = time.time()

    for i, sql_file in enumerate(sql_files, 1):
        sql_content = sql_file.read_text(encoding='utf-8')
        start = time.time()

        try:
            result = await conn.execute(sql_content)
            elapsed = time.time() - start
            print(f'  ✅ [{i:02d}/{len(sql_files)}] {sql_file.name} ({elapsed:.2f}s) {result}')
            success_count += 1
        except Exception as e:
            elapsed = time.time() - start
            print(f'  ❌ [{i:02d}/{len(sql_files)}] {sql_file.name} ({elapsed:.2f}s)')
            print(f'      错误: {e}')
            fail_count += 1

    await conn.close()

    total_elapsed = time.time() - total_start
    print(f'\n{"=" * 50}')
    print(f'🏁 执行完毕 | 总耗时: {total_elapsed:.2f}s')
    print(f'   ✅ 成功: {success_count}  ❌ 失败: {fail_count}  📄 总计: {len(sql_files)}')


def main():
    parser = argparse.ArgumentParser(description='批量执行 SQL 文件')
    parser.add_argument('filter', nargs='?', default=None, help='文件名过滤关键词')
    parser.add_argument('--dry', action='store_true', help='仅预览不执行')
    args = parser.parse_args()

    sql_dir = Path(__file__).parent
    sql_files = sorted(sql_dir.glob('*.sql'))

    if args.filter:
        sql_files = [f for f in sql_files if args.filter in f.stem]

    if not sql_files:
        print('❌ 没有找到匹配的 SQL 文件')
        sys.exit(1)

    print(f'📂 SQL 目录: {sql_dir}')

    asyncio.run(run(sql_files, args.dry))


if __name__ == '__main__':
    main()
