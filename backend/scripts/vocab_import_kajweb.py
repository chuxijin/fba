#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
从 kajweb/dict 的 JSONL zip 文件导入词书数据到 vocab 模块。

用法:
    cd backend
    uv run python scripts/vocab_import_kajweb.py

数据来源: https://github.com/kajweb/dict
"""
import asyncio
import json
import os
import sys
import zipfile

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

DATA_DIR = os.path.join(os.path.dirname(__file__), 'vocab_data')

# 词书配置: zip 文件名 → (词书名称, 分类, 描述, 排序)
BOOK_CONFIGS = {
    'CET4_3.zip': (
        '大学英语四级词汇',
        'cet4',
        '大学英语四级考试核心词汇，约 2600 词，涵盖大纲全部要求。',
        10,
    ),
    'CET6_3.zip': (
        '大学英语六级词汇',
        'cet6',
        '大学英语六级考试核心词汇，在四级基础上进阶，约 2000 词。',
        20,
    ),
    'KaoYan_3.zip': (
        '考研英语词汇',
        'kaoyan',
        '全国硕士研究生入学考试英语词汇，约 5500 词。',
        30,
    ),
}

# 批量大小
BATCH_SIZE = 200

# 系统导入使用管理员用户 ID
SYSTEM_USER_ID = 1


def get_database_url() -> str:
    """
    获取数据库连接 URL

    优先使用环境变量 DATABASE_URL，否则从 backend settings 读取
    """
    env_url = os.environ.get('DATABASE_URL')
    if env_url:
        return env_url

    # 回退到 settings
    from backend.core.conf import settings
    from backend.common.enums import DataBaseType

    driver = 'postgresql+asyncpg' if settings.DATABASE_TYPE == DataBaseType.postgresql else 'mysql+asyncmy'
    return (
        f'{driver}://{settings.DATABASE_USER}:{settings.DATABASE_PASSWORD}'
        f'@{settings.DATABASE_HOST}:{settings.DATABASE_PORT}/{settings.DATABASE_SCHEMA}'
    )


def read_jsonl_from_zip(zip_path: str) -> list[dict]:
    """
    从 zip 文件中读取 JSONL 格式数据

    :param zip_path: zip 文件路径
    :return:
    """
    with zipfile.ZipFile(zip_path) as zf:
        json_files = [n for n in zf.namelist() if n.endswith('.json')]
        if not json_files:
            raise ValueError(f'No JSON file found in {zip_path}')

        with zf.open(json_files[0]) as f:
            raw = f.read().decode('utf-8')

    items = []
    for line in raw.strip().split('\n'):
        line = line.strip()
        if not line:
            continue
        items.append(json.loads(line))

    return items


def parse_word_entry(entry: dict) -> dict:
    """
    解析单个词条数据为标准化的字典

    :param entry: kajweb JSONL 中的一行数据
    :return:
    """
    head_word = entry.get('headWord', '').strip()
    word_rank = entry.get('wordRank', 0)
    content = entry.get('content', {}).get('word', {}).get('content', {})

    # 音标
    usphone = content.get('usphone', '') or ''
    ukphone = content.get('ukphone', '') or ''

    # 释义列表
    trans_raw = content.get('trans', [])
    definitions = []
    common_meanings = []
    for idx, t in enumerate(trans_raw):
        pos = (t.get('pos') or '').strip()
        meaning_cn = (t.get('tranCn') or '').strip()
        meaning_en = (t.get('tranOther') or '').strip()
        if meaning_cn:
            definitions.append({
                'meaning': meaning_cn,
                'part_of_speech': pos or None,
                'meaning_en': meaning_en or None,
                'sort_order': idx,
            })
            label = f'{pos}. {meaning_cn}' if pos else meaning_cn
            common_meanings.append(label)

    # 例句列表
    sentences_raw = content.get('sentence', {}).get('sentences', [])
    examples = []
    for idx, s in enumerate(sentences_raw):
        en = (s.get('sContent') or '').strip()
        zh = (s.get('sCn') or '').strip()
        if en:
            examples.append({
                'sentence_en': en,
                'sentence_zh': zh or None,
                'source': 'kajweb/dict',
                'sort_order': idx,
            })

    # 合成 common_meaning (截取前 200 字符)
    common_meaning = '；'.join(common_meanings)
    if len(common_meaning) > 200:
        common_meaning = common_meaning[:197] + '...'

    return {
        'word': head_word,
        'phonetic_us': usphone or None,
        'phonetic_uk': ukphone or None,
        'audio_us_url': f'https://dict.youdao.com/dictvoice?audio={head_word}&type=2' if head_word else None,
        'audio_uk_url': f'https://dict.youdao.com/dictvoice?audio={head_word}&type=1' if head_word else None,
        'common_meaning': common_meaning or None,
        'frequency': 0,
        'word_rank': word_rank,
        'definitions': definitions,
        'examples': examples,
    }


async def import_book(db: AsyncSession, zip_filename: str) -> dict:
    """
    导入单本词书

    :param db: 数据库会话
    :param zip_filename: zip 文件名
    :return:
    """
    from backend.app.vocab.model.vocab_book import VocabBook
    from backend.app.vocab.model.vocab_book_word import VocabBookWord
    from backend.app.vocab.model.vocab_definition import VocabDefinition
    from backend.app.vocab.model.vocab_example import VocabExample
    from backend.app.vocab.model.vocab_word import VocabWord

    config = BOOK_CONFIGS[zip_filename]
    book_name, category, description, sort_order = config
    zip_path = os.path.join(DATA_DIR, zip_filename)

    if not os.path.exists(zip_path):
        print(f'  [SKIP] {zip_path} not found')
        return {'status': 'skipped', 'reason': 'file not found'}

    # 检查词书是否已存在
    existing_book = await db.scalar(
        select(VocabBook).where(VocabBook.name == book_name).limit(1)
    )
    if existing_book:
        print(f'  [SKIP] "{book_name}" already exists (id={existing_book.id})')
        return {'status': 'skipped', 'reason': 'book exists'}

    print(f'  [READ] {zip_filename}...')
    raw_entries = read_jsonl_from_zip(zip_path)
    print(f'  [PARSE] {len(raw_entries)} entries')

    # 解析所有词条
    parsed_entries = []
    skip_count = 0
    for entry in raw_entries:
        parsed = parse_word_entry(entry)
        if not parsed['word']:
            skip_count += 1
            continue
        parsed_entries.append(parsed)

    if skip_count:
        print(f'  [WARN] skipped {skip_count} empty entries')

    # 1. 创建词书
    book = VocabBook(
        name=book_name,
        description=description,
        category=category,
        word_count=len(parsed_entries),
        is_official=True,
        sort_order=sort_order,
        status=1,
        created_by=SYSTEM_USER_ID,
    )
    db.add(book)
    await db.flush()
    book_id = book.id
    print(f'  [BOOK] created id={book_id}')

    # 2. 批量收集全部单词文本，一次性查询已有单词
    word_texts = list({p['word'] for p in parsed_entries})
    existing_word_map: dict[str, int] = {}

    # 分批查询已存在的单词（避免 IN 子句过长）
    for i in range(0, len(word_texts), 500):
        batch_texts = word_texts[i:i + 500]
        result = await db.execute(
            select(VocabWord.id, VocabWord.word).where(VocabWord.word.in_(batch_texts))
        )
        for row in result:
            existing_word_map[row.word] = row.id

    new_word_count = 0
    reuse_word_count = 0
    total_definitions = 0
    total_examples = 0

    for batch_start in range(0, len(parsed_entries), BATCH_SIZE):
        batch = parsed_entries[batch_start:batch_start + BATCH_SIZE]

        for idx_in_batch, parsed in enumerate(batch):
            global_idx = batch_start + idx_in_batch
            word_text = parsed['word']

            word_id = existing_word_map.get(word_text)
            if word_id is None:
                word_obj = VocabWord(
                    word=word_text,
                    phonetic_us=parsed['phonetic_us'],
                    phonetic_uk=parsed['phonetic_uk'],
                    audio_us_url=parsed['audio_us_url'],
                    audio_uk_url=parsed['audio_uk_url'],
                    common_meaning=parsed['common_meaning'],
                    frequency=parsed['frequency'],
                    created_by=SYSTEM_USER_ID,
                )
                db.add(word_obj)
                await db.flush()
                word_id = word_obj.id
                existing_word_map[word_text] = word_id
                new_word_count += 1

                # 写入释义
                for defn in parsed['definitions']:
                    db.add(VocabDefinition(
                        word_id=word_id,
                        meaning=defn['meaning'],
                        part_of_speech=defn['part_of_speech'],
                        meaning_en=defn['meaning_en'],
                        sort_order=defn['sort_order'],
                    ))
                    total_definitions += 1

                # 写入例句
                for ex in parsed['examples']:
                    db.add(VocabExample(
                        word_id=word_id,
                        sentence_en=ex['sentence_en'],
                        sentence_zh=ex['sentence_zh'],
                        source=ex['source'],
                        sort_order=ex['sort_order'],
                    ))
                    total_examples += 1
            else:
                reuse_word_count += 1

            # 词书-单词关联
            db.add(VocabBookWord(
                book_id=book_id,
                word_id=word_id,
                sort_order=parsed.get('word_rank', global_idx),
            ))

        await db.flush()
        progress = min(batch_start + BATCH_SIZE, len(parsed_entries))
        print(f'  [BATCH] {progress}/{len(parsed_entries)}')

    await db.commit()

    stats = {
        'status': 'ok',
        'book_id': book_id,
        'book_name': book_name,
        'total_entries': len(parsed_entries),
        'new_words': new_word_count,
        'reused_words': reuse_word_count,
        'definitions': total_definitions,
        'examples': total_examples,
    }
    print(f'  [DONE] {json.dumps(stats, ensure_ascii=False)}')
    return stats


async def main():
    """导入全部词书"""
    print('=' * 60)
    print('Vocab Import: kajweb/dict -> vocab tables')
    print('=' * 60)

    db_url = get_database_url()
    # 隐藏密码打印
    safe_url = db_url.split('@')[-1] if '@' in db_url else db_url
    print(f'Database: ...@{safe_url}')

    engine = create_async_engine(db_url, echo=False)
    session_factory = async_sessionmaker(bind=engine, expire_on_commit=False)

    results = []
    async with session_factory() as db:
        for zip_filename in BOOK_CONFIGS:
            print(f'\n--- {zip_filename} ---')
            result = await import_book(db, zip_filename)
            results.append(result)

    await engine.dispose()

    print('\n' + '=' * 60)
    print('Summary:')
    for r in results:
        if r['status'] == 'ok':
            print(f"  OK: {r['book_name']}: {r['total_entries']} words "
                  f"(new={r['new_words']}, reused={r['reused_words']}, "
                  f"defs={r['definitions']}, examples={r['examples']})")
        else:
            print(f"  SKIP: {r.get('reason', 'unknown')}")
    print('=' * 60)


if __name__ == '__main__':
    asyncio.run(main())
