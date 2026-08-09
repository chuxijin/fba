#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
导入考研兔导出的 V2 格式 Excel 到本地 V2 题库（开发/生产库），并按合集挂载。

用法:
    # 开发库（默认，读取 backend/.env 配置）
    python backend/scripts/kaoyantu/import_to_v2.py \
        --file "C:\\Users\\19396\\Desktop\\27mi1000_v2_final.xlsx" \
        --bank-name "27米1000题" \
        --bank-code qb_mi_27_1000 \
        --collection-code qb_kp_mi_27

    # 先 dry-run 预检（只读，不写入任何数据），确认无误再正式导入
    python backend/scripts/kaoyantu/import_to_v2.py \
        --file "xxx.xlsx" --bank-name "xxx" --bank-code xxx \
        --collection-code xxx --env prod --dry-run

    # 生产库（读取 backend/.env.prod 配置）
    python backend/scripts/kaoyantu/import_to_v2.py \
        --file "C:\\Users\\19396\\Desktop\\27mi1000_v2_final.xlsx" \
        --bank-name "27米1000题" \
        --bank-code qb_mi_27_1000 \
        --collection-code qb_kp_mi_27 \
        --env prod

合集挂载说明:
    合集层级按 code 查找/自动创建。例如要在「米系列题库」下建「米27考研」：
        --parent-collection-code qb_kp_mi --collection-code qb_kp_mi_27
    若合集已存在则直接挂载，不重复创建。
"""

import argparse
import json
import re
import sys
from decimal import Decimal
from pathlib import Path

import pandas as pd
from sqlalchemy import bindparam, create_engine, text

TYPE_MAPPING = {
    'single_choice': 'single_choice', '单选题': 'single_choice', '单选': 'single_choice',
    'multiple_choice': 'multiple_choice', '多选题': 'multiple_choice', '多选': 'multiple_choice',
    'true_false': 'true_false', '判断题': 'true_false', '判断': 'true_false',
    'fill_blank': 'fill_blank', '填空题': 'fill_blank', '填空': 'fill_blank',
    'short_answer': 'short_answer', '简答题': 'short_answer', '简答': 'short_answer',
}


def load_env(path: Path) -> dict:
    """读取 .env 文件，返回 key-value 字典（去除引号）。"""
    env = {}
    for line in Path(path).read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, _, val = line.partition('=')
        env[key.strip()] = val.strip().strip("'").strip('"')
    return env


def get_engine(env: str):
    """按环境构建 SQLAlchemy 引擎。"""
    backend_dir = Path(__file__).resolve().parents[2]
    if env == 'prod':
        env_cfg = load_env(backend_dir / '.env.prod')
        url = (
            f"postgresql+psycopg://{env_cfg['DATABASE_USER']}:{env_cfg['DATABASE_PASSWORD']}"
            f"@{env_cfg['DATABASE_HOST']}:{env_cfg['DATABASE_PORT']}/fba"
        )
        return create_engine(url, pool_pre_ping=True)

    sys.path.insert(0, str(backend_dir))
    os_env = __import__('os')
    os_env.environ.setdefault('FBA_DEV', '1')
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
    answer_str = str(answer_str).strip()
    if question_type == 'single_choice':
        codes = re.findall(r'[A-Za-z]', answer_str.upper())
        return {'correct': codes[0]} if codes else {'correct': answer_str}
    if question_type == 'multiple_choice':
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
        k = str(key).strip().replace(' ', '_').replace('-', '_')
        if k.startswith('explanation_'):
            exp_type = k[len('explanation_'):]
            if exp_type and val and str(val).strip():
                result.append({'explanation_type': exp_type, 'content': str(val).strip()})
    if not result:
        result.append({'explanation_type': 'default', 'content': '暂无解析'})
    return result


def parse_options(row):
    options = []
    for letter in 'ABCDEFGHIJ':
        val = row.get(f'option_{letter}')
        if val is not None and str(val).strip():
            options.append({
                'option_code': letter,
                'content': str(val).strip(),
                'sort_order': ord(letter) - ord('A'),
            })
    return options


def get_or_create_sections(conn, revision_id, row):
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
                     "VALUES (:rid, :code, :name, :pid, :depth, 0, 1, NOW()) RETURNING id"),
                {'rid': revision_id, 'code': key, 'name': name, 'pid': parent_id, 'depth': i}
            )
            section_id = r.fetchone()[0]
            parent_id = section_id
            conn.commit()
    return section_id


def fix_sequences(conn):
    tables = [
        'qbank_v2_bank', 'qbank_v2_bank_revision', 'qbank_v2_bank_item',
        'qbank_v2_bank_section', 'qbank_v2_question', 'qbank_v2_question_answer',
        'qbank_v2_question_explanation', 'qbank_v2_material',
        'qbank_v2_material_revision', 'qbank_v2_question_material',
        'qbank_v2_collection', 'qbank_v2_collection_bank',
    ]
    for table in tables:
        conn.execute(text(
            f"SELECT setval('{table}_id_seq', COALESCE((SELECT MAX(id) FROM {table}), 0) + 1)"
        ))
    conn.commit()


def get_or_create_collection(conn, code, name, parent_id, sort_order=0):
    """按 code 查找合集，不存在则创建；返回合集 id。"""
    existing = conn.execute(
        text("SELECT id FROM qbank_v2_collection WHERE code = :code AND deleted = 0"),
        {'code': code}
    ).fetchone()
    if existing:
        return existing[0]
    cid = conn.execute(
        text("INSERT INTO qbank_v2_collection "
             "(code, name, parent_id, owner_id, visibility, status, sort_order, created_by, created_time) "
             "VALUES (:code, :name, :pid, NULL, 'public', 'active', :sort, 1, NOW()) RETURNING id"),
        {'code': code, 'name': name, 'pid': parent_id, 'sort': sort_order}
    ).fetchone()[0]
    conn.commit()
    print(f'  collection created: {cid} {code} {name}')
    return cid


def report_dry_run(conn, args, bank_code, rows):
    """只读预检：不写入任何数据，仅统计题目与检查冲突。"""
    type_counts = {}
    for row in rows:
        qtype = TYPE_MAPPING.get(row.get('question_type', ''), row.get('question_type', 'single_choice'))
        type_counts[qtype] = type_counts.get(qtype, 0) + 1

    item_keys = {row.get('item_key') for row in rows if row.get('item_key')}
    dup_existing = 0
    if item_keys:
        dup_existing = conn.execute(
            text("SELECT COUNT(*) FROM qbank_v2_bank_item "
                 "WHERE item_key IN :keys AND deleted = 0").bindparams(
                bindparam('keys', expanding=True)),
            {'keys': tuple(item_keys)}
        ).fetchone()[0]

    report = {
        'dry_run': True,
        'env': args.env,
        'file': str(args.file),
        'bank_name': args.bank_name,
        'bank_code': bank_code,
        'type_counts': type_counts,
        'rows': len(rows),
        'item_keys_with_conflicts': dup_existing,
    }
    if args.collection_code:
        existing = conn.execute(
            text("SELECT id, name FROM qbank_v2_collection WHERE code = :code AND deleted = 0"),
            {'code': args.collection_code}
        ).fetchone()
        report['collection'] = {
            'code': args.collection_code,
            'exists': bool(existing),
            'id': existing[0] if existing else None,
            'name': existing[1] if existing else None,
            'will_create': not bool(existing),
        }
    if args.parent_collection_code:
        existing = conn.execute(
            text("SELECT id, name FROM qbank_v2_collection WHERE code = :code AND deleted = 0"),
            {'code': args.parent_collection_code}
        ).fetchone()
        report['parent_collection'] = {
            'code': args.parent_collection_code,
            'exists': bool(existing),
            'id': existing[0] if existing else None,
            'name': existing[1] if existing else None,
            'will_create': not bool(existing),
        }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print('\n[DRY RUN] 预检完成，未写入任何数据。确认无误后去掉 --dry-run 正式导入。')


def main():
    parser = argparse.ArgumentParser(description='导入 V2 格式 Excel 到题库并按合集挂载')
    parser.add_argument('--file', required=True, help='V2 格式 Excel 路径')
    parser.add_argument('--bank-name', required=True, help='题库名称，如 27米1000题')
    parser.add_argument('--bank-code', default=None, help='题库 code（可选，默认自动生成）')
    parser.add_argument('--bank-kind', default='practice', choices=['practice', 'paper'], help='题库类型')
    parser.add_argument('--collection-code', default=None, help='要挂载的合集 code')
    parser.add_argument('--collection-name', default=None, help='合集不存在时使用的名称（默认等于 code）')
    parser.add_argument('--parent-collection-code', default=None, help='父合集 code（合集不存在时创建挂载）')
    parser.add_argument('--env', default='dev', choices=['dev', 'prod'], help='目标库环境')
    parser.add_argument('--dry-run', action='store_true', help='只读预检：统计题目/检查合集与题库冲突，不写入任何数据')
    args = parser.parse_args()

    file_path = Path(args.file)
    if not file_path.exists():
        raise SystemExit(f'文件不存在: {file_path}')

    bank_code = args.bank_code or f'imp_{file_path.stem}'
    coll_name = args.collection_name or args.collection_code or bank_code

    # 2. 读取题目表
    df = pd.read_excel(file_path, sheet_name=0, dtype=str)
    df = df.where(df.notna(), None)
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
    print(f'  rows: {len(rows)}')

    # 材料表（可选）
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
    print(f'  materials: {len(material_rows)}')

    eng = get_engine(args.env)
    with eng.connect() as conn:
        # dry-run：只读预检，不写入任何数据
        if args.dry_run:
            report_dry_run(conn, args, bank_code, rows)
            return

        fix_sequences(conn)

        # 1. 合集挂载层级
        target_collection_id = None
        if args.collection_code:
            parent_id = None
            if args.parent_collection_code:
                parent_id = get_or_create_collection(
                    conn, args.parent_collection_code, args.parent_collection_code, None
                )
            target_collection_id = get_or_create_collection(
                conn, args.collection_code, coll_name, parent_id
            )

        # 3. 创建题库
        bank_id = conn.execute(
            text("INSERT INTO qbank_v2_bank (code, owner_id, visibility, status, created_by, created_time) "
                 "VALUES (:code, NULL, 'public', 'active', 1, NOW()) RETURNING id"),
            {'code': bank_code}
        ).fetchone()[0]
        revision_id = conn.execute(
            text("INSERT INTO qbank_v2_bank_revision "
                 "(bank_id, revision_no, name, bank_kind, settings, question_count, total_score, status, created_by, created_time) "
                 "VALUES (:bid, 1, :name, :kind, '{}'::jsonb, 0, 0, 'published', 1, NOW()) RETURNING id"),
            {'bid': bank_id, 'name': args.bank_name, 'kind': args.bank_kind}
        ).fetchone()[0]
        conn.commit()

        # 4. 材料
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

        # 5. 逐题导入
        success = 0
        skipped = 0
        for idx, row in enumerate(rows):
            item_key = row.get('item_key', '')
            existing_item = conn.execute(
                text("SELECT 1 FROM qbank_v2_bank_item WHERE item_key = :key AND deleted = 0 LIMIT 1"),
                {'key': item_key}
            ).fetchone() if item_key else None
            if existing_item:
                skipped += 1
                continue

            qtype = TYPE_MAPPING.get(row.get('question_type', ''), row.get('question_type', 'single_choice'))
            options = parse_options(row)
            answer_data = parse_answer(row.get('answer', ''), qtype)
            explanations = parse_explanations(row)
            stem = row['stem']
            score = Decimal(str(row.get('score', '1') or '1'))

            qcode = f'{bank_code}_{item_key or f"q{idx:04d}"}'
            existing_q = conn.execute(
                text("SELECT id FROM qbank_v2_question WHERE code = :code AND deleted = 0"),
                {'code': qcode}
            ).fetchone()
            if existing_q:
                question_id = existing_q[0]
            else:
                question_id = conn.execute(
                    text("INSERT INTO qbank_v2_question "
                         "(code, owner_id, visibility, origin_type, status, stem, content_format, "
                         "question_type, option_data, default_score, created_by, created_time) "
                         "VALUES (:code, NULL, 'public', 'imported', 'active', :stem, 'html', "
                         ":qtype, CAST(:opts AS jsonb), :score, 1, NOW()) RETURNING id"),
                    {'code': qcode, 'stem': stem, 'qtype': qtype,
                     'opts': json.dumps(options, ensure_ascii=False),
                     'score': float(score)}
                ).fetchone()[0]

                conn.execute(
                    text("INSERT INTO qbank_v2_question_answer "
                         "(question_id, answer_data, grading_method, grading_config, created_by, created_time) "
                         "VALUES (:qid, CAST(:ad AS jsonb), 'exact', '{}'::jsonb, 1, NOW())"),
                    {'qid': question_id, 'ad': json.dumps(answer_data, ensure_ascii=False)}
                )

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

            section_id = get_or_create_sections(conn, revision_id, row)

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

        total_score = conn.execute(
            text("SELECT COALESCE(SUM(score),0) FROM qbank_v2_bank_item WHERE bank_revision_id = :rid AND deleted=0"),
            {'rid': revision_id}
        ).fetchone()[0]
        conn.execute(
            text("UPDATE qbank_v2_bank_revision SET question_count = :cnt, total_score = :ts WHERE id = :id"),
            {'cnt': success, 'ts': total_score, 'id': revision_id}
        )
        conn.execute(
            text("UPDATE qbank_v2_bank SET current_revision_id = :rid WHERE id = :bid"),
            {'rid': revision_id, 'bid': bank_id}
        )
        conn.commit()

        # 6. 挂载到合集
        if target_collection_id is not None:
            conn.execute(
                text("INSERT INTO qbank_v2_collection_bank "
                     "(collection_id, bank_id, bank_revision_id, follow_latest, display_name, sort_order, is_active, "
                     "created_by, created_time) "
                     "VALUES (:cid, :bid, NULL, true, :dname, 0, true, 1, NOW()) "
                     "ON CONFLICT (collection_id, bank_id, deleted) DO NOTHING"),
                {'cid': target_collection_id, 'bid': bank_id, 'dname': args.bank_name}
            )
            conn.commit()

        print(json.dumps({
            'env': args.env,
            'bank_id': bank_id,
            'revision_id': revision_id,
            'bank_name': args.bank_name,
            'bank_code': bank_code,
            'imported': success,
            'skipped': skipped,
            'materials': len(material_rows),
            'collection_id': target_collection_id,
        }, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
