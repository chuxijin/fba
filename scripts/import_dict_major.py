#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
专业目录字典数据导入脚本

数据来源: 教育部《普通高等学校本科专业目录（2025年）》
使用方法: python scripts/import_dict_major.py
"""
import asyncio
import json
import sys
from pathlib import Path

# 添加项目根目录到 sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text

from backend.database.db import async_engine

# 数据文件路径
DATA_FILE = Path(__file__).parent / 'data' / 'major_catalog_2025.json'


def load_catalog() -> dict:
    """加载专业目录数据"""
    with open(DATA_FILE, encoding='utf-8') as f:
        return json.load(f)


def parse_major_code(code: str) -> tuple[str, bool, bool]:
    """
    解析专业代码，提取基础代码和特殊标记

    :param code: 专业代码（如 030101K、080717T）
    :return: (基础代码, 是否特设专业T, 是否国控专业K)
    """
    is_special = 'T' in code
    is_controlled = 'K' in code
    base_code = code.replace('T', '').replace('K', '')
    return base_code, is_special, is_controlled


async def import_majors() -> None:
    """导入专业目录数据"""
    print('=' * 60)
    print('开始导入专业目录数据')
    print('=' * 60)

    # 1. 加载数据
    print('\n[1/3] 加载专业目录数据...')
    catalog = load_catalog()
    print(f'  数据版本: {catalog["version"]}')
    print(f'  数据来源: {catalog["source"]}')

    # 2. 转换数据
    print('\n[2/3] 转换数据格式...')

    all_majors = []
    category_count = 0
    class_count = 0
    major_count = 0

    for cat_idx, category in enumerate(catalog['categories']):
        # 学科门类（level 1）
        category_count += 1
        all_majors.append({
            'code': category['code'],
            'name': category['name'],
            'level': 1,
            'parent_code': None,
            'edu_level': '本科',
            'aliases': None,
            'description': None,
            'sort_order': cat_idx,
            'is_active': True,
        })

        for cls_idx, major_class in enumerate(category['classes']):
            # 专业类（level 2）
            class_count += 1
            all_majors.append({
                'code': major_class['code'],
                'name': major_class['name'],
                'level': 2,
                'parent_code': category['code'],
                'edu_level': '本科',
                'aliases': None,
                'description': None,
                'sort_order': cls_idx,
                'is_active': True,
            })

            for maj_idx, major in enumerate(major_class['majors']):
                # 专业（level 3）
                major_count += 1
                base_code, is_special, is_controlled = parse_major_code(major['code'])

                # 构建描述
                desc_parts = []
                if is_special:
                    desc_parts.append('特设专业')
                if is_controlled:
                    desc_parts.append('国家控制布点专业')
                description = '，'.join(desc_parts) if desc_parts else None

                all_majors.append({
                    'code': major['code'],  # 保留原始代码（含 T/K 标记）
                    'name': major['name'],
                    'level': 3,
                    'parent_code': major_class['code'],
                    'edu_level': '本科',
                    'aliases': None,  # 可后续补充别名
                    'description': description,
                    'sort_order': maj_idx,
                    'is_active': True,
                })

    print(f'  学科门类: {category_count} 个')
    print(f'  专业类: {class_count} 个')
    print(f'  专业: {major_count} 个')
    print(f'  总计: {len(all_majors)} 条记录')

    # 3. 写入数据库
    print('\n[3/3] 写入数据库...')

    async with async_engine.begin() as conn:
        # 清空旧数据
        await conn.execute(text('TRUNCATE TABLE gk_dict_major RESTART IDENTITY CASCADE'))
        print('  已清空旧数据')

        # 批量插入
        insert_sql = text('''
            INSERT INTO gk_dict_major (
                code, name, level, parent_code, edu_level,
                aliases, description, sort_order, is_active, created_time
            )
            VALUES (
                :code, :name, :level, :parent_code, :edu_level,
                :aliases, :description, :sort_order, :is_active, NOW()
            )
        ''')

        # 分批插入（每批 500 条）
        batch_size = 500
        for i in range(0, len(all_majors), batch_size):
            batch = all_majors[i : i + batch_size]
            await conn.execute(insert_sql, batch)
            print(f'  已插入 {min(i + batch_size, len(all_majors))}/{len(all_majors)} 条')

    print('\n' + '=' * 60)
    print('专业目录数据导入完成！')
    print(f'  - 学科门类 (level 1): {category_count} 个')
    print(f'  - 专业类 (level 2): {class_count} 个')
    print(f'  - 专业 (level 3): {major_count} 个')
    print(f'  - 总计: {len(all_majors)} 条')
    print('=' * 60)


if __name__ == '__main__':
    asyncio.run(import_majors())
