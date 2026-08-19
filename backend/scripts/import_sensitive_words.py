#!/usr/bin/env python3
"""导入 Sensitive-lexicon 精选分类敏感词到本地 dev 库。

用法:
    python scripts/import_sensitive_words.py [词库目录] [--all-categories]

默认读取克隆的 Sensitive-lexicon/Vocabulary 目录精选分类；
传 --all-categories 可把大库(Tencent/网易/GFW)也纳入，注意高误伤风险。
按词长区分处理方式: len<=4 -> block(打码)  len>4 -> reject(拦截)。
"""

import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ['FBA_DEV'] = '1'

from sqlalchemy import create_engine, text  # noqa: E402

# 精选分类（避开 Tencent大库/非法网址/GFW/网易前端等噪音源）
CURATED_FILES = [
    '政治类型.txt', '色情类型.txt', '色情词库.txt', '涉枪涉爆.txt',
    '暴恐词库.txt', '反动词库.txt', '贪腐词库.txt', '民生词库.txt',
    '广告类型.txt', '补充词库.txt', '新思想启蒙.txt', 'COVID-19词库.txt',
    '其他词库.txt',
]
# 大库文件（--all-categories 时追加）
EXTRA_FILES = ['零时-Tencent.txt', '网易前端过滤敏感词库.txt', 'GFW补充词库.txt']

DEFAULT_DIR = Path(r'C:\Users\19396\AppData\Local\Temp\opencode\Sensitive-lexicon\Vocabulary')


def is_junk(w: str) -> bool:
    """过滤噪音：单字、纯数字、域名、含空格句子、拼接句。"""
    if len(w) <= 1:
        return True
    if w.isdigit():
        return True
    if re.match(r'^[\w.\-]+\.[a-z]{2,}$', w, re.I):  # 域名
        return True
    if re.search(r'\s', w):  # 含空格句子
        return True
    if '+' in w:  # 拼接句
        return True
    return False


def load_words(dir_path: Path, all_categories: bool) -> dict[str, str]:
    """读取词库文件，返回 {小写规范化key: (原词, 分类)}。"""
    files = CURATED_FILES + (EXTRA_FILES if all_categories else [])
    norm: dict[str, tuple[str, str]] = {}
    for fn in files:
        f = dir_path / fn
        if not f.exists():
            print(f'[skip] 缺失文件: {fn}')
            continue
        cat = fn.replace('.txt', '')
        n = 0
        for line in f.read_text(encoding='utf-8').splitlines():
            w = line.strip()
            if not w or is_junk(w):
                continue
            key = w.lower()
            # 同 key 取更短的原词，避免大小写/繁简变体重复
            if key not in norm or len(w) < len(norm[key][0]):
                norm[key] = (w, cat)
                n += 1
        print(f'[read] {fn}: +{n}')
    return norm


def get_engine():
    from backend.core.conf import settings
    driver = 'psycopg' if settings.DATABASE_TYPE == 'postgresql' else 'pymysql'
    database = settings.DATABASE_SCHEMA
    url = (
        f'{settings.DATABASE_TYPE}+{driver}://{settings.DATABASE_USER}:{settings.DATABASE_PASSWORD}'
        f'@{settings.DATABASE_HOST}:{settings.DATABASE_PORT}/{database}'
    )
    return create_engine(url, pool_pre_ping=True)


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('dir', nargs='?', default=str(DEFAULT_DIR), help='词库目录')
    parser.add_argument('--all-categories', action='store_true', help='纳入大库(高误伤)')
    args = parser.parse_args()

    dir_path = Path(args.dir)
    if not dir_path.is_dir():
        sys.exit(f'词库目录不存在: {dir_path}')

    norm = load_words(dir_path, args.all_categories)
    print(f'清洗后待导入: {len(norm)} 条')
    if not norm:
        sys.exit('无数据')

    block = [w for w in norm if len(norm[w][0]) <= 4]
    reject = [w for w in norm if len(norm[w][0]) > 4]
    print(f'  block 打码 (len<=4): {len(block)}')
    print(f'  reject 拦截 (len>4): {len(reject)}')

    eng = get_engine()
    with eng.begin() as conn:
        existing = {
            row[0]
            for row in conn.execute(
                text("select word from sensitive_word where deleted = 0")
            ).fetchall()
        }
        inserted = skipped = 0
        rows = []
        for key, (word, cat) in norm.items():
            if word in existing:
                skipped += 1
                continue
            action = 'block' if len(word) <= 4 else 'reject'
            rows.append({
                'word': word,
                'variants': [],
                'replacement': None,
                'action': action,
                'status': 'active',
                'remark': f'来源: Sensitive-lexicon/{cat}',
                'sort_order': 0,
                'created_by': 1,
            })
        from sqlalchemy.dialects.postgresql import JSONB
        from sqlalchemy import bindparam
        from sqlalchemy import table, column

        tbl = table(
            'sensitive_word',
            column('word'), column('variants', JSONB), column('replacement'),
            column('action'), column('status'), column('remark'),
            column('sort_order'), column('created_by'), column('created_time'),
        )
        for i in range(0, len(rows), 1000):
            batch = rows[i:i + 1000]
            sql = tbl.insert().values([
                {
                    'word': bindparam(f'w{j}'),
                    'variants': bindparam(f'v{j}', type_=JSONB),
                    'replacement': bindparam(f'r{j}'),
                    'action': bindparam(f'a{j}'),
                    'status': bindparam(f's{j}'),
                    'remark': bindparam(f'm{j}'),
                    'sort_order': bindparam(f'o{j}'),
                    'created_by': bindparam(f'c{j}'),
                    'created_time': text('now()'),
                }
                for j in range(len(batch))
            ])
            params = {}
            for j, row in enumerate(batch):
                params[f'w{j}'] = row['word']
                params[f'v{j}'] = row['variants']
                params[f'r{j}'] = row['replacement']
                params[f'a{j}'] = row['action']
                params[f's{j}'] = row['status']
                params[f'm{j}'] = row['remark']
                params[f'o{j}'] = row['sort_order']
                params[f'c{j}'] = row['created_by']
            conn.execute(sql, params)
            inserted += len(batch)
        print(f'[db] 新增 {inserted} 条, 跳过已存在 {skipped} 条')

    # 清理 Redis 规则缓存（RedisCache 的 key 即前缀本身），让新词立即生效
    try:
        from backend.database.redis import redis_client
        redis_client.delete('sensitive:word:rules')
        print('[redis] 已清理规则缓存 key=sensitive:word:rules')
    except Exception as e:  # noqa: BLE001
        print(f'[redis] 缓存清理跳过: {e}')


if __name__ == '__main__':
    main()
