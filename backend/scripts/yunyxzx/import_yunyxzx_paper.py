#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
从云易学（yunyxzx）接口拉取单套试卷题目，导入本地 V2 题库并按合集挂载。

V1 版为异步 ORM 模型，本版改造为 V2 表结构（同步 SQLAlchemy）：
    qbank_v2_bank / qbank_v2_bank_revision / qbank_v2_bank_section /
    qbank_v2_question / qbank_v2_question_answer / qbank_v2_question_explanation /
    qbank_v2_bank_item / qbank_v2_collection / qbank_v2_collection_bank

用法:
    # 先 dry-run 预检（只读，不写入任何数据）
    python backend/scripts/yunyxzx/import_yunyxzx_paper.py \
        --paper-id 12345 --paper-name "云易学XX试卷" \
        --collection-code qb_kp_xxx --env prod --dry-run

    # 正式导入（开发库默认；--env prod 写生产库）
    python backend/scripts/yunyxzx/import_yunyxzx_paper.py \
        --paper-id 12345 --paper-name "云易学XX试卷" \
        --bank-code qb_xxx --collection-code qb_kp_xxx --env dev

    # 使用本地抓包 JSON（不请求网络）
    python backend/scripts/yunyxzx/import_yunyxzx_paper.py \
        --input-json response.json --paper-name "云易学XX试卷" \
        --collection-code qb_kp_xxx --env dev

说明:
    - 章节按题型自动分组（如 单选题/多选题），--no-chapter 则不建章节
    - --chapter-name 传入后所有题目归入同一章节
    - item_key 取远端题目 id，重复导入自动跳过
"""

import argparse
import json
import re
import sys
from decimal import Decimal
from pathlib import Path

import httpx
import pandas as pd
from sqlalchemy import bindparam, create_engine, text

SOURCE = 'yunyxzx'
API_URL = 'https://www.yunyxzx.com/huikao_pc/querySubjectList'
DEFAULT_CREATED_BY = 1

TYPE_LABELS = {
    1: '单选题',
    2: '多选题',
    3: '判断题',
    4: '填空题',
    5: '简答题',
    6: '材料题',
}
# 远端 subType → V2 题型
V2_TYPE_MAP = {
    1: 'single_choice',
    2: 'multiple_choice',
    3: 'true_false',
    4: 'fill_blank',
    5: 'short_answer',
    6: 'short_answer',
}
TYPE_MAPPING = {
    'single_choice': 'single_choice', '单选题': 'single_choice', '单选': 'single_choice',
    'multiple_choice': 'multiple_choice', '多选题': 'multiple_choice', '多选': 'multiple_choice',
    'true_false': 'true_false', '判断题': 'true_false', '判断': 'true_false',
    'fill_blank': 'fill_blank', '填空题': 'fill_blank', '填空': 'fill_blank',
    'short_answer': 'short_answer', '简答题': 'short_answer', '简答': 'short_answer',
    '材料题': 'short_answer', 'material': 'short_answer',
}


def parse_args() -> argparse.Namespace:
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description='从云易学接口导入单套试卷题目（V2）')
    parser.add_argument('--paper-id', required=True, help='远端 sectionId（试卷 ID）')
    parser.add_argument('--paper-name', default='', help='试卷名称，不传则使用 paperId 生成')
    parser.add_argument('--type', dest='qtype', type=int, default=2, help='远端接口 type 参数（默认 2）')
    parser.add_argument('--bank-code', default='', help='题库编码，不传则自动生成')
    parser.add_argument('--bank-kind', default='practice', choices=['practice', 'paper'], help='题库类型')
    parser.add_argument('--collection-code', default='', help='要挂载的合集 code（按 code 查找，不存在则创建）')
    parser.add_argument('--collection-name', default='', help='合集不存在时使用的名称（默认等于 code）')
    parser.add_argument('--parent-collection-code', default='', help='父合集 code（合集不存在时创建父子层级）')
    parser.add_argument('--cookie', default='', help='远端接口 Cookie')
    parser.add_argument('--authorization', default='', help='远端接口 Authorization 请求头')
    parser.add_argument('--input-json', default='', help='本地接口响应 JSON 文件，传入后不再请求网络')
    parser.add_argument('--chapter-name', default='', help='统一章节名称，传入后所有题目归入同一章节，不再按题型拆分')
    parser.add_argument('--no-chapter', action='store_true', help='不创建章节，题目直接挂载到题库')
    parser.add_argument('--dry-run', action='store_true', help='只读预检：统计题目/检查合集与题库冲突，不写入任何数据')
    parser.add_argument('--env', default='dev', choices=['dev', 'prod'], help='目标库环境')
    parser.add_argument('--timeout', type=float, default=30.0, help='接口超时时间')
    return parser.parse_args()


# ---------- 远端解析 ----------

def normalize_text(value) -> str:
    """规范化文本"""
    return str(value or '').replace('\r\n', '\n').strip()


def normalize_html(value) -> str:
    """规范化富文本"""
    return normalize_text(value).replace('\n', '<br/>')


def build_bank_code(paper_id: str, bank_code: str) -> str:
    """构建题库编码"""
    if bank_code:
        return bank_code[:64]
    return f'YUNYXZX_{paper_id}'[:64]


def parse_year(paper_name: str):
    """从试卷名称提取年份"""
    matched = re.search(r'(?<!\d)(20\d{2}|19\d{2})(?!\d)', paper_name)
    if not matched:
        return None
    return int(matched.group(1))


def parse_options(raw) -> list:
    """解析选项，返回 [{option_code, content, sort_order}]"""
    text = normalize_text(raw)
    if not text:
        return []

    options = []
    for index, part in enumerate(text.split('|'), start=1):
        item = part.strip()
        matched = re.match(r'^([A-Z])[\.\．、\s]*(.*)$', item, flags=re.IGNORECASE)
        if matched:
            code = matched.group(1).upper()
            content = matched.group(2).strip()
        else:
            code = chr(ord('A') + index - 1)
            content = item
        if content:
            options.append({
                'option_code': code,
                'content': content,
                'sort_order': index - 1,
            })
    return options


def normalize_answer(answer) -> str:
    """规范化答案（仅保留字母/数字/汉字）"""
    return re.sub(r'[^A-Za-z0-9\u4e00-\u9fff]', '', normalize_text(answer)).upper()


def infer_question_type(sub_type: int, answer: str, options: list) -> str:
    """推断 V2 题型"""
    normalized_answer = normalize_answer(answer)
    if sub_type == 1 and len(normalized_answer) > 1:
        return 'multiple_choice'
    if sub_type == 3:
        return 'true_false'
    if len(options) == 2:
        option_text = ''.join(o['content'] for o in options)
        if '正确' in option_text and '错误' in option_text:
            return 'true_false'
    return V2_TYPE_MAP.get(sub_type, 'single_choice')


def build_answer_data(question_type: str, answer) -> dict:
    """按 V2 题型构建 answer_data"""
    if question_type == 'single_choice':
        codes = re.findall(r'[A-Z]', normalize_answer(answer))
        return {'correct': codes[0]} if codes else {'correct': str(answer or '')}
    if question_type == 'multiple_choice':
        codes = re.findall(r'[A-Z]', normalize_answer(answer))
        return {'correct': sorted(set(codes))} if codes else {'correct': [str(answer or '')]}
    if question_type == 'true_false':
        low = normalize_answer(answer).lower()
        if any(k in low for k in ('对', '正', '是', '正确', 'true', 'yes', 'y', 't', '1', 'a')):
            return {'correct': True}
        return {'correct': False}
    parts = [p.strip() for p in str(answer or '').replace('，', ',').split(',') if p.strip()]
    return {'correct': parts if parts else [str(answer or '')]}


def chapter_label(sub_type: int, group_key: str) -> str:
    """获取章节名称"""
    return TYPE_LABELS.get(sub_type) or f'第 {group_key} 部分'


def iter_remote_questions(payload) -> list:
    """展开远端题目，返回题目 dict 列表"""
    questions = []
    if not isinstance(payload, list):
        return questions

    def collect(item: dict, group_key: str) -> None:
        children = item.get('childre') or item.get('children') or []
        if isinstance(children, list):
            for child in children:
                if isinstance(child, dict):
                    collect(child, group_key)

        issue = normalize_html(item.get('issue') or item.get('stem'))
        source_id = normalize_text(item.get('id'))
        if not source_id or not issue:
            return

        sub_type = int(item.get('subType') or 1)
        options = parse_options(item.get('sOption'))
        answer = normalize_text(item.get('answer'))
        qtype = infer_question_type(sub_type, answer, options)
        questions.append({
            'source_id': source_id,
            'group_key': group_key,
            'sub_type': sub_type,
            'question_type': qtype,
            'stem': issue,
            'options': options,
            'answer': answer,
            'answer_data': build_answer_data(qtype, answer),
            'analysis': normalize_html(item.get('analysis')),
            'sort_order': int(item.get('order') or len(questions) + 1),
            'raw': item,
        })

    for group in payload:
        if not isinstance(group, dict):
            continue
        for group_key, items in group.items():
            if not isinstance(items, list):
                continue
            for item in items:
                if isinstance(item, dict):
                    collect(item, str(group_key))
    return questions


def parse_response_payload(payload: dict) -> list:
    """解析接口响应"""
    if payload.get('code') != 0:
        raise RuntimeError(f'远端接口返回失败: {payload.get("msg") or payload}')
    return iter_remote_questions(payload.get('data'))


def load_questions_from_json(path: str) -> list:
    """从本地 JSON 加载题目"""
    with open(path, encoding='utf-8') as file:
        payload = json.load(file)
    if isinstance(payload, list):
        return iter_remote_questions(payload)
    if isinstance(payload, dict):
        return parse_response_payload(payload)
    raise RuntimeError('JSON 文件格式不支持')


def fetch_paper_questions(section_id: str, qtype: int = 2, cookie: str = '', authorization: str = '',
                          timeout: float = 30.0) -> list:
    """拉取远端试卷题目（querySubjectList?sectionId=..&type=..）"""
    headers = {
        'User-Agent': 'Mozilla/5.0',
        'Referer': 'https://www.yunyxzx.com/',
    }
    if cookie:
        headers['Cookie'] = cookie
    if authorization:
        headers['authorization'] = authorization
    response = httpx.get(API_URL, params={'sectionId': section_id, 'type': qtype},
                         headers=headers, timeout=timeout)
    response.raise_for_status()
    return parse_response_payload(response.json())


# ---------- 数据库（V2） ----------

def load_env(path: Path) -> dict:
    """读取 .env 文件"""
    env = {}
    for line in Path(path).read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, _, val = line.partition('=')
        env[key.strip()] = val.strip().strip("'").strip('"')
    return env


def get_engine(env: str):
    """按环境构建 SQLAlchemy 引擎"""
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


def fix_sequences(conn) -> None:
    """修复序列，避免手动 INSERT 后主键冲突"""
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


def get_or_create_collection(conn, code, name, parent_id, sort_order=0) -> int:
    """按 code 查找合集，不存在则创建；返回合集 id"""
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


def get_or_create_section(conn, revision_id, code, name, sort_order):
    """获取或创建一级题型章节"""
    existing = conn.execute(
        text("SELECT id FROM qbank_v2_bank_section "
             "WHERE bank_revision_id = :rid AND code = :code AND deleted = 0"),
        {'rid': revision_id, 'code': code}
    ).fetchone()
    if existing:
        return existing[0]
    sid = conn.execute(
        text("INSERT INTO qbank_v2_bank_section "
             "(bank_revision_id, code, name, parent_id, depth, sort_order, created_by, created_time) "
             "VALUES (:rid, :code, :name, NULL, 0, :sort, 1, NOW()) RETURNING id"),
        {'rid': revision_id, 'code': code, 'name': name, 'sort': sort_order}
    ).fetchone()[0]
    conn.commit()
    return sid


def report_dry_run(conn, args, bank_code, questions) -> None:
    """只读预检：不写入任何数据"""
    type_counts = {}
    for q in questions:
        type_counts[q['question_type']] = type_counts.get(q['question_type'], 0) + 1

    source_ids = {q['source_id'] for q in questions}
    dup_existing = 0
    if source_ids:
        dup_existing = conn.execute(
            text("SELECT COUNT(*) FROM qbank_v2_bank_item "
                 "WHERE item_key IN :keys AND deleted = 0").bindparams(
                bindparam('keys', expanding=True)),
            {'keys': tuple(source_ids)}
        ).fetchone()[0]

    report = {
        'dry_run': True,
        'env': args.env,
        'paper_id': args.paper_id,
        'paper_name': args.paper_name,
        'bank_name': args.paper_name or f'云易学试卷 {args.paper_id}',
        'bank_code': bank_code,
        'type_counts': type_counts,
        'rows': len(questions),
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


def main() -> None:
    """运行导入脚本"""
    args = parse_args()

    if args.input_json:
        questions = load_questions_from_json(args.input_json)
    else:
        questions = fetch_paper_questions(
            args.paper_id, args.qtype, args.cookie, args.authorization, args.timeout
        )
    print(f'  fetched: {len(questions)}')

    paper_name = args.paper_name or f'云易学试卷 {args.paper_id}'
    bank_code = build_bank_code(args.paper_id, args.bank_code)
    coll_name = args.collection_name or args.collection_code or bank_code

    eng = get_engine(args.env)
    with eng.connect() as conn:
        if args.dry_run:
            report_dry_run(conn, args, bank_code, questions)
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

        # 2. 创建题库
        bank_id = conn.execute(
            text("INSERT INTO qbank_v2_bank (code, owner_id, visibility, status, created_by, created_time) "
                 "VALUES (:code, NULL, 'public', 'active', 1, NOW()) RETURNING id"),
            {'code': bank_code}
        ).fetchone()[0]
        revision_id = conn.execute(
            text("INSERT INTO qbank_v2_bank_revision "
                 "(bank_id, revision_no, name, bank_kind, settings, question_count, total_score, status, created_by, created_time) "
                 "VALUES (:bid, 1, :name, :kind, '{}'::jsonb, 0, 0, 'published', 1, NOW()) RETURNING id"),
            {'bid': bank_id, 'name': paper_name, 'kind': args.bank_kind}
        ).fetchone()[0]
        conn.commit()

        # 3. 逐题导入
        success = 0
        skipped = 0
        section_cache = {}
        for idx, q in enumerate(questions):
            if not q.get('stem'):
                skipped += 1
                continue
            item_key = q['source_id']
            existing_item = conn.execute(
                text("SELECT 1 FROM qbank_v2_bank_item WHERE item_key = :key AND deleted = 0 LIMIT 1"),
                {'key': item_key}
            ).fetchone()
            if existing_item:
                skipped += 1
                continue

            qcode = f'{bank_code}_{item_key}'
            qtype = TYPE_MAPPING.get(q['question_type'], 'single_choice')
            options = q['options']
            answer_data = q['answer_data']
            stem = q['stem']
            score = Decimal('1')

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

                analysis = q.get('analysis') or '暂无解析'
                conn.execute(
                    text("INSERT INTO qbank_v2_question_explanation "
                         "(question_id, content, explanation_type, is_default, status, created_by, created_time) "
                         "VALUES (:qid, :content, 'default', true, 'published', 1, NOW())"),
                    {'qid': question_id, 'content': analysis}
                )

            # 章节
            section_id = None
            if not args.no_chapter:
                if args.chapter_name:
                    sec_code = '_unified'
                    sec_name = args.chapter_name
                else:
                    sec_code = str(q['sub_type'] or q['group_key'])
                    sec_name = chapter_label(q['sub_type'], q['group_key'])
                if sec_code not in section_cache:
                    section_cache[sec_code] = get_or_create_section(
                        conn, revision_id, sec_code, sec_name, len(section_cache) + 1
                    )
                section_id = section_cache[sec_code]

            conn.execute(
                text("INSERT INTO qbank_v2_bank_item "
                     "(bank_revision_id, item_key, question_id, section_id, score, sort_order, "
                     "is_required, is_active, settings, created_by, created_time) "
                     "VALUES (:rid, :ik, :qid, :sid, :score, :sort, "
                     "true, true, '{}'::jsonb, 1, NOW())"),
                {'rid': revision_id, 'ik': item_key,
                 'qid': question_id, 'sid': section_id,
                 'score': float(score), 'sort': idx}
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

        # 4. 挂载到合集
        if target_collection_id is not None:
            conn.execute(
                text("INSERT INTO qbank_v2_collection_bank "
                     "(collection_id, bank_id, bank_revision_id, follow_latest, display_name, sort_order, is_active, "
                     "created_by, created_time) "
                     "VALUES (:cid, :bid, NULL, true, :dname, 0, true, 1, NOW()) "
                     "ON CONFLICT (collection_id, bank_id, deleted) DO NOTHING"),
                {'cid': target_collection_id, 'bid': bank_id, 'dname': paper_name}
            )
            conn.commit()

        print(json.dumps({
            'env': args.env,
            'bank_id': bank_id,
            'revision_id': revision_id,
            'bank_name': paper_name,
            'bank_code': bank_code,
            'imported': success,
            'skipped': skipped,
            'collection_id': target_collection_id,
        }, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
