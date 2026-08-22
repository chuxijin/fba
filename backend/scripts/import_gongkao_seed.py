#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""导入公考申论 seed 数据到 question_bank_v2（生产库 fba schema）。

两个阶段：
  enrich  - 为已有 short_answer 题目补充多机构参考答案（写入 qbank_v2_question_explanation）
  papers  - 导入 v2 中没有对应 bank 的整卷（bank + 材料 + 题目 + 答案 + 挂合集）

用法（默认 dry-run，--commit 才真正提交）：
  uv run python backend/scripts/import_gongkao_seed.py --sqlite <seed.sqlite3> --phase enrich --dry-run
  uv run python backend/scripts/import_gongkao_seed.py --sqlite <seed.sqlite3> --phase papers --dry-run
  uv run python backend/scripts/import_gongkao_seed.py --sqlite <seed.sqlite3> --phase all --commit
"""

from __future__ import annotations

import argparse
import hashlib
import html
import os
import re
import sqlite3
import sys
import unicodedata

from collections import defaultdict
from datetime import datetime
from decimal import Decimal, InvalidOperation
from difflib import SequenceMatcher
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy import create_engine, text as sa_text  # noqa: E402

DEFAULT_SQLITE = r'D:\100_Work\101_Program\Proj\YanShen\data\gongkao_seed.sqlite3'
DEFAULT_CREATED_BY = 1
FUZZY_MIN_RATIO = 0.90
FUZZY_UNIQUE_GAP = 0.02
TARGET_SCHEMA = 'fba'


def text(statement: str):
    """创建 SQL 文本，并将历史硬编码的 fba schema 映射到当前目标 schema。"""
    return sa_text(statement.replace('fba.', f'{TARGET_SCHEMA}.'))

# 已有 v2 bank 但卷名写法不同的卷（sqlite 卷名 -> 说明），整卷导入时跳过
SKIP_NAME_VARIANTS = {
    '2020年0725公务员多省联考《申论》题（四川上半年B卷）': 'bank:2020年公务员多省联考（四川上半年B卷）',
    '2020年0725公务员多省联考《申论》题（四川上半年C卷）': 'bank:2020年公务员多省联考（四川上半年C卷）',
    '2023年浙江省公考《申论》题（B卷）': 'bank:2023年浙年浙江省公考（B卷）[空bank]',
    '2024年四川省公考《申论》题（县乡、普通选调卷）': 'bank:2024年四川省公考（县乡、普通选调）',
    '2024年四川省公考《申论》题（行政执法卷）': 'bank:2024四年四川省公考（行政执法）',
    '2025年四川省公考《申论》题（县乡、普通选调卷）': 'bank:2025年四川省公考（县乡、普通选调）',
    '2025年四川省公考《申论》题（省市卷）': 'bank:2025年四川省公考（省市）',
    '2025年四川省公考《申论》题（行政执法卷）': 'bank:2025年四川省公考（行政执法）',
}

XUANDIAO_COLLECTION = 'SET_GWY_SL_PROV_XDS'

EXAM_TYPE_COLLECTION = {
    '国考': 'SET_GWY_SL_NAT',
    '公安院校联考': 'SET_GWY_SL_PROV_OTHER',
}

PROVINCE_COLLECTION = {
    '浙江': 'SET_GWY_SL_PROV_ZJ',
    '宁夏': 'SET_GWY_SL_PROV_NX',
    '海南': 'SET_GWY_SL_PROV_HI',
    '重庆': 'SET_GWY_SL_PROV_CQ',
    '四川': 'SET_GWY_SL_PROV_SC',
    '河北': 'SET_GWY_SL_PROV_HEB',
    '福建': 'SET_GWY_SL_PROV_FJ',
    '云南': 'SET_GWY_SL_PROV_YN',
    '天津': 'SET_GWY_SL_PROV_TJ',
    '湖北': 'SET_GWY_SL_PROV_HUB',
    '湖南': 'SET_GWY_SL_PROV_HUN',
    '新疆': 'SET_GWY_SL_PROV_XJ',
    '江西': 'SET_GWY_SL_PROV_JX',
    '河南': 'SET_GWY_SL_PROV_HEN',
    '青海': 'SET_GWY_SL_PROV_QH',
    '上海': 'SET_GWY_SL_PROV_SH',
    '广东': 'SET_GWY_SL_PROV_GD',
    '深圳': 'SET_GWY_SL_PROV_GD',
    '安徽': 'SET_GWY_SL_PROV_AH',
    '江苏': 'SET_GWY_SL_PROV_JS',
    '山东': 'SET_GWY_SL_PROV_SD',
    '陕西': 'SET_GWY_SL_PROV_SNX',
    '甘肃': 'SET_GWY_SL_PROV_GS',
    '山西': 'SET_GWY_SL_PROV_SX',
    '贵州': 'SET_GWY_SL_PROV_GZ',
    '广西': 'SET_GWY_SL_PROV_GX',
    '辽宁': 'SET_GWY_SL_PROV_LN',
    '吉林': 'SET_GWY_SL_PROV_JL',
    '黑龙江': 'SET_GWY_SL_PROV_HLJ',
    '内蒙古': 'SET_GWY_SL_PROV_NMG',
    '北京': 'SET_GWY_SL_PROV_BJ',
    '西藏': 'SET_GWY_SL_PROV_OTHER',
}


def norm_text(s: str) -> str:
    """归一化题干文本用于匹配：剥 HTML、NFKC、全去空白与标点。"""
    if not s:
        return ''
    s = html.unescape(str(s))
    s = re.sub(r'<[^>]+>', '', s)
    s = unicodedata.normalize('NFKC', s)
    s = re.sub(r'[\s\u3000\u200b\u00a0]+', '', s)
    s = re.sub(r'[^\u4e00-\u9fffA-Za-z0-9]', '', s)
    return s.lower()


def to_html_paragraphs(text: str) -> str:
    """纯文本转 <p> 段落 HTML；已是 HTML 则原样返回。"""
    if not text:
        return ''
    if re.search(r'</?[a-zA-Z][^>]*>', str(text)):
        return str(text)
    lines = [line.strip() for line in str(text).splitlines() if line.strip()]
    if not lines:
        return ''
    return ''.join(f'<p>{html.escape(line)}</p>' for line in lines)


def build_stem(prompt: str, requirements: str) -> str:
    """按现有导入惯例拼接题干 HTML（prompt + requirements）。"""
    parts: list[str] = []
    content_html = to_html_paragraphs(prompt)
    if content_html:
        parts.append(content_html)
    require_html = to_html_paragraphs(requirements)
    if require_html:
        parts.append(require_html)
    return ''.join(parts)


def parse_score(text: str) -> Decimal:
    """从题干 `（N分）` 解析分值。"""
    if not text:
        return Decimal('1.00')
    match = re.search(r'[（(]\s*(\d+(?:\.\d+)?)\s*分\s*[）)]', str(text))
    if match:
        try:
            value = Decimal(match.group(1))
        except InvalidOperation:
            return Decimal('1.00')
        if value > 0:
            return value
    return Decimal('1.00')


def canonical_org(answer: dict) -> str:
    org = str(answer.get('canonical_organization') or '').strip()
    if not org:
        org = str(answer.get('organization') or '').strip()
    return org or '机构答案'


def answer_score(answer: dict) -> tuple[int, int, str]:
    """组内择优：已审 > 文本更长 > 创建更早。"""
    reviewed = 1 if int(answer.get('is_reviewed') or 0) else 0
    length = len(str(answer.get('answer_text') or '').strip())
    created = str(answer.get('created_at') or '')
    return (reviewed, length, created)


def pick_best_answers(answers: list[dict]) -> list[dict]:
    """按 canonical_organization 去重，每组取最优一条，按优先级排序。"""
    groups: dict[str, list[dict]] = defaultdict(list)
    for answer in answers:
        text_val = str(answer.get('answer_text') or '').strip()
        if not text_val:
            continue
        groups[canonical_org(answer)].append(answer)
    chosen: list[dict] = []
    for org, items in groups.items():
        best = max(items, key=answer_score)
        best['_org'] = org
        chosen.append(best)
    chosen.sort(key=answer_score, reverse=True)
    return chosen


def make_explanation_type(base: str, used: set[str]) -> str:
    """生成每题内唯一的 explanation_type（<=24 字符，撞名加 hash 后缀）。"""
    base = (base or '机构答案').strip() or '机构答案'
    candidate = base[:24]
    if candidate not in used:
        used.add(candidate)
        return candidate
    digest = hashlib.md5(base.encode('utf-8')).hexdigest()[:4]
    candidate = f'{base[:19]}_{digest}'
    counter = 2
    while candidate in used:
        candidate = f'{base[:19]}_{digest}{counter}'
        counter += 1
    used.add(candidate)
    return candidate


# --------------------------------------------------------------------------- #
# 数据库连接
# --------------------------------------------------------------------------- #

def load_env_file(path: Path) -> dict[str, str]:
    env_cfg: dict[str, str] = {}
    for line in path.read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, _, value = line.partition('=')
        env_cfg[key.strip()] = value.strip().strip('"').strip("'")
    return env_cfg


def get_engine(*, env: str, db_url: str | None):
    if db_url:
        return create_engine(db_url, pool_pre_ping=True)
    envfile = PROJECT_ROOT / 'backend' / ('.env.prod' if env == 'prod' else '.env')
    if not envfile.exists():
        raise SystemExit(f'env 文件不存在: {envfile}')
    env_cfg = load_env_file(envfile)
    user = env_cfg.get('DATABASE_USER')
    password = env_cfg.get('DATABASE_PASSWORD')
    host = env_cfg.get('DATABASE_HOST')
    port = env_cfg.get('DATABASE_PORT')
    if not (user and password and host and port):
        raise SystemExit(f'{envfile} 缺少数据库配置')
    url = (
        f'postgresql+psycopg://{user}:{password}@{host}:{port}'
        f"/{env_cfg.get('DATABASE_SCHEMA', 'fba')}"
    )
    return create_engine(url, pool_pre_ping=True)


# --------------------------------------------------------------------------- #
# SQLite 数据加载
# --------------------------------------------------------------------------- #

def load_sqlite(db_path: str) -> dict:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    papers = [dict(r) for r in cur.execute('SELECT * FROM papers')]
    materials = [dict(r) for r in cur.execute(
        'SELECT paper_id, material_number, title, content FROM paper_materials ORDER BY paper_id, material_number'
    )]
    questions = [dict(r) for r in cur.execute(
        'SELECT id, question_code, exam_type, year, source_province, question_type, prompt, '
        'requirements, word_limit, paper_id, paper_name, question_number FROM questions ORDER BY id'
    )]
    answers = [dict(r) for r in cur.execute(
        'SELECT id, question_id, organization, canonical_organization, answer_text, '
        'is_reviewed, created_at FROM reference_answers ORDER BY id'
    )]
    conn.close()
    return {'papers': papers, 'materials': materials, 'questions': questions, 'answers': answers}


# --------------------------------------------------------------------------- #
# 题干匹配
# --------------------------------------------------------------------------- #

def build_exact_index(prod_questions: list[dict]) -> dict[str, list[int]]:
    index: dict[str, list[int]] = defaultdict(list)
    for q in prod_questions:
        index[q['_n']].append(q['id'])
    return index


def build_run_index(prod_questions: list[dict]) -> dict[str, list[dict]]:
    run_index: dict[str, list[dict]] = defaultdict(list)
    for q in prod_questions:
        n = q['_n']
        for i in range(0, max(0, len(n) - 11)):
            run_index.setdefault(n[i:i + 12], []).append(q)
    return run_index


def fuzzy_unique_best(n: str, run_index: dict[str, list[dict]]) -> tuple[float, dict | None]:
    """返回唯一高相似候选（>=FUZZY_MIN_RATIO 且与第二高差距>=FUZZY_UNIQUE_GAP）。"""
    cand: dict[int, dict] = {}
    seen: set[int] = set()
    for i in range(0, max(0, len(n) - 11)):
        for q in run_index.get(n[i:i + 12], []):
            if q['id'] in seen:
                continue
            seen.add(q['id'])
            cand[q['id']] = q
    scored: list[tuple[float, dict]] = []
    for q in cand.values():
        ratio = SequenceMatcher(None, n, q['_n']).ratio()
        scored.append((ratio, q))
    scored.sort(key=lambda item: -item[0])
    if not scored:
        return 0.0, None
    top_ratio, top_q = scored[0]
    second_ratio = scored[1][0] if len(scored) > 1 else 0.0
    if top_ratio >= FUZZY_MIN_RATIO and top_ratio - second_ratio >= FUZZY_UNIQUE_GAP:
        return top_ratio, top_q
    return top_ratio, None


def match_questions(sqlite_questions: list[dict], prod_questions: list[dict]) -> dict:
    """返回 {sqlite_q_id: {'prod_ids': [...], 'match': 'exact'|'fuzzy'|'low'|'none', 'ratio': float}}"""
    exact_index = build_exact_index(prod_questions)
    run_index = build_run_index(prod_questions)
    result: dict[int, dict] = {}
    for sq in sqlite_questions:
        ids = exact_index.get(sq['_n'], [])
        if ids:
            result[sq['id']] = {'prod_ids': ids, 'match': 'exact', 'ratio': 1.0}
            continue
        ratio, best = fuzzy_unique_best(sq['_n'], run_index)
        if best is not None:
            result[sq['id']] = {'prod_ids': [best['id']], 'match': 'fuzzy', 'ratio': ratio}
        elif ratio >= FUZZY_MIN_RATIO:
            result[sq['id']] = {'prod_ids': [], 'match': 'ambiguous', 'ratio': ratio}
        else:
            result[sq['id']] = {'prod_ids': [], 'match': 'low' if ratio > 0.0 else 'none', 'ratio': ratio}
    return result


# --------------------------------------------------------------------------- #
# Phase 1: 补答案
# --------------------------------------------------------------------------- #

SQL_EXP_INSERT_TEMPLATE = (
    "INSERT INTO {schema}.qbank_v2_question_explanation "
    "(question_id, content, explanation_type, is_default, status, created_by, updated_by, created_time, updated_time, deleted) "
    "VALUES (:qid, :content, :etype, :is_default, 'published', :cb, :cb, NOW(), NOW(), 0) "
    "ON CONFLICT (question_id, explanation_type, deleted) DO NOTHING RETURNING id"
)


def phase_enrich(conn, data: dict, args) -> None:
    created_by = args.created_by
    questions = data['questions']
    answers = data['answers']
    answers_by_q = defaultdict(list)
    for answer in answers:
        answers_by_q[answer['question_id']].append(answer)

    prod_rows = conn.execute(text(
        "SELECT id, stem FROM qbank_v2_question "
        "WHERE question_type = 'short_answer' AND deleted = 0"
    )).fetchall()
    prod_questions = [{'id': int(r[0]), 'code': None, '_n': norm_text(r[1])} for r in prod_rows]
    print(f'[ENRICH] sqlite_questions={len(questions)} prod_short_answer={len(prod_questions)}')

    sql_exp_insert = text(SQL_EXP_INSERT_TEMPLATE.format(schema=TARGET_SCHEMA))
    for sq in questions:
        sq['_n'] = norm_text('\n'.join(x for x in (sq['prompt'], sq['requirements']) if x))
    match_result = match_questions(questions, prod_questions)

    matched_count = 0
    unmatched_buckets: dict[str, int] = defaultdict(int)
    for sq in questions:
        info = match_result[sq['id']]
        if info['prod_ids']:
            matched_count += 1
        else:
            unmatched_buckets[info['match']] += 1

    # 现有解析（内容 + 类型，按题）用于去重与防撞名
    existing_explanations: dict[int, dict] = defaultdict(lambda: {'contents': set(), 'types': set()})
    if matched_count:
        exp_rows = conn.execute(text(
            "SELECT question_id, content, explanation_type FROM qbank_v2_question_explanation "
            "WHERE deleted = 0"
        )).fetchall()
        for qid, content, etype in exp_rows:
            existing_explanations[int(qid)]['contents'].add(norm_text(content))
            existing_explanations[int(qid)]['types'].add(str(etype))

    # 规划插入
    planned: list[dict] = []
    skipped_content = 0
    for sq in questions:
        info = match_result[sq['id']]
        if not info['prod_ids']:
            continue
        chosen = pick_best_answers(answers_by_q.get(sq['id'], []))
        if not chosen:
            continue
        for prod_qid in info['prod_ids']:
            state = existing_explanations[prod_qid]
            used_types: set[str] = set(state['types'])
            for answer in chosen:
                content_html = to_html_paragraphs(answer['answer_text'])
                content_norm = norm_text(content_html)
                if content_norm in state['contents']:
                    skipped_content += 1
                    continue
                etype = make_explanation_type(answer['_org'], used_types)
                planned.append({
                    'qid': prod_qid,
                    'content': content_html,
                    'etype': etype,
                    'is_default': False,
                    'cb': created_by,
                })
                state['contents'].add(content_norm)
                state['types'].add(etype)

    # 实际写入统计
    inserted = 0
    if not args.dry_run:
        for row in planned:
            inserted += len(conn.execute(sql_exp_insert, row).fetchall())

    print(f'[ENRICH] matched_questions={matched_count}')
    print(f'[ENRICH] planned_explanation_inserts={len(planned)}')
    print(f'[ENRICH] skipped_content_dup={skipped_content}')
    print(f'[ENRICH] unmatched_buckets={dict(unmatched_buckets)}')
    if args.dry_run:
        print('[ENRICH] DRY-RUN, no commit')
    else:
        print(f'[ENRICH] inserted={inserted}')

    # 未匹配清单
    if args.show_unmatched:
        print('\n[ENRICH] === 未匹配清单（需人工核对） ===')
        for sq in questions:
            info = match_result[sq['id']]
            if info['prod_ids']:
                continue
            print(f"  [{info['match']}] {sq['question_code']} | {sq['exam_type']} {sq['year']} | "
                  f"Q{sq['question_number']} | ratio={info['ratio']:.2f}")


# --------------------------------------------------------------------------- #
# Phase 2: 缺失卷导入
# --------------------------------------------------------------------------- #

def collection_for_paper(paper: dict) -> str:
    exam_type = str(paper.get('exam_type') or '')
    if '选调' in exam_type:
        return XUANDIAO_COLLECTION
    if exam_type in EXAM_TYPE_COLLECTION:
        return EXAM_TYPE_COLLECTION[exam_type]
    province = str(paper.get('source_province') or paper.get('region') or '')
    if province in PROVINCE_COLLECTION:
        return PROVINCE_COLLECTION[province]
    return 'SET_GWY_SL_PROV_OTHER'


def phase_papers(conn, data: dict, args) -> None:
    created_by = args.created_by
    papers = data['papers']
    materials = data['materials']
    questions = data['questions']
    answers = data['answers']
    sql_exp_insert = text(SQL_EXP_INSERT_TEMPLATE.format(schema=TARGET_SCHEMA))

    answers_by_q = defaultdict(list)
    for answer in answers:
        answers_by_q[answer['question_id']].append(answer)

    questions_by_paper = defaultdict(list)
    for q in questions:
        questions_by_paper[q['paper_id']].append(q)
    for qs in questions_by_paper.values():
        qs.sort(key=lambda q: q['question_number'] or 0)

    materials_by_paper = defaultdict(list)
    for m in materials:
        materials_by_paper[m['paper_id']].append(m)
    for ms in materials_by_paper.values():
        ms.sort(key=lambda m: m['material_number'] or 0)

    # 现有 paper-kind bank
    bank_rows = conn.execute(text(
        "SELECT DISTINCT b.code AS bank_code, r.name AS name "
        "FROM qbank_v2_bank b JOIN qbank_v2_bank_revision r ON r.bank_id = b.id "
        "WHERE b.deleted = 0 AND r.bank_kind = 'paper'"
    )).fetchall()
    bank_names = {norm_text(r[1]): r[0] for r in bank_rows}
    print(f'[PAPERS] v2_paper_banks={len(bank_names)}')

    missing: list[dict] = []
    skipped_variant: list[dict] = []
    for paper in papers:
        n = norm_text(paper['paper_name'])
        if n in bank_names:
            continue
        if paper['paper_name'] in SKIP_NAME_VARIANTS:
            skipped_variant.append(paper)
            continue
        missing.append(paper)
    missing.sort(key=lambda p: (p.get('year') or 0, p.get('paper_name') or ''))

    print(f'[PAPERS] missing_papers={len(missing)} skipped_name_variants={len(skipped_variant)}')

    # 新建选调申论合集
    collection_id = ensure_collection(conn, XUANDIAO_COLLECTION, '选调生申论', created_by)
    collection_cache = {XUANDIAO_COLLECTION: collection_id}

    stats = {
        'banks': 0, 'materials': 0, 'material_revisions': 0,
        'questions': 0, 'answers': 0, 'explanations': 0, 'items': 0, 'mounts': 0,
    }
    for paper in missing:
        paper_id = paper['id']
        bank_code = f'PAPER_GK_{paper_id}'
        exists = conn.execute(text(
            'SELECT 1 FROM qbank_v2_bank WHERE code = :code AND deleted = 0'
        ), {'code': bank_code}).fetchone()
        if exists:
            print(f'[PAPERS] skip existing bank code={bank_code} name={paper["paper_name"]}')
            continue

        bank_id = conn.execute(text(
            "INSERT INTO qbank_v2_bank (code, owner_id, current_revision_id, visibility, status, "
            "created_by, updated_by, created_time, updated_time, deleted) "
            "VALUES (:code, NULL, NULL, 'public', 'active', :cb, :cb, NOW(), NOW(), 0) RETURNING id"
        ), {'code': bank_code, 'cb': created_by}).fetchone()[0]
        stats['banks'] += 1

        settings = {
            'exam_type': paper.get('exam_type'),
            'year': paper.get('year'),
            'region': paper.get('region'),
            'source_province': paper.get('source_province'),
            'paper_category': paper.get('paper_category'),
            'target_group': paper.get('target_group'),
            'zhejiang_relevance': paper.get('zhejiang_relevance'),
            'source': 'gongkao_seed',
        }
        import json as _json
        revision_id = conn.execute(text(
            "INSERT INTO qbank_v2_bank_revision "
            "(bank_id, revision_no, name, bank_kind, description, settings, question_count, total_score, "
            "content_hash, status, published_by, published_time, created_by, updated_by, created_time, updated_time, deleted) "
            "VALUES (:bid, 1, :name, 'paper', NULL, CAST(:settings AS jsonb), 0, 0, NULL, "
            "'published', :cb, NOW(), :cb, :cb, NOW(), NOW(), 0) RETURNING id"
        ), {'bid': bank_id, 'name': paper['paper_name'], 'settings': _json.dumps(settings, ensure_ascii=False), 'cb': created_by}).fetchone()[0]
        conn.execute(text(
            "UPDATE qbank_v2_bank SET current_revision_id = :rid WHERE id = :bid"
        ), {'rid': revision_id, 'bid': bank_id})

        # 材料
        material_ids: list[int] = []
        for material in materials_by_paper.get(paper_id, []):
            number = int(material.get('material_number') or 0)
            mcode = f'MAT_GK_{paper_id}_{number}'
            mid = conn.execute(text(
                "INSERT INTO qbank_v2_material (code, current_revision_id, status, "
                "created_by, updated_by, created_time, updated_time, deleted) "
                "VALUES (:code, NULL, 'active', :cb, :cb, NOW(), NOW(), 0) RETURNING id"
            ), {'code': mcode, 'cb': created_by}).fetchone()[0]
            stats['materials'] += 1
            mrev = conn.execute(text(
                "INSERT INTO qbank_v2_material_revision "
                "(material_id, revision_no, title, content, content_format, structured_data, source_name, "
                "source_url, content_hash, status, published_by, published_time, created_by, updated_by, "
                "created_time, updated_time, deleted) "
                "VALUES (:mid, 1, :title, :content, 'html', '{}'::jsonb, 'gongkao_seed', NULL, NULL, "
                "'published', :cb, NOW(), :cb, :cb, NOW(), NOW(), 0) RETURNING id"
            ), {'mid': mid, 'title': material.get('title') or f'材料{number}', 'content': to_html_paragraphs(material.get('content')), 'cb': created_by}).fetchone()[0]
            stats['material_revisions'] += 1
            conn.execute(text(
                "UPDATE qbank_v2_material SET current_revision_id = :rid WHERE id = :mid"
            ), {'rid': mrev, 'mid': mid})
            material_ids.append((mid, mrev))

        # 题目
        for sort_order, q in enumerate(questions_by_paper.get(paper_id, [])):
            qcode = f'gk_{q["question_code"]}'
            score = parse_score(q['prompt'])
            stem = build_stem(q['prompt'], q['requirements'])
            question_id = conn.execute(text(
                "INSERT INTO qbank_v2_question "
                "(code, owner_id, visibility, origin_type, status, stem, content_format, question_type, "
                "option_data, default_score, difficulty, content_hash, created_by, updated_by, created_time, updated_time, deleted) "
                "VALUES (:code, NULL, 'public', 'imported', 'active', :stem, 'html', 'short_answer', "
                "'[]'::jsonb, :score, NULL, NULL, :cb, :cb, NOW(), NOW(), 0) RETURNING id"
            ), {'code': qcode, 'stem': stem, 'score': float(score), 'cb': created_by}).fetchone()[0]
            stats['questions'] += 1

            chosen = pick_best_answers(answers_by_q.get(q['id'], []))
            if chosen:
                primary = chosen[0]
                conn.execute(text(
                    "INSERT INTO qbank_v2_question_answer "
                    "(question_id, answer_data, grading_method, grading_config, created_by, updated_by, "
                    "created_time, updated_time, deleted) "
                    "VALUES (:qid, CAST(:ad AS jsonb), 'rubric', '{}'::jsonb, :cb, :cb, NOW(), NOW(), 0) "
                    "ON CONFLICT (question_id) DO NOTHING"
                ), {'qid': question_id, 'ad': _json.dumps({'source': 'gongkao_seed', 'organ': primary['_org'], 'source_answer_id': primary['id']}, ensure_ascii=False), 'cb': created_by})
                stats['answers'] += 1

                used_types: set[str] = set()
                for idx, answer in enumerate(chosen):
                    etype = make_explanation_type(answer['_org'], used_types)
                    conn.execute(sql_exp_insert, {
                        'qid': question_id,
                        'content': to_html_paragraphs(answer['answer_text']),
                        'etype': etype,
                        'is_default': idx == 0,
                        'cb': created_by,
                    })
                    stats['explanations'] += 1

            for sort_no, (mid, mrev) in enumerate(material_ids, start=1):
                conn.execute(text(
                    "INSERT INTO qbank_v2_question_material "
                    "(question_id, material_id, material_revision_id, role, sort_order, display_config, "
                    "created_by, updated_by, created_time, updated_time, deleted) "
                    "VALUES (:qid, :mid, :mrev, 'passage', :sort, '{}'::jsonb, :cb, :cb, NOW(), NOW(), 0) "
                    "ON CONFLICT (question_id, material_id, role, deleted) DO NOTHING"
                ), {'qid': question_id, 'mid': mid, 'mrev': mrev, 'sort': sort_no, 'cb': created_by})

            item_key = str(q.get('question_number') or sort_order + 1)
            conn.execute(text(
                "INSERT INTO qbank_v2_bank_item "
                "(bank_revision_id, item_key, question_id, section_id, exam_year, score, sort_order, "
                "is_required, is_active, settings, created_by, updated_by, created_time, updated_time, deleted) "
                "VALUES (:rid, :ik, :qid, NULL, :year, :score, :sort, true, true, '{}'::jsonb, "
                ":cb, :cb, NOW(), NOW(), 0) ON CONFLICT (bank_revision_id, item_key, deleted) DO NOTHING"
            ), {'rid': revision_id, 'ik': item_key, 'qid': question_id, 'year': paper.get('year'), 'score': float(score), 'sort': sort_order, 'cb': created_by})
            stats['items'] += 1

        conn.execute(text(
            "UPDATE qbank_v2_bank_revision SET question_count = :cnt WHERE id = :rid"
        ), {'cnt': len(questions_by_paper.get(paper_id, [])), 'rid': revision_id})

        # 挂合集
        col_code = collection_for_paper(paper)
        if col_code not in collection_cache:
            collection_cache[col_code] = ensure_collection(conn, col_code, col_code, created_by)
        conn.execute(text(
            "INSERT INTO qbank_v2_collection_bank "
            "(collection_id, bank_id, bank_revision_id, follow_latest, display_name, sort_order, is_active, "
            "created_by, updated_by, created_time, updated_time, deleted) "
            "VALUES (:cid, :bid, NULL, true, :name, 0, true, :cb, :cb, NOW(), NOW(), 0) "
            "ON CONFLICT (collection_id, bank_id, deleted) DO NOTHING"
        ), {'cid': collection_cache[col_code], 'bid': bank_id, 'name': paper['paper_name'], 'cb': created_by})
        stats['mounts'] += 1

        print(f'[PAPERS] bank={bank_id} code={bank_code} name={paper["paper_name"]} '
              f'q={len(questions_by_paper.get(paper_id, []))} mat={len(material_ids)}')

    print(f'[PAPERS] stats={stats}')
    if skipped_variant:
        print('[PAPERS] skipped_name_variants:')
        for paper in skipped_variant:
            print(f"  {paper['paper_name']} -> {SKIP_NAME_VARIANTS[paper['paper_name']]}")
    if not args.dry_run:
        print('[PAPERS] committed')


def phase_materials(conn, data: dict, args) -> None:
    """为缺少材料的申论题目按卷补挂材料（从 sqlite paper_materials）。"""
    import json as _json

    created_by = args.created_by
    questions = data['questions']
    materials = data['materials']

    materials_by_paper = defaultdict(list)
    for m in materials:
        materials_by_paper[m['paper_id']].append(m)
    for ms in materials_by_paper.values():
        ms.sort(key=lambda m: m['material_number'] or 0)

    target_rows = conn.execute(text(
        "SELECT q.id, q.stem FROM qbank_v2_question q "
        "WHERE q.question_type = 'short_answer' AND q.deleted = 0 "
        "AND NOT EXISTS (SELECT 1 FROM qbank_v2_question_material qm "
        "                WHERE qm.question_id = q.id AND qm.deleted = 0)"
    )).fetchall()
    target = [{'id': int(r[0]), '_n': norm_text(r[1])} for r in target_rows]
    print(f'[MATERIALS] target_questions_without_materials={len(target)}')
    if not target:
        print('[MATERIALS] nothing to do')
        return

    for sq in questions:
        sq['_n'] = norm_text('\n'.join(x for x in (sq['prompt'], sq['requirements']) if x))
    match_result = match_questions(questions, target)

    target_to_sqlite: dict[int, list[dict]] = defaultdict(list)
    for sq in questions:
        info = match_result[sq['id']]
        for tid in info['prod_ids']:
            target_to_sqlite[tid].append(sq)
    print(f'[MATERIALS] matched_target={len(target_to_sqlite)}')

    existing_mat: dict[str, int] = {}
    for mid, code in conn.execute(text(
        'SELECT id, code FROM qbank_v2_material WHERE deleted = 0'
    )).fetchall():
        existing_mat[str(code)] = int(mid)
    existing_mrev: dict[int, int] = {}
    for mrev_id, mid in conn.execute(text(
        'SELECT id, material_id FROM qbank_v2_material_revision WHERE deleted = 0'
    )).fetchall():
        existing_mrev[int(mid)] = int(mrev_id)

    stats = {'questions': 0, 'materials_created': 0, 'links': 0, 'unmatched': 0}
    for tid, sqlite_qs in target_to_sqlite.items():
        sq = sqlite_qs[0]
        ms = materials_by_paper.get(sq['paper_id'], [])
        if not ms:
            continue
        material_ids: list[tuple[int, int]] = []
        for material in ms:
            number = int(material.get('material_number') or 0)
            mcode = f'MAT_GK_{sq["paper_id"]}_{number}'
            mid = existing_mat.get(mcode)
            if mid is None:
                mid = conn.execute(text(
                    "INSERT INTO qbank_v2_material (code, current_revision_id, status, "
                    "created_by, updated_by, created_time, updated_time, deleted) "
                    "VALUES (:code, NULL, 'active', :cb, :cb, NOW(), NOW(), 0) RETURNING id"
                ), {'code': mcode, 'cb': created_by}).fetchone()[0]
                existing_mat[mcode] = int(mid)
                mrev = conn.execute(text(
                    "INSERT INTO qbank_v2_material_revision "
                    "(material_id, revision_no, title, content, content_format, structured_data, source_name, "
                    "source_url, content_hash, status, published_by, published_time, created_by, updated_by, "
                    "created_time, updated_time, deleted) "
                    "VALUES (:mid, 1, :title, :content, 'html', '{}'::jsonb, 'gongkao_seed', NULL, NULL, "
                    "'published', :cb, NOW(), :cb, :cb, NOW(), NOW(), 0) RETURNING id"
                ), {'mid': mid, 'title': material.get('title') or f'材料{number}', 'content': to_html_paragraphs(material.get('content')), 'cb': created_by}).fetchone()[0]
                conn.execute(text(
                    "UPDATE qbank_v2_material SET current_revision_id = :rid WHERE id = :mid"
                ), {'rid': mrev, 'mid': mid})
                existing_mrev[int(mid)] = int(mrev)
                stats['materials_created'] += 1
            else:
                mid = int(mid)
                mrev = existing_mrev.get(mid)
            if mrev is None:
                stats['unmatched'] += 1
                continue
            material_ids.append((mid, int(mrev)))

        for sort_no, (mid, mrev) in enumerate(material_ids, start=1):
            conn.execute(text(
                "INSERT INTO qbank_v2_question_material "
                "(question_id, material_id, material_revision_id, role, sort_order, display_config, "
                "created_by, updated_by, created_time, updated_time, deleted) "
                "VALUES (:qid, :mid, :mrev, 'passage', :sort, '{}'::jsonb, :cb, :cb, NOW(), NOW(), 0) "
                "ON CONFLICT (question_id, material_id, role, deleted) DO NOTHING"
            ), {'qid': tid, 'mid': mid, 'mrev': mrev, 'sort': sort_no, 'cb': created_by})
            stats['links'] += 1
        stats['questions'] += 1

    print(f'[MATERIALS] stats={stats}')
    if args.dry_run:
        print('[MATERIALS] DRY-RUN, no commit')


def ensure_collection(conn, code: str, name: str, created_by: int) -> int:
    row = conn.execute(text(
        'SELECT id FROM qbank_v2_collection WHERE code = :code AND deleted = 0'
    ), {'code': code}).fetchone()
    if row:
        return int(row[0])
    new_id = conn.execute(text(
        "INSERT INTO qbank_v2_collection "
        "(code, name, parent_id, owner_id, description, visibility, status, sort_order, "
        "created_by, updated_by, created_time, updated_time, deleted) "
        "VALUES (:code, :name, NULL, NULL, NULL, 'public', 'active', 0, :cb, :cb, NOW(), NOW(), 0) "
        "ON CONFLICT (code, deleted) DO NOTHING RETURNING id"
    ), {'code': code, 'name': name, 'cb': created_by}).fetchone()
    return int(new_id[0]) if new_id else int(conn.execute(text(
        'SELECT id FROM qbank_v2_collection WHERE code = :code AND deleted = 0'
    ), {'code': code}).fetchone()[0])


def fix_sequences(conn, schema: str) -> None:
    tables = [
        'qbank_v2_bank', 'qbank_v2_bank_revision', 'qbank_v2_bank_item', 'qbank_v2_bank_section',
        'qbank_v2_question', 'qbank_v2_question_answer', 'qbank_v2_question_explanation',
        'qbank_v2_question_material', 'qbank_v2_material', 'qbank_v2_material_revision',
        'qbank_v2_collection', 'qbank_v2_collection_bank',
    ]
    for table in tables:
        conn.execute(text(
            f"SELECT setval('{schema}.{table}_id_seq', "
            f"GREATEST((SELECT COALESCE(MAX(id), 1) FROM {schema}.{table}), 1))"
        ))


def main() -> None:
    global TARGET_SCHEMA

    parser = argparse.ArgumentParser(description='导入公考申论 seed 数据到 question_bank_v2')
    parser.add_argument('--sqlite', default=DEFAULT_SQLITE, help='sqlite 文件路径')
    parser.add_argument('--env', default='prod', choices=['dev', 'prod'], help='连接 prod(.env.prod) 或 dev(.env)')
    parser.add_argument('--db-url', default=None, help='直接指定数据库 DSN（覆盖 env）')
    parser.add_argument('--schema', default=None, help='目标 schema；默认 prod=fba，dev=public')
    parser.add_argument('--phase', default='all', choices=['enrich', 'papers', 'materials', 'all'], help='执行阶段')
    parser.add_argument('--dry-run', action='store_true', help='演练，不提交（默认）')
    parser.add_argument('--commit', action='store_true', help='真正提交写入')
    parser.add_argument('--created-by', type=int, default=DEFAULT_CREATED_BY, help='created_by 用户 ID')
    parser.add_argument('--show-unmatched', action='store_true', help='输出未匹配题清单')
    args = parser.parse_args()

    target_schema = args.schema or ('fba' if args.env == 'prod' else 'public')
    if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', target_schema):
        raise SystemExit(f'非法 schema 名称: {target_schema}')
    TARGET_SCHEMA = target_schema

    if not os.path.exists(args.sqlite):
        raise SystemExit(f'sqlite 文件不存在: {args.sqlite}')
    if not args.commit:
        args.dry_run = True
    else:
        args.dry_run = False

    data = load_sqlite(args.sqlite)
    engine = get_engine(env=args.env, db_url=args.db_url)
    print(
        f'[MAIN] sqlite={args.sqlite} env={args.env} schema={TARGET_SCHEMA} '
        f'phase={args.phase} dry_run={args.dry_run}'
    )

    with engine.connect() as conn:
        conn.execute(text('SELECT set_config(:k, :s, false)'), {'k': 'search_path', 's': TARGET_SCHEMA})
        try:
            if args.phase in ('enrich', 'all'):
                phase_enrich(conn, data, args)
            if args.phase in ('papers', 'all'):
                phase_papers(conn, data, args)
            if args.phase in ('materials', 'all'):
                phase_materials(conn, data, args)
            if args.commit:
                fix_sequences(conn, TARGET_SCHEMA)
                conn.commit()
                print('[MAIN] COMMITTED')
            else:
                conn.rollback()
                print('[MAIN] DRY-RUN finished, rolled back')
        except Exception as exc:  # noqa: BLE001
            conn.rollback()
            print(f'[MAIN] ERROR rolled back: {exc!r}')
            raise
    engine.dispose()


if __name__ == '__main__':
    main()
