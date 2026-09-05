#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
《雨菲言语·27言语带背800词》全量自适应导入脚本

功能说明:
1. 自动检查并创建 gk_hanyu_group、gk_hanyu_group_item 表结构 (DDL)。
2. 基于词语名称 (name) 动态匹配数据库中的底层词汇 gk_hanyu，自动复用已有词 ID，缺则动态补录。
3. 批量幂等导入词书 (gk_hanyu_wordbook)、章节条目 (gk_hanyu_wordbook_entry) 及近义辨析组 (gk_hanyu_group & item)。
4. 支持开发环境、测试环境及生产环境无缝执行，零自增 ID 冲突。

使用方法:
  python scripts/import_yufei_wordbook.py
  python scripts/import_yufei_wordbook.py --db-url "postgresql+asyncpg://user:pass@host:5432/dbname"
"""
import argparse
import asyncio
import json
import os
import re
import sys
from pathlib import Path

# 添加项目根目录到 sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from backend.core.conf import settings
from backend.app.gongkao.model import GkHanyu, GkHanyuWordbook, GkHanyuWordbookEntry
from backend.app.gongkao.model.hanyu_group import GkHanyuGroup, GkHanyuGroupItem
from pypinyin import pinyin, Style

DATA_FILE = ROOT_DIR / 'scripts' / 'data' / 'yufei_800_words.json'

DDL_CREATE_GROUP_TABLES = """
CREATE TABLE IF NOT EXISTS gk_hanyu_group (
    id BIGSERIAL PRIMARY KEY,
    title VARCHAR(128) NOT NULL,
    group_no VARCHAR(32),
    category VARCHAR(50) DEFAULT '实词辨析' NOT NULL,
    summary TEXT,
    example TEXT,
    sort_order INT DEFAULT 0 NOT NULL,
    created_by BIGINT,
    updated_by BIGINT,
    created_time TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_time TIMESTAMPTZ,
    deleted BIGINT DEFAULT 0 NOT NULL,
    deleted_time TIMESTAMPTZ
);

COMMENT ON TABLE gk_hanyu_group IS '汉语词语/成语辨析组表';
COMMENT ON COLUMN gk_hanyu_group.id IS '主键 ID';
COMMENT ON COLUMN gk_hanyu_group.title IS '辨析组标题(如: 阻碍 阻拦 阻止)';
COMMENT ON COLUMN gk_hanyu_group.group_no IS '序号/题号(如: 398)';
COMMENT ON COLUMN gk_hanyu_group.category IS '分类(如: 实词辨析、成语辨析)';
COMMENT ON COLUMN gk_hanyu_group.summary IS '辨析概要与核心差异解析';
COMMENT ON COLUMN gk_hanyu_group.example IS '典型例句/考题';
COMMENT ON COLUMN gk_hanyu_group.sort_order IS '排序';

CREATE INDEX IF NOT EXISTS ix_gk_hanyu_group_category ON gk_hanyu_group (category);
CREATE INDEX IF NOT EXISTS ix_gk_hanyu_group_group_no ON gk_hanyu_group (group_no);

CREATE TABLE IF NOT EXISTS gk_hanyu_group_item (
    id BIGSERIAL PRIMARY KEY,
    group_id BIGINT NOT NULL REFERENCES gk_hanyu_group(id) ON DELETE CASCADE,
    hanyu_id BIGINT REFERENCES gk_hanyu(id) ON DELETE SET NULL,
    word VARCHAR(64) NOT NULL,
    emphasis TEXT,
    collocation VARCHAR(255),
    sort_order INT DEFAULT 0 NOT NULL,
    created_time TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_time TIMESTAMPTZ,
    deleted BIGINT DEFAULT 0 NOT NULL,
    deleted_time TIMESTAMPTZ
);

COMMENT ON TABLE gk_hanyu_group_item IS '汉语辨析组成员明细表';
COMMENT ON COLUMN gk_hanyu_group_item.id IS '主键 ID';
COMMENT ON COLUMN gk_hanyu_group_item.group_id IS '所属辨析组 ID';
COMMENT ON COLUMN gk_hanyu_group_item.hanyu_id IS '关联汉语词汇 ID';
COMMENT ON COLUMN gk_hanyu_group_item.word IS '词语名称';
COMMENT ON COLUMN gk_hanyu_group_item.emphasis IS '对比侧重点/释义';
COMMENT ON COLUMN gk_hanyu_group_item.collocation IS '常见搭配/适用对象';
COMMENT ON COLUMN gk_hanyu_group_item.sort_order IS '组内排序';

CREATE INDEX IF NOT EXISTS ix_gk_hanyu_group_item_group_id ON gk_hanyu_group_item (group_id);
CREATE INDEX IF NOT EXISTS ix_gk_hanyu_group_item_hanyu_id ON gk_hanyu_group_item (hanyu_id);
CREATE INDEX IF NOT EXISTS ix_gk_hanyu_group_item_word ON gk_hanyu_group_item (word);
"""

watermark_patterns = [
    r'公考资料免费更新.*$',
    r'加微\s*[a-zA-Z0-9_-]+.*$',
    r'关注公众号.*$',
    r'扫一扫.*$',
    r'扫一.*$',
    r'内部资料免费交流.*$',
    r'上岸村.*$',
]

def clean_text(t: str | None) -> str:
    if not t:
        return ""
    for pat in watermark_patterns:
        t = re.sub(pat, '', t, flags=re.IGNORECASE).strip()
    return t

def get_word_pinyin(word: str) -> str:
    py_list = pinyin(word, style=Style.TONE)
    return " ".join([item[0] for item in py_list])

def split_shici_words(raw_title: str) -> list[str]:
    raw_title = raw_title.strip()
    parts = [p.strip() for p in re.split(r'[\s/]+', raw_title) if p.strip()]
    if len(parts) > 1:
        return parts
    if len(raw_title) == 4:
        return [raw_title[:2], raw_title[2:]]
    if len(raw_title) == 6:
        return [raw_title[:2], raw_title[2:4], raw_title[4:]]
    if len(raw_title) == 8:
        return [raw_title[:2], raw_title[2:4], raw_title[4:6], raw_title[6:]]
    return [raw_title]


async def run_import(db_url: str | None = None, data_path: Path = DATA_FILE):
    print("=" * 65)
    print("开始导入《雨菲言语·27言语带背800词》")
    print("=" * 65)

    if not db_url:
        db_url = f"postgresql+asyncpg://{settings.DATABASE_USER}:{settings.DATABASE_PASSWORD}@{settings.DATABASE_HOST}:{settings.DATABASE_PORT}/fba"
    
    print(f"[配置] 数据库目标: {db_url.split('@')[-1] if '@' in db_url else db_url}")
    print(f"[配置] 数据包路径: {data_path}")

    if not data_path.exists():
        print(f"错误: 数据文件不存在: {data_path}")
        return

    with open(data_path, 'r', encoding='utf-8') as f:
        dataset = json.load(f)

    book_info = dataset.get("book_info", {})
    chapters = dataset.get("chapters", [])

    engine = create_async_engine(db_url, echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with session_factory() as db:
        # 1. 检查并执行 DDL
        print("\n[1/5] 检查/创建辨析组表结构 (gk_hanyu_group / gk_hanyu_group_item)...")
        for stmt in DDL_CREATE_GROUP_TABLES.strip().split(';'):
            stmt = stmt.strip()
            if stmt:
                await db.execute(text(stmt))
        await db.commit()
        print("  ✓ 表结构检查完成")

        # 2. 定位或创建词书 (Wordbook)
        print("\n[2/5] 定位或创建词书元数据...")
        book_name = book_info.get("name", "雨菲言语·27言语带背800词")
        stmt = select(GkHanyuWordbook).where(GkHanyuWordbook.name == book_name)
        res = await db.execute(stmt)
        wb = res.scalar_one_or_none()

        if not wb:
            wb = GkHanyuWordbook(
                name=book_name,
                teacher_id=1,
                description=book_info.get("description", ""),
                category=book_info.get("category", "official"),
                word_count=0,
                is_official=book_info.get("is_official", True),
                sort_order=book_info.get("sort_order", 1),
                status=1,
                created_by=1
            )
            db.add(wb)
            await db.flush()
            print(f"  ✓ 新建词书成功: ID={wb.id}, Name={wb.name}")
        else:
            print(f"  ✓ 找到已有词书: ID={wb.id}, Name={wb.name}")

        # 3. 预加载当前数据库已有词典映射 (gk_hanyu)
        print("\n[3/5] 加载底层词汇库映射 (gk_hanyu)...")
        existing_hanyu = {}
        stmt = select(GkHanyu.id, GkHanyu.name)
        res = await db.execute(stmt)
        for hid, hname in res.all():
            existing_hanyu[hname] = hid
        print(f"  ✓ 当前数据库已有底层词汇: {len(existing_hanyu)} 条")

        # 4. 清理当前词书已有关联条目及旧辨析组，确保幂等性
        print("\n[4/5] 准备数据写入环境 (清空旧关联条目)...")
        await db.execute(text(f"DELETE FROM gk_hanyu_wordbook_entry WHERE wordbook_id = {wb.id}"))
        await db.execute(text("DELETE FROM gk_hanyu_group WHERE category IN ('成语辨析', '实词辨析', '实词400组')"))
        await db.flush()

        # 辅助函数：获取或插入 gk_hanyu
        new_hanyu_count = 0
        async def ensure_hanyu(word: str, word_type: str, default_def: str | None = None) -> int:
            nonlocal new_hanyu_count, existing_hanyu
            word = word.strip()
            if not word:
                return 0
            if word in existing_hanyu:
                return existing_hanyu[word]
            
            new_h = GkHanyu(
                name=word,
                type=word_type,
                pinyin=get_word_pinyin(word),
                definition_info={'definition': default_def} if default_def else None,
                created_by=1
            )
            db.add(new_h)
            await db.flush()
            existing_hanyu[word] = new_h.id
            new_hanyu_count += 1
            return new_h.id

        # 5. 依次导入 5 个章节
        print("\n[5/5] 开始按章节结构化导入数据...")
        current_sort_order = 0
        total_groups_inserted = 0
        total_group_items_inserted = 0
        total_wb_entries_inserted = 0

        for ch_idx, ch in enumerate(chapters, 1):
            ch_name = ch.get("chapter_name", f"第{ch_idx}章")
            ch_cat = ch.get("category", "")
            ch_type = ch.get("type", "word")
            print(f"\n  ▶ 处理 [{ch_idx}/5] {ch_name} ({ch_type}类型)...")

            if ch_type == "word":
                items = ch.get("items", [])
                for it in items:
                    w = it.get("word", "").strip()
                    if not w:
                        continue
                    meaning = clean_text(it.get("meaning", ""))
                    word_type = '成语' if len(w) >= 4 and ch_cat == '成语积累' else '词语'
                    hid = await ensure_hanyu(w, word_type, meaning)

                    current_sort_order += 1
                    entry = GkHanyuWordbookEntry(
                        wordbook_id=wb.id,
                        hanyu_id=hid,
                        group_name=it.get("group_name", ch_name),
                        category=ch_cat,
                        meaning=meaning,
                        commentary=it.get("commentary"),
                        sort_order=current_sort_order
                    )
                    db.add(entry)
                    total_wb_entries_inserted += 1

            elif ch_type == "group":
                groups = ch.get("groups", [])
                for g_idx, g in enumerate(groups, 1):
                    g_title = g.get("title", "")
                    g_no = str(g.get("group_no", g_idx))
                    summary = clean_text(g.get("summary", ""))

                    # 创建辨析组主表
                    group_obj = GkHanyuGroup(
                        title=g_title,
                        group_no=g_no,
                        category=ch_cat,
                        summary=summary,
                        sort_order=g_idx,
                        created_by=1
                    )
                    db.add(group_obj)
                    await db.flush()
                    total_groups_inserted += 1

                    # 处理成员明细
                    items = g.get("items", [])
                    # 若 items 为空（如实词400组），从 title 拆分词汇
                    if not items and "words" in g:
                        items = [{"word": w, "emphasis": summary, "collocation": None} for w in g["words"]]
                    elif not items:
                        items = [{"word": w, "emphasis": summary, "collocation": None} for w in split_shici_words(g_title)]

                    for item_idx, it in enumerate(items, 1):
                        w = it.get("word", "").strip()
                        if not w:
                            continue
                        emp = clean_text(it.get("emphasis", ""))
                        colloc = it.get("collocation")
                        word_type = '成语' if ch_cat == '成语辨析' else '词语'
                        hid = await ensure_hanyu(w, word_type, emp)

                        # 插入明细表
                        g_item = GkHanyuGroupItem(
                            group_id=group_obj.id,
                            hanyu_id=hid,
                            word=w,
                            emphasis=emp,
                            collocation=colloc,
                            sort_order=item_idx
                        )
                        db.add(g_item)
                        total_group_items_inserted += 1

                        # 插入词本条目（若该词本尚未包含该词，则加入条目）
                        res_exists = await db.execute(
                            select(GkHanyuWordbookEntry.id).where(
                                GkHanyuWordbookEntry.wordbook_id == wb.id,
                                GkHanyuWordbookEntry.hanyu_id == hid
                            )
                        )
                        if not res_exists.scalar_one_or_none():
                            current_sort_order += 1
                            wb_entry = GkHanyuWordbookEntry(
                                wordbook_id=wb.id,
                                hanyu_id=hid,
                                group_name=f"{ch_name} · 第{g_no}组",
                                category=ch_cat,
                                meaning=emp if emp else f"【对比组: {g_title}】{summary}",
                                commentary=f"【对比词群】{g_title}\n【解析】\n{summary}",
                                sort_order=current_sort_order
                            )
                            db.add(wb_entry)
                            total_wb_entries_inserted += 1

        # 更新词本条目总数
        wb.word_count = total_wb_entries_inserted
        await db.commit()

        print("\n" + "=" * 65)
        print("✓ 导入成功完成！统计摘要:")
        print("=" * 65)
        print(f"  • 词书名称: 《{wb.name}》 (ID: {wb.id})")
        print(f"  • 词书条目总数 (gk_hanyu_wordbook_entry): {wb.word_count} 条")
        print(f"  • 辨析组总数 (gk_hanyu_group): {total_groups_inserted} 组")
        print(f"  • 辨析组成员数 (gk_hanyu_group_item): {total_group_items_inserted} 条")
        print(f"  • 新增底层词汇 (gk_hanyu): {new_hanyu_count} 个")
        print(f"  • 当前底层词库总规模: {len(existing_hanyu)} 个词")
        print("=" * 65)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='导入雨菲言语800词')
    parser.add_argument('--db-url', type=str, default=None, help='数据库连接字符串 (默认使用 .env 配置)')
    parser.add_argument('--data-file', type=str, default=str(DATA_FILE), help='JSON数据文件路径')
    args = parser.parse_args()

    asyncio.run(run_import(db_url=args.db_url, data_path=Path(args.data_file)))
