#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
地区字典数据导入脚本

数据来源: https://github.com/modood/Administrative-divisions-of-China
使用方法: python scripts/import_dict_region.py
"""
import asyncio
import sys
from pathlib import Path

import httpx

# 添加项目根目录到 sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text

from backend.database.db import async_engine

# GitHub 原始文件地址
BASE_URL = 'https://raw.githubusercontent.com/modood/Administrative-divisions-of-China/master/dist'
PROVINCES_URL = f'{BASE_URL}/provinces.json'
CITIES_URL = f'{BASE_URL}/cities.json'
AREAS_URL = f'{BASE_URL}/areas.json'

# 备用镜像（如果 GitHub 访问慢）
MIRROR_BASE_URL = 'https://cdn.jsdelivr.net/gh/modood/Administrative-divisions-of-China@master/dist'


async def fetch_json(url: str) -> list[dict]:
    """
    从 URL 获取 JSON 数据

    :param url: JSON 文件 URL
    :return:
    """
    async with httpx.AsyncClient(timeout=30) as client:
        try:
            response = await client.get(url)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError:
            # 尝试镜像
            mirror_url = url.replace(BASE_URL, MIRROR_BASE_URL)
            print(f'  GitHub 访问失败，尝试镜像: {mirror_url}')
            response = await client.get(mirror_url)
            response.raise_for_status()
            return response.json()


def normalize_code(code: str, level: int) -> str:
    """
    标准化行政区划代码为6位

    :param code: 原始代码
    :param level: 级别 (1省 2市 3县)
    :return:
    """
    if level == 1:
        # 省级: 11 -> 110000
        return code.ljust(6, '0')
    elif level == 2:
        # 市级: 1101 -> 110100
        return code.ljust(6, '0')
    else:
        # 县级: 110101 -> 110101
        return code


def get_parent_code(item: dict, level: int) -> str | None:
    """
    获取父级代码

    :param item: 数据项
    :param level: 级别
    :return:
    """
    if level == 1:
        return None
    elif level == 2:
        # 市的父级是省
        province_code = item.get('provinceCode', '')
        return province_code.ljust(6, '0') if province_code else None
    else:
        # 县的父级是市
        city_code = item.get('cityCode', '')
        return city_code.ljust(6, '0') if city_code else None


async def import_regions() -> None:
    """导入地区字典数据"""
    print('=' * 60)
    print('开始导入地区字典数据')
    print('=' * 60)

    # 1. 获取数据
    print('\n[1/4] 获取省份数据...')
    provinces = await fetch_json(PROVINCES_URL)
    print(f'  获取到 {len(provinces)} 个省份')

    print('\n[2/4] 获取城市数据...')
    cities = await fetch_json(CITIES_URL)
    print(f'  获取到 {len(cities)} 个城市')

    print('\n[3/4] 获取区县数据...')
    areas = await fetch_json(AREAS_URL)
    print(f'  获取到 {len(areas)} 个区县')

    # 2. 转换数据
    print('\n[4/4] 转换并导入数据库...')

    all_regions = []
    seen_codes: set[str] = set()

    # 省级
    for idx, p in enumerate(provinces):
        code = normalize_code(p['code'], 1)
        seen_codes.add(code)
        all_regions.append({
            'code': code,
            'name': p['name'],
            'level': 1,
            'parent_code': None,
            'is_remote_area': False,
            'sort_order': idx,
        })

    # 市级
    for idx, c in enumerate(cities):
        code = normalize_code(c['code'], 2)
        if code in seen_codes:
            continue
        seen_codes.add(code)
        all_regions.append({
            'code': code,
            'name': c['name'],
            'level': 2,
            'parent_code': get_parent_code(c, 2),
            'is_remote_area': False,
            'sort_order': idx,
        })

    # 县级
    for idx, a in enumerate(areas):
        code = normalize_code(a['code'], 3)
        if code in seen_codes:
            print(f'  跳过重复代码: {code} ({a["name"]})')
            continue
        seen_codes.add(code)
        all_regions.append({
            'code': code,
            'name': a['name'],
            'level': 3,
            'parent_code': get_parent_code(a, 3),
            'is_remote_area': False,
            'sort_order': idx,
        })

    print(f'  共计 {len(all_regions)} 条记录')

    # 3. 写入数据库
    async with async_engine.begin() as conn:
        # 清空旧数据
        await conn.execute(text('TRUNCATE TABLE gk_dict_region RESTART IDENTITY CASCADE'))
        print('  已清空旧数据')

        # 批量插入
        insert_sql = text('''
            INSERT INTO gk_dict_region (code, name, level, parent_code, is_remote_area, sort_order, created_time)
            VALUES (:code, :name, :level, :parent_code, :is_remote_area, :sort_order, NOW())
        ''')

        # 分批插入（每批 1000 条）
        batch_size = 1000
        for i in range(0, len(all_regions), batch_size):
            batch = all_regions[i : i + batch_size]
            await conn.execute(insert_sql, batch)
            print(f'  已插入 {min(i + batch_size, len(all_regions))}/{len(all_regions)} 条')

    print('\n' + '=' * 60)
    print('地区字典数据导入完成！')
    print(f'  - 省级: {len(provinces)} 条')
    print(f'  - 市级: {len(cities)} 条')
    print(f'  - 县级: {len(areas)} 条')
    print(f'  - 总计: {len(all_regions)} 条')
    print('=' * 60)


if __name__ == '__main__':
    asyncio.run(import_regions())
