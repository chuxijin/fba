#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
《花生十三·高频1000词记忆版》自适应导入脚本

功能说明:
1. 自动检查并创建 gk_hanyu_group、gk_hanyu_group_item 表结构 (DDL)。
2. 基于词语名称 (name) 动态匹配数据库底层词汇 gk_hanyu，自动复用已有词 ID，缺则动态补录。
3. 批量幂等导入词书 (gk_hanyu_wordbook)、章节条目 (gk_hanyu_wordbook_entry) 及近义辨析组 (gk_hanyu_group & item)。
4. 完美支持开发环境、测试环境及生产环境无缝执行，零自增 ID 冲突。

使用方法:
  python scripts/import_huasheng13_wordbook.py
  python scripts/import_huasheng13_wordbook.py --db-url "postgresql+asyncpg://user:pass@host:5432/dbname"
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

DATA_FILE = ROOT_DIR / 'scripts' / 'data' / 'huasheng13_1000_words.json'

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

def get_word_pinyin(word: str) -> str:
    py_list = pinyin(word, style=Style.TONE)
    return " ".join([item[0] for item in py_list])

async def run_import(db_url: str | None = None, data_path: Path = DATA_FILE):
    print("=" * 65)
    print("开始导入《花生十三·高频1000词记忆版》")
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
    items = dataset.get("items", [])

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
        book_name = book_info.get("name", "花生十三·高频1000词记忆版")
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
                sort_order=book_info.get("sort_order", 2),
                status=1,
                created_by=1
            )
            db.add(wb)
            await db.flush()
            print(f"  ✓ 新建词书成功: ID={wb.id}, Name={wb.name}")
        else:
            print(f"  ✓ 找到已有词书: ID={wb.id}, Name={wb.name}")

        # 3. 预加载底层词典映射 (gk_hanyu)
        print("\n[3/5] 加载底层词汇库映射 (gk_hanyu)...")
        existing_hanyu = {}
        stmt = select(GkHanyu.id, GkHanyu.name)
        res = await db.execute(stmt)
        for hid, hname in res.all():
            existing_hanyu[hname] = hid
        print(f"  ✓ 当前数据库已有底层词汇: {len(existing_hanyu)} 条")

        # 4. 清理旧关联条目
        print("\n[4/5] 准备数据写入环境 (清空本词书已有条目)...")
        await db.execute(text(f"DELETE FROM gk_hanyu_wordbook_entry WHERE wordbook_id = {wb.id}"))
        await db.execute(text("DELETE FROM gk_hanyu_group WHERE category = '花生十三高频1000词'"))
        await db.flush()

        # 辅助函数：动态插入或获取 gk_hanyu
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

        # 5. 批量写入词本条目与辨析组
        print(f"\n[5/5] 开始导入 {len(items)} 条词汇...")
        inserted_entries = 0
        inserted_hanyu_ids = set()
        group_map = {} # minor_group -> list of items

        for it in items:
            w = it.get("word", "").strip()
            if not w:
                continue
            meaning = it.get("meaning", "").strip()
            comm = it.get("commentary")
            major = it.get("major_group", "高频成语")
            minor = it.get("minor_group", "高频分类")

            word_type = '成语' if len(w) >= 4 else '词语'
            hid = await ensure_hanyu(w, word_type, meaning)

            # 如果该词尚未加入当前词书条目，则插入
            if hid not in inserted_hanyu_ids:
                inserted_entries += 1
                commentary_text = f"【主题大类】{major}\n【应用场景】{minor}"
                if comm:
                    commentary_text += f"\n【考点提示】{comm}"

                entry = GkHanyuWordbookEntry(
                    wordbook_id=wb.id,
                    hanyu_id=hid,
                    group_name=major,
                    category=minor,
                    meaning=meaning,
                    commentary=commentary_text,
                    sort_order=inserted_entries
                )
                db.add(entry)
                inserted_hanyu_ids.add(hid)

            # 聚类到辨析组（辨析组允许多维度出现）
            group_key = f"{major} · {minor}"
            if group_key not in group_map:
                group_map[group_key] = []
            group_map[group_key].append({
                "word": w,
                "hanyu_id": hid,
                "meaning": meaning,
                "commentary": comm
            })

        # 写入辨析组
        print(f"\n  ▶ 正在为 {len(group_map)} 个小类创建主题近义辨析组...")
        total_groups = 0
        total_group_items = 0
        for g_idx, (g_name, g_items) in enumerate(group_map.items(), 1):
            if len(g_items) >= 2: # 2个及以上组成辨析组
                title = " ".join([x["word"] for x in g_items])
                summary = "\n".join([f"【{x['word']}】{x['meaning']}" for x in g_items])
                
                group_obj = GkHanyuGroup(
                    title=title[:128],
                    group_no=str(g_idx),
                    category="花生十三高频1000词",
                    summary=summary,
                    sort_order=g_idx,
                    created_by=1
                )
                db.add(group_obj)
                await db.flush()
                total_groups += 1

                for item_idx, x in enumerate(g_items, 1):
                    g_item = GkHanyuGroupItem(
                        group_id=group_obj.id,
                        hanyu_id=x["hanyu_id"],
                        word=x["word"],
                        emphasis=x["meaning"],
                        collocation=x["commentary"],
                        sort_order=item_idx
                    )
                    db.add(g_item)
                    total_group_items += 1

        # 更新词书条目总数
        wb.word_count = inserted_entries
        await db.commit()

        print("\n" + "=" * 65)
        print("✓ 《花生十三·高频1000词记忆版》导入完成！统计摘要:")
        print("=" * 65)
        print(f"  • 词书名称: 《{wb.name}》 (ID: {wb.id})")
        print(f"  • 词书条目总数 (gk_hanyu_wordbook_entry): {wb.word_count} 条")
        print(f"  • 沉淀主题辨析组 (gk_hanyu_group): {total_groups} 组")
        print(f"  • 辨析组成员数 (gk_hanyu_group_item): {total_group_items} 条")
        print(f"  • 新增底层词汇 (gk_hanyu): {new_hanyu_count} 个")
        print(f"  • 当前底层词库总规模: {len(existing_hanyu)} 个词")
        print("=" * 65)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='导入花生十三高频1000词')
    parser.add_argument('--db-url', type=str, default=None, help='数据库连接字符串 (默认使用 .env 配置)')
    parser.add_argument('--data-file', type=str, default=str(DATA_FILE), help='JSON数据文件路径')
    args = parser.parse_args()

    asyncio.run(run_import(db_url=args.db_url, data_path=Path(args.data_file)))
