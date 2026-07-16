#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import asyncio
import csv
import re
import sys

from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.question_bank.model import QuestionBank, QuestionPlacement
from backend.database.db import async_db_session

CODE_MAX_LENGTH = 32
NORMAL_CODE_RE = re.compile(r'^[A-Z][A-Z0-9_]{2,31}$')
CHINESE_RE = re.compile(r'[\u4e00-\u9fff]')
YEAR_RE = re.compile(r'(20\d{2})')

DOMAIN_KEYWORDS = [
    ('资料分析', 'ZLFX'),
    ('言语理解', 'YYLJ'),
    ('言语', 'YYLJ'),
    ('判断推理', 'JDTL'),
    ('判断', 'JDTL'),
    ('数量关系', 'SLGX'),
    ('数量', 'SLGX'),
    ('常识判断', 'CSPD'),
    ('常识', 'CSPD'),
    ('申论', 'SHENLUN'),
    ('行测', 'XINGCE'),
    ('公安', 'GONGAN'),
    ('公基', 'GONGJI'),
    ('国考', 'GUOKAO'),
    ('省考', 'SHENGKAO'),
]

REGION_KEYWORDS = [
    ('北京', 'BJ'),
    ('天津', 'TJ'),
    ('河北', 'HEB'),
    ('山西', 'SX'),
    ('内蒙古', 'NMG'),
    ('辽宁', 'LN'),
    ('吉林', 'JL'),
    ('黑龙江', 'HLJ'),
    ('上海', 'SH'),
    ('江苏', 'JS'),
    ('浙江', 'ZJ'),
    ('安徽', 'AH'),
    ('福建', 'FJ'),
    ('江西', 'JX'),
    ('山东', 'SD'),
    ('河南', 'HEN'),
    ('湖北', 'HUB'),
    ('湖南', 'HUN'),
    ('广东', 'GD'),
    ('广西', 'GX'),
    ('海南', 'HI'),
    ('重庆', 'CQ'),
    ('四川', 'SC'),
    ('贵州', 'GZ'),
    ('云南', 'YN'),
    ('西藏', 'XZ'),
    ('陕西', 'SNX'),
    ('甘肃', 'GS'),
    ('青海', 'QH'),
    ('宁夏', 'NX'),
    ('新疆', 'XJ'),
]

TEMP_MARKERS = {'DEMO', 'TEST', 'TEMP', 'TMP', 'UNKNOWN', 'UNTITLED', 'NULL', 'NONE'}


@dataclass
class BankCodeAuditRow:
    bank_id: int
    code: str
    name: str
    bank_type: int
    parent_id: int | None
    year: int | None
    status: int
    question_count: int
    issues: list[str]
    suggested_code: str


def parse_args() -> argparse.Namespace:
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description='审计 study_question_bank.code 规范性')
    parser.add_argument('--all', action='store_true', help='输出全部题库，默认只输出存在问题的题库')
    parser.add_argument('--csv', default='', help='输出 CSV 文件路径')
    parser.add_argument('--limit', default=0, type=int, help='最多输出多少行，0 表示不限制')
    parser.add_argument('--schema', default='fba', help='生成 SQL 草案使用的 schema')
    parser.add_argument('--emit-update-sql', action='store_true', help='打印安全 UPDATE 草案，不执行')
    return parser.parse_args()


def detect_code_issues(code: str) -> list[str]:
    """
    检测题库编码问题

    :param code: 题库编码
    :return:
    """
    value = str(code or '').strip()
    issues: list[str] = []
    if not value:
        return ['blank']
    if len(value) > CODE_MAX_LENGTH:
        issues.append('too_long')
    if value != value.upper():
        issues.append('not_uppercase')
    if CHINESE_RE.search(value):
        issues.append('has_chinese')
    if re.search(r'[^A-Za-z0-9_]', value):
        issues.append('invalid_chars')
    if not re.match(r'^[A-Za-z]', value):
        issues.append('bad_prefix')
    if re.fullmatch(r'(BANK_)?\d+', value.upper()):
        issues.append('weak_semantic')

    upper_parts = set(re.split(r'[_\W]+', value.upper()))
    if upper_parts & TEMP_MARKERS:
        issues.append('temporary_like')
    if not issues and not NORMAL_CODE_RE.fullmatch(value):
        issues.append('non_standard')
    return issues


def get_bank_prefix(bank_type: int) -> str:
    """
    获取题库类型前缀

    :param bank_type: 题库类型
    :return:
    """
    if bank_type == 2:
        return 'PAPER'
    if bank_type == 3:
        return 'SET'
    return 'BANK'


def find_keyword_tokens(value: str, keyword_pairs: list[tuple[str, str]], *, max_count: int) -> list[str]:
    """
    从文本中提取关键词 token

    :param value: 原始文本
    :param keyword_pairs: 关键词映射
    :param max_count: 最大数量
    :return:
    """
    tokens: list[str] = []
    for keyword, token in keyword_pairs:
        if keyword not in value:
            continue
        if token in tokens:
            continue
        tokens.append(token)
        if len(tokens) >= max_count:
            break
    return tokens


def find_year(bank_year: int | None, name: str, code: str) -> str | None:
    """
    提取年份

    :param bank_year: 题库年份字段
    :param name: 题库名称
    :param code: 题库编码
    :return:
    """
    if bank_year and 2000 <= bank_year <= 2099:
        return str(bank_year)

    match = YEAR_RE.search(f'{name} {code}')
    if not match:
        return None
    return match.group(1)


def sanitize_token(value: str) -> str:
    """
    清理编码片段

    :param value: 原始片段
    :return:
    """
    token = re.sub(r'[^A-Z0-9]+', '_', value.upper()).strip('_')
    return token or 'X'


def compact_code(segments: list[str], suffix: str) -> str:
    """
    压缩编码到 32 位以内

    :param segments: 编码片段
    :param suffix: 唯一后缀
    :return:
    """
    safe_segments = [sanitize_token(item) for item in segments if item]
    if not safe_segments:
        safe_segments = ['BANK']

    safe_suffix = sanitize_token(suffix)
    result_segments: list[str] = []
    for segment in safe_segments:
        candidate_segments = [*result_segments, segment, safe_suffix]
        candidate = '_'.join(candidate_segments)
        if len(candidate) <= CODE_MAX_LENGTH:
            result_segments.append(segment)
            continue
        break

    if result_segments:
        result = '_'.join([*result_segments, safe_suffix])
    else:
        reserved = len(safe_suffix) + 1
        result = f'{safe_segments[0][: CODE_MAX_LENGTH - reserved]}_{safe_suffix}'

    return result[:CODE_MAX_LENGTH]


def build_suggested_code(row: BankCodeAuditRow, occupied_codes: set[str], proposed_codes: set[str]) -> str:
    """
    生成建议编码

    :param row: 审计行
    :param occupied_codes: 当前已占用编码
    :param proposed_codes: 本轮已建议编码
    :return:
    """
    if not row.issues:
        return row.code

    search_text = f'{row.name} {row.code}'
    segments = [get_bank_prefix(row.bank_type)]
    segments.extend(find_keyword_tokens(search_text, DOMAIN_KEYWORDS, max_count=2))
    segments.extend(find_keyword_tokens(search_text, REGION_KEYWORDS, max_count=1))

    year = find_year(row.year, row.name, row.code)
    if year:
        segments.append(year)

    candidate = compact_code(segments, str(row.bank_id))
    while candidate in occupied_codes or candidate in proposed_codes:
        candidate = compact_code([*segments, 'B'], str(row.bank_id))
        if candidate not in occupied_codes and candidate not in proposed_codes:
            break
        candidate = f'{get_bank_prefix(row.bank_type)}_{row.bank_id}'[:CODE_MAX_LENGTH]
        break

    proposed_codes.add(candidate)
    return candidate


async def fetch_bank_rows(db: AsyncSession) -> list[BankCodeAuditRow]:
    """
    查询题库编码审计数据

    :param db: 数据库会话
    :return:
    """
    stmt = (
        select(
            QuestionBank.id,
            QuestionBank.code,
            QuestionBank.name,
            QuestionBank.bank_type,
            QuestionBank.parent_id,
            QuestionBank.year,
            QuestionBank.status,
            func.count(QuestionPlacement.id).label('question_count'),
        )
        .outerjoin(QuestionPlacement, QuestionPlacement.bank_id == QuestionBank.id)
        .group_by(
            QuestionBank.id,
            QuestionBank.code,
            QuestionBank.name,
            QuestionBank.bank_type,
            QuestionBank.parent_id,
            QuestionBank.year,
            QuestionBank.status,
        )
        .order_by(QuestionBank.id.asc())
    )
    rows = (await db.execute(stmt)).all()
    result: list[BankCodeAuditRow] = []
    for row in rows:
        code = str(row.code or '').strip()
        result.append(
            BankCodeAuditRow(
                bank_id=int(row.id),
                bank_type=int(row.bank_type or 0),
                code=code,
                issues=detect_code_issues(code),
                name=str(row.name or ''),
                parent_id=int(row.parent_id) if row.parent_id is not None else None,
                question_count=int(row.question_count or 0),
                status=int(row.status or 0),
                suggested_code='',
                year=int(row.year) if row.year is not None else None,
            )
        )
    return result


def fill_suggestions(rows: list[BankCodeAuditRow]) -> None:
    """
    填充建议编码

    :param rows: 审计行
    :return:
    """
    occupied_codes = {row.code for row in rows if row.code}
    proposed_codes: set[str] = set()
    for row in rows:
        occupied_without_current = occupied_codes - {row.code}
        row.suggested_code = build_suggested_code(row, occupied_without_current, proposed_codes)


def filter_rows(rows: list[BankCodeAuditRow], *, include_all: bool, limit: int) -> list[BankCodeAuditRow]:
    """
    过滤输出行

    :param rows: 审计行
    :param include_all: 是否包含全部
    :param limit: 输出上限
    :return:
    """
    filtered = rows if include_all else [row for row in rows if row.issues]
    if limit <= 0:
        return filtered
    return filtered[:limit]


def write_csv(rows: list[BankCodeAuditRow], csv_path: str) -> None:
    """
    写入 CSV

    :param rows: 输出行
    :param csv_path: CSV 路径
    :return:
    """
    output_path = Path(csv_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open('w', encoding='utf-8-sig', newline='') as file:
        writer = csv.DictWriter(
            file,
            fieldnames=[
                'id',
                'code',
                'suggested_code',
                'issues',
                'name',
                'bank_type',
                'parent_id',
                'year',
                'status',
                'question_count',
            ],
        )
        writer.writeheader()
        for row in rows:
            writer.writerow(row_to_dict(row))


def row_to_dict(row: BankCodeAuditRow) -> dict[str, str | int | None]:
    """
    转换为字典

    :param row: 审计行
    :return:
    """
    return {
        'bank_type': row.bank_type,
        'code': row.code,
        'id': row.bank_id,
        'issues': ','.join(row.issues),
        'name': row.name,
        'parent_id': row.parent_id,
        'question_count': row.question_count,
        'status': row.status,
        'suggested_code': row.suggested_code,
        'year': row.year,
    }


def print_summary(rows: list[BankCodeAuditRow], output_rows: list[BankCodeAuditRow]) -> None:
    """
    打印审计汇总

    :param rows: 全量行
    :param output_rows: 输出行
    :return:
    """
    issue_counter: Counter[str] = Counter()
    for row in rows:
        issue_counter.update(row.issues)

    print(f'[SUMMARY] total={len(rows)} problem={sum(1 for row in rows if row.issues)} output={len(output_rows)}')
    for issue, count in issue_counter.most_common():
        print(f'[ISSUE] {issue}={count}')


def print_table(rows: list[BankCodeAuditRow]) -> None:
    """
    打印表格

    :param rows: 输出行
    :return:
    """
    for row in rows:
        print(
            '[BANK]'
            f' id={row.bank_id}'
            f' type={row.bank_type}'
            f' status={row.status}'
            f' q={row.question_count}'
            f' code={row.code}'
            f' suggest={row.suggested_code}'
            f' issues={",".join(row.issues) or "-"}'
            f' name={row.name}'
        )


def quote_sql(value: str) -> str:
    """
    SQL 字符串转义

    :param value: 原始字符串
    :return:
    """
    return value.replace("'", "''")


def print_update_sql(rows: list[BankCodeAuditRow], *, schema: str) -> None:
    """
    打印 UPDATE 草案

    :param rows: 输出行
    :param schema: schema 名称
    :return:
    """
    safe_schema = re.sub(r'[^a-zA-Z0-9_]', '', schema) or 'fba'
    print('-- Review carefully before running in production.')
    print('BEGIN;')
    for row in rows:
        if not row.issues:
            continue
        print(f'-- id={row.bank_id} name={quote_sql(row.name)} issues={",".join(row.issues)}')
        print(
            f"UPDATE {safe_schema}.study_question_bank "
            f"SET code = '{quote_sql(row.suggested_code)}' "
            f"WHERE id = {row.bank_id} AND code = '{quote_sql(row.code)}';"
        )
    print('ROLLBACK;')


async def run() -> None:
    """执行审计"""
    args = parse_args()
    async with async_db_session() as db:
        rows = await fetch_bank_rows(db)
        await db.rollback()

    fill_suggestions(rows)
    output_rows = filter_rows(rows, include_all=bool(args.all), limit=int(args.limit or 0))
    print_summary(rows, output_rows)
    if args.csv:
        write_csv(output_rows, str(args.csv))
        print(f'[CSV] {args.csv}')
    else:
        print_table(output_rows)

    if args.emit_update_sql:
        print_update_sql(output_rows, schema=str(args.schema or 'fba'))


if __name__ == '__main__':
    asyncio.run(run())
