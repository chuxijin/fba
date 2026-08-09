#!/usr/bin/env python3
"""导入国考行测试卷到本地 V2 题库，按试卷建独立题库，自动去重。"""

import json
import os
import sys
import time
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ['FBA_DEV'] = '1'

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

TYPE_MAPPING = {
    'single_choice': 'single_choice', '单选题': 'single_choice', '单选': 'single_choice', '单': 'single_choice',
    'multiple_choice': 'multiple_choice', '多选题': 'multiple_choice', '多选': 'multiple_choice', '多': 'multiple_choice',
    'true_false': 'true_false', '判断题': 'true_false', '判断': 'true_false',
    'fill_blank': 'fill_blank', '填空题': 'fill_blank', '填空': 'fill_blank',
    'short_answer': 'short_answer', '简答题': 'short_answer', '简答': 'short_answer',
}


def get_engine():
    from backend.core.conf import settings
    driver = 'psycopg' if settings.DATABASE_TYPE == 'postgresql' else 'pymysql'
    database = settings.DATABASE_SCHEMA
    url = (
        f"{settings.DATABASE_TYPE}+{driver}://{settings.DATABASE_USER}:{settings.DATABASE_PASSWORD}"
        f"@{settings.DATABASE_HOST}:{settings.DATABASE_PORT}/{database}"
    )
    return create_engine(url, pool_pre_ping=True)


def parse_answer(answer_str, question_type):
    if not answer_str:
        return {'correct': ''}
    answer_str = answer_str.strip()
    if question_type == 'single_choice':
        import re
        codes = re.findall(r'[A-Za-z]', answer_str.upper())
        return {'correct': codes[0]} if codes else {'correct': answer_str}
    if question_type == 'multiple_choice':
        import re
        codes = re.findall(r'[A-Za-z]', answer_str.upper())
        return {'correct': sorted(set(codes))} if codes else {'correct': [answer_str]}
    if question_type == 'true_false':
        normalized = answer_str.lower().strip()
        if normalized in ('对', '正确', 'true', 't', '1', '是', 'right', 'yes', 'y'):
            return {'correct': True}
        return {'correct': False}
    parts = [p.strip() for p in answer_str.replace('，', ',').split(',') if p.strip()]
    return {'correct': parts if parts else [answer_str]}


def parse_explanations(row):
    result = []
    for key, val in row.items():
        k = key.strip().replace(' ', '_').replace('-', '_')
        if k.startswith('explanation_'):
            exp_type = k[len('explanation_'):]
            if exp_type and val and str(val).strip():
                result.append({'explanation_type': exp_type, 'content': str(val).strip()})
    if not result:
        result.append({'explanation_type': 'default', 'content': '暂无解析'})
    return result


def parse_options(row):
    options = []
    for letter in 'ABCDE':
        val = row.get(f'option_{letter}')
        if val is not None and str(val).strip():
            options.append({
                'option_code': letter,
                'content': str(val).strip(),
                'sort_order': ord(letter) - ord('A'),
            })
    return options


def item_key_exists(conn, item_key):
    row = conn.execute(
        text("SELECT 1 FROM qbank_v2_bank_item WHERE item_key = :key AND deleted = 0 LIMIT 1"),
        {'key': item_key}
    ).fetchone()
    return row is not None


def get_or_create_sections(conn, revision_id, row):
    """根据 section_l1/l2/l3 获取或创建章节，返回 section_id"""
    l1 = row.get('section_l1')
    l2 = row.get('section_l2')
    l3 = row.get('section_l3')
    parts = [p for p in [l1, l2, l3] if p and str(p).strip()]
    if not parts:
        return None

    section_id = None
    parent_id = None
    for i, name in enumerate(parts):
        key = f'l{i}/{name}'
        existing = conn.execute(
            text("SELECT id FROM qbank_v2_bank_section "
                 "WHERE bank_revision_id = :rid AND code = :code AND deleted = 0"),
            {'rid': revision_id, 'code': key}
        ).fetchone()
        if existing:
            section_id = existing[0]
            parent_id = section_id
        else:
            r = conn.execute(
                text("INSERT INTO qbank_v2_bank_section "
                     "(bank_revision_id, code, name, parent_id, depth, sort_order, created_by, created_time) "
                     "VALUES (:rid, :code, :name, :pid, :depth, 0, 1, NOW()) "
                     "RETURNING id"),
                {'rid': revision_id, 'code': key, 'name': name, 'pid': parent_id, 'depth': i}
            )
            section_id = r.fetchone()[0]
            parent_id = section_id
            conn.commit()
    return section_id


def import_file(conn, file_path):
    df = pd.read_excel(file_path, sheet_name=0, dtype=str)
    df = df.where(df.notna(), None)

    # 从文件名提取试卷信息
    fname = Path(file_path).stem  # e.g. "2026_PAPER_GWY_XC_NAT_2026_DS_..."
    parts = fname.split('_', 3)  # ["2026", "PAPER", "GWY", "XC_NAT_2026_DS_..."]
    bank_year = parts[0] if parts else ''
    bank_name_parts = fname.split('_', 4)
    bank_code = bank_name_parts[1] if len(bank_name_parts) > 1 else 'import'
    bank_name = bank_name_parts[4].replace('_', '') if len(bank_name_parts) > 4 else fname

    # 直接使用文件名中的完整名称
    # 尝试从原始文件路径获取更好名称
    stem = Path(file_path).stem
    # 去掉前导年份和编码前缀
    display_name = stem
    # 去掉 年份_CODE_ 前缀
    import re
    m = re.match(r'\d{4}_[A-Z_]+_(.+)', stem)
    if m:
        display_name = m.group(1)

    print(f'  Importing: {display_name}')

    rows = []
    for _, r in df.iterrows():
        row = {}
        for col in df.columns:
            cc = str(col).strip().replace(' ', '_').replace('-', '_')
            val = r[col]
            if pd.notna(val) and val is not None:
                row[cc] = str(val).strip()
        if not row.get('stem'):
            continue
        rows.append(row)

    if not rows:
        print(f'    No valid rows')
        return

    # 读取材料表（第二个 sheet，可选）
    material_rows = []
    try:
        mdf = pd.read_excel(file_path, sheet_name='材料', dtype=str)
        mdf = mdf.where(mdf.notna(), None)
        for _, r in mdf.iterrows():
            mrow = {}
            for col in mdf.columns:
                cc = str(col).strip().replace(' ', '_').replace('-', '_')
                val = r[col]
                if pd.notna(val) and val is not None:
                    mrow[cc] = str(val).strip()
            if mrow.get('material_code') and mrow.get('material_content'):
                material_rows.append(mrow)
    except Exception:
        material_rows = []

    # 检查是否全部已存在
    all_existing = all(item_key_exists(conn, row.get('item_key', '')) for row in rows if row.get('item_key'))
    if all_existing and rows[0].get('item_key'):
        print(f'    All {len(rows)} questions already exist, skipped')
        return

    # 创建题库
    import random
    code = f'imp_nat_{int(time.time())}_{random.randint(1000, 9999)}'
    r = conn.execute(
        text("INSERT INTO qbank_v2_bank (code, owner_id, visibility, status, created_by, created_time) "
             "VALUES (:code, NULL, 'public', 'active', 1, NOW()) RETURNING id"),
        {'code': code}
    )
    bank_id = r.fetchone()[0]

    r = conn.execute(
        text("INSERT INTO qbank_v2_bank_revision "
             "(bank_id, revision_no, name, bank_kind, settings, question_count, total_score, status, created_by, created_time) "
             "VALUES (:bid, 1, :name, 'paper', '{}'::jsonb, 0, 0, 'draft', 1, NOW()) RETURNING id"),
        {'bid': bank_id, 'name': display_name}
    )
    revision_id = r.fetchone()[0]
    conn.commit()

    # 创建材料（material + material_revision + 设置 current_revision_id）
    material_code_to_id = {}
    for mrow in material_rows:
        mcode = mrow['material_code']
        existing = conn.execute(
            text("SELECT id FROM qbank_v2_material WHERE code = :code AND deleted = 0"),
            {'code': mcode}
        ).fetchone()
        if existing:
            material_code_to_id[mcode] = existing[0]
            continue

        mid = conn.execute(
            text("INSERT INTO qbank_v2_material (code, status, created_by, created_time) "
                 "VALUES (:code, 'active', 1, NOW()) RETURNING id"),
            {'code': mcode}
        ).fetchone()[0]

        mrev = conn.execute(
            text("INSERT INTO qbank_v2_material_revision "
                 "(material_id, revision_no, title, content, content_format, structured_data, "
                 "status, published_by, published_time, created_by, created_time) "
                 "VALUES (:mid, 1, :title, :content, 'html', '{}'::jsonb, "
                 "'published', 1, NOW(), 1, NOW()) RETURNING id"),
            {'mid': mid, 'title': mrow.get('material_title') or mcode,
             'content': mrow['material_content']}
        ).fetchone()[0]
        conn.execute(
            text("UPDATE qbank_v2_material SET current_revision_id = :rid WHERE id = :mid"),
            {'rid': mrev, 'mid': mid}
        )
        conn.commit()
        material_code_to_id[mcode] = mid

    success = 0
    skipped = 0
    for idx, row in enumerate(rows):
        item_key = row.get('item_key', '')
        if item_key and item_key_exists(conn, item_key):
            skipped += 1
            continue

        qtype = TYPE_MAPPING.get(row.get('question_type', ''), row.get('question_type', 'single_choice'))
        options = parse_options(row)
        answer_data = parse_answer(row.get('answer', ''), qtype)
        explanations = parse_explanations(row)
        stem = row['stem']
        score = Decimal(str(row.get('score', '1') or '1'))

        # 创建题目
        qcode = f'{code}_{item_key or f"q{idx:04d}"}'
        existing_q = conn.execute(
            text("SELECT id FROM qbank_v2_question WHERE code = :code AND deleted = 0"),
            {'code': qcode}
        ).fetchone()
        if existing_q:
            question_id = existing_q[0]
        else:
            r = conn.execute(
                text("INSERT INTO qbank_v2_question "
                     "(code, owner_id, visibility, origin_type, status, stem, content_format, "
                     "question_type, option_data, default_score, created_by, created_time) "
                     "VALUES (:code, NULL, 'public', 'imported', 'active', :stem, 'html', "
                     ":qtype, CAST(:opts AS jsonb), :score, 1, NOW()) RETURNING id"),
                {'code': qcode, 'stem': stem, 'qtype': qtype,
                 'opts': json.dumps(options, ensure_ascii=False),
                 'score': float(score)}
            )
            question_id = r.fetchone()[0]

            # 创建答案
            conn.execute(
                text("INSERT INTO qbank_v2_question_answer "
                     "(question_id, answer_data, grading_method, grading_config, created_by, created_time) "
                     "VALUES (:qid, CAST(:ad AS jsonb), 'exact', '{}'::jsonb, 1, NOW())"),
                {'qid': question_id, 'ad': json.dumps(answer_data, ensure_ascii=False)}
            )

            # 创建解析
            is_first = True
            for exp in explanations:
                conn.execute(
                    text("INSERT INTO qbank_v2_question_explanation "
                         "(question_id, content, explanation_type, is_default, status, created_by, created_time) "
                         "VALUES (:qid, :content, :etype, :is_default, 'published', 1, NOW())"),
                    {'qid': question_id, 'content': exp['content'],
                     'etype': exp['explanation_type'], 'is_default': is_first}
                )
                is_first = False

        # 创建章节（如果需要）
        section_id = get_or_create_sections(conn, revision_id, row)

        # 创建 bank_item
        conn.execute(
            text("INSERT INTO qbank_v2_bank_item "
                 "(bank_revision_id, item_key, question_id, section_id, score, sort_order, "
                 "is_required, is_active, settings, created_by, created_time) "
                 "VALUES (:rid, :ik, :qid, :sid, :score, :sort, "
                 "true, true, '{}'::jsonb, 1, NOW())"),
            {'rid': revision_id, 'ik': item_key or f'q{idx:04d}',
             'qid': question_id, 'sid': section_id,
             'score': float(score), 'sort': idx}
        )

        # 关联材料（material_code 支持逗号分隔多材料）
        material_codes = [
            m.strip() for m in str(row.get('material_code', '') or '').split(',') if m.strip()
        ]
        for sort_no, mcode in enumerate(material_codes, start=1):
            mid = material_code_to_id.get(mcode)
            if mid is None:
                continue
            mrev = conn.execute(
                text("SELECT id FROM qbank_v2_material_revision "
                     "WHERE material_id = :mid AND revision_no = 1 AND deleted = 0"),
                {'mid': mid}
            ).fetchone()
            if mrev is None:
                continue
            conn.execute(
                text("INSERT INTO qbank_v2_question_material "
                     "(question_id, material_id, material_revision_id, role, sort_order, display_config, "
                     "created_by, created_time) "
                     "VALUES (:qid, :mid, :mrev, 'passage', :sort, '{}'::jsonb, 1, NOW()) "
                     "ON CONFLICT (question_id, material_id, role, deleted) DO NOTHING"),
                {'qid': question_id, 'mid': mid, 'mrev': mrev[0], 'sort': sort_no}
            )

        success += 1
        conn.commit()

    # 更新题量快照
    conn.execute(
        text("UPDATE qbank_v2_bank_revision SET question_count = :cnt WHERE id = :id"),
        {'cnt': success, 'id': revision_id}
    )
    conn.commit()

    print(f'    Imported {success} questions, {skipped} skipped')
    return bank_id, revision_id


def fix_sequences(conn):
    """修复所有自增序列"""
    tables = [
        'qbank_v2_bank', 'qbank_v2_bank_revision', 'qbank_v2_bank_item',
        'qbank_v2_bank_section', 'qbank_v2_question', 'qbank_v2_question_answer',
        'qbank_v2_question_explanation', 'qbank_v2_material',
        'qbank_v2_material_revision', 'qbank_v2_question_material',
    ]
    for table in tables:
        conn.execute(text(
            f"SELECT setval('{table}_id_seq', COALESCE((SELECT MAX(id) FROM {table}), 0) + 1)"
        ))
    conn.commit()


def main():
    engine = get_engine()
    outputs_dir = Path(__file__).resolve().parent / 'outputs'
    files = sorted(outputs_dir.glob('*PAPER_GWY_XC_NAT*.xlsx'))

    if not files:
        print('No XLSX files found in outputs/')
        return

    print(f'Found {len(files)} paper files\n')

    conn = engine.connect()
    print('Fixing sequences...')
    fix_sequences(conn)
    total_imported = 0

    for f in files:
        result = import_file(conn, f)
        if result:
            total_imported += 1

    conn.close()
    print(f'\nDone! Imported {total_imported} paper banks')


if __name__ == '__main__':
    main()
