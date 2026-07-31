#!/usr/bin/env python3
"""
从题库数据库导出题目为 V2 导入格式的 XLSX

用法:
  python backend/scripts/export_bank_to_excel.py --bank-id 60
  python backend/scripts/export_bank_to_excel.py --bank-id 60,1638
  python backend/scripts/export_bank_to_excel.py --cat-id 20
  python backend/scripts/export_bank_to_excel.py --bank-id 2394 --db-url postgresql://user:pass@host:5432/dbname
"""

import argparse
import os
import re
import sys
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# 路径与 Django/FASTAPI 环境
# ---------------------------------------------------------------------------
_SCRIPT_DIR = Path(__file__).resolve().parent
_BACKEND_DIR = _SCRIPT_DIR.parent
_PROJECT_ROOT = _BACKEND_DIR.parent

for p in [_PROJECT_ROOT, _BACKEND_DIR]:
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

os.environ.setdefault('FBA_DEV', '1')

COLUMNS = [
    'question_type', 'stem', 'answer', 'explanation',
    'option_A', 'option_B', 'option_C', 'option_D', 'option_E',
    'option_F', 'option_G', 'option_H', 'option_I', 'option_J',
    'score', 'difficulty',
    'section_l1', 'section_l2', 'section_l3',
    'knowledge_point', 'item_key',
]

V1_TO_V2_TYPE = {
    'single': 'single_choice',
    'multiple': 'multiple_choice',
    'judgement': 'true_false',
    'fill': 'fill_blank',
    'shortAnswer': 'short_answer',
}


# ---------------------------------------------------------------------------
# 数据库连接
# ---------------------------------------------------------------------------
def _get_engine(db_url: str | None = None):
    from sqlalchemy import create_engine

    if db_url:
        return create_engine(db_url, pool_pre_ping=True)
    from backend.core.conf import settings
    driver = 'psycopg' if settings.DATABASE_TYPE == 'postgresql' else 'pymysql'
    database = settings.DATABASE_SCHEMA
    url = (
        f"{settings.DATABASE_TYPE}+{driver}://{settings.DATABASE_USER}:{settings.DATABASE_PASSWORD}"
        f"@{settings.DATABASE_HOST}:{settings.DATABASE_PORT}/{database}"
    )
    return create_engine(url, pool_pre_ping=True)


# ---------------------------------------------------------------------------
# 查询
# ---------------------------------------------------------------------------
def fetch_banks(engine, bank_ids: list[int] | None, cat_id: int | None) -> list[dict]:
    from sqlalchemy import text

    with engine.connect() as conn:
        if bank_ids:
            placeholders = ','.join(str(b) for b in bank_ids)
            sql = text(
                f"SELECT id, code, name, cat_id FROM fba.study_question_bank "
                f"WHERE id IN ({placeholders}) AND deleted = 0 AND status = 1 "
                f"ORDER BY sort_order, id"
            )
        elif cat_id:
            sql = text(
                f"WITH RECURSIVE cat_tree AS ("
                f"  SELECT id FROM sys_category WHERE id = :cat AND deleted = 0 AND status IS TRUE"
                f"  UNION ALL"
                f"  SELECT c.id FROM sys_category c JOIN cat_tree ct ON c.parent_id = ct.id"
                f"  WHERE c.deleted = 0 AND c.status IS TRUE"
                f")"
                f"SELECT DISTINCT b.id, b.code, b.name, b.cat_id "
                f"FROM fba.study_question_bank b "
                f"JOIN fba.study_question_bank_mount m ON m.bank_id = b.id "
                f"WHERE m.cat_id IN (SELECT id FROM cat_tree) "
                f"AND b.deleted = 0 AND b.status = 1 AND m.deleted = 0 "
                f"ORDER BY b.sort_order, b.id"
            )
        else:
            return []
        rows = conn.execute(sql, {'cat': cat_id} if cat_id else {}).mappings().all()
        return [dict(r) for r in rows]


def fetch_chapters(engine, bank_id: int) -> list[dict]:
    from sqlalchemy import text

    with engine.connect() as conn:
        rows = conn.execute(text(
            "SELECT id, name, parent_id, level FROM fba.study_question_chapter "
            "WHERE bank_id = :bid AND deleted = 0 AND status = 1 "
            "ORDER BY level, sort_order, id"
        ), {'bid': bank_id}).mappings().all()
        return [dict(r) for r in rows]


def fetch_placements(engine, bank_id: int) -> list[dict]:
    from sqlalchemy import text

    with engine.connect() as conn:
        rows = conn.execute(text(
            "SELECT question_id, chapter_id, sort_order, score "
            "FROM fba.study_question_placement "
            "WHERE bank_id = :bid AND deleted = 0 AND is_active = TRUE "
            "ORDER BY sort_order, id"
        ), {'bid': bank_id}).mappings().all()
        return [dict(r) for r in rows]


def fetch_questions(engine, qids: list[int]) -> dict[int, dict]:
    if not qids:
        return {}
    from sqlalchemy import text

    placeholders = ','.join(str(q) for q in qids)
    with engine.connect() as conn:
        rows = conn.execute(text(
            f"SELECT id, type, stem, options, default_score, difficulty, knowledge_point "
            f"FROM fba.study_question WHERE id IN ({placeholders}) AND deleted = 0"
        )).mappings().all()
        arows = conn.execute(text(
            f"SELECT question_id, answer_data, content FROM fba.study_question_analysis "
            f"WHERE question_id IN ({placeholders}) AND deleted = 0 AND is_default = TRUE"
        )).mappings().all()

    qmap: dict[int, dict] = {}
    for r in rows:
        qmap[int(r.id)] = dict(r)
    for r in arows:
        qid = int(r.question_id)
        if qid in qmap:
            qmap[qid]['answer_data'] = r.answer_data
            qmap[qid]['analysis_content'] = r.content
    return qmap


# ---------------------------------------------------------------------------
# 数据转换
# ---------------------------------------------------------------------------
def parse_answer(answer_data: Any, v1_type: str) -> str:
    if not answer_data:
        return ''
    if isinstance(answer_data, str):
        return answer_data
    if isinstance(answer_data, dict):
        correct = answer_data.get('correct')
        if correct is None:
            return ''
        if isinstance(correct, list):
            return ','.join(str(c) for c in correct)
        if isinstance(correct, bool):
            return '对' if correct else '错'
        return str(correct)
    return str(answer_data)


def parse_options(options_data: Any) -> dict[str, str]:
    result: dict[str, str] = {}
    if not options_data:
        return result
    if isinstance(options_data, dict):
        for k, v in options_data.items():
            if isinstance(v, dict):
                result[k.upper()] = v.get('content', '')
            else:
                result[k.upper()] = str(v)
    elif isinstance(options_data, list):
        for item in options_data:
            if isinstance(item, dict):
                code = item.get('option_code', item.get('code', '')).upper()
                content = item.get('content', '')
                if code:
                    result[code] = content
    return result


def chapter_path(chapters: list[dict], ch_id: int | None):
    if not ch_id:
        return None, None, None
    cmap = {c['id']: c for c in chapters}
    names = []
    cid = ch_id
    while cid and cid in cmap:
        names.append(cmap[cid]['name'])
        cid = cmap[cid].get('parent_id')
    names.reverse()
    return (names[0] if len(names) > 0 else None,
            names[1] if len(names) > 1 else None,
            names[2] if len(names) > 2 else None)


def safe_filename(name: str) -> str:
    name = re.sub(r'[\\/:*?"<>|]', '_', name)
    name = re.sub(r'\s+', '_', name)
    return name.strip('_. ')


# ---------------------------------------------------------------------------
# 导出
# ---------------------------------------------------------------------------
def export_bank(engine, bank: dict, output_dir: Path) -> Path | None:
    bank_id = bank['id']
    bank_name = bank['name']
    bank_code = bank['code']
    print(f'  [导出] {bank_name} ({bank_code}) ...')

    chapters = fetch_chapters(engine, bank_id)
    placements = fetch_placements(engine, bank_id)
    qids = [p['question_id'] for p in placements]
    qmap = fetch_questions(engine, qids)

    rows: list[list[Any]] = []
    for idx, p in enumerate(placements):
        q = qmap.get(p['question_id'])
        if not q:
            continue

        v1_type = q.get('type', 'single')
        v2_type = V1_TO_V2_TYPE.get(v1_type, 'single_choice')
        stem = q.get('stem', '')
        score = float(q.get('default_score') or p.get('score') or 1)
        diff = q.get('difficulty')

        opts = parse_options(q.get('options', {}))
        answer = parse_answer(q.get('answer_data'), v1_type)
        analysis = q.get('analysis_content', '')

        kp_raw = q.get('knowledge_point')
        kp = ''
        if kp_raw:
            if isinstance(kp_raw, list):
                kp = ','.join(str(k) for k in kp_raw)
            elif isinstance(kp_raw, dict):
                kp = kp_raw.get('name', '')
            else:
                kp = str(kp_raw)

        l1, l2, l3 = chapter_path(chapters, p.get('chapter_id'))

        row = [v2_type, stem, answer, analysis]
        for letter in 'ABCDEFGHIJ':
            row.append(opts.get(letter, ''))
        row.append(score)
        row.append(diff)
        row.append(l1)
        row.append(l2)
        row.append(l3)
        row.append(kp)
        row.append(f'q{idx+1:04d}')
        rows.append(row)

    if not rows:
        print(f'    (空题库，跳过)')
        return None

    import pandas as pd
    df = pd.DataFrame(rows, columns=COLUMNS)
    filename = f'{bank_code}_{safe_filename(bank_name)}.xlsx'
    filepath = output_dir / filename
    df.to_excel(filepath, index=False, sheet_name='题目')
    print(f'    → {filepath} ({len(rows)} 题)')
    return filepath


def main():
    parser = argparse.ArgumentParser(description='导出题库为 V2 导入格式 XLSX')
    parser.add_argument('--bank-id', help='题库 ID，多个用逗号分隔')
    parser.add_argument('--cat-id', type=int, help='分类 ID，导出分类下全部题库')
    parser.add_argument('--output-dir', default='./exports', help='输出目录')
    parser.add_argument('--db-url', help='数据库连接串（默认使用本地 settings）')
    args = parser.parse_args()

    if not args.bank_id and not args.cat_id:
        parser.print_help()
        print('\n错误：请指定 --bank-id 或 --cat-id')
        sys.exit(1)

    bank_ids = [int(b.strip()) for b in args.bank_id.split(',')] if args.bank_id else None
    engine = _get_engine(args.db_url)
    banks = fetch_banks(engine, bank_ids, args.cat_id)

    if not banks:
        print('未找到匹配的题库')
        sys.exit(1)

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f'找到 {len(banks)} 个题库:\n')
    for bank in banks:
        export_bank(engine, bank, output_dir)
    print(f'\n完成！文件保存在: {output_dir.resolve()}')


if __name__ == '__main__':
    main()
