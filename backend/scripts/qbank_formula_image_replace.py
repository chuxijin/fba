#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import asyncio
import builtins
import csv
import html
import os
import re
import sys

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from urllib.parse import parse_qs, unquote_plus, urlparse

from sqlalchemy import func, select, text

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

DEFAULT_ENV_FILE = PROJECT_ROOT / 'backend' / '.env.prod'


def resolve_script_env_file() -> Path:
    """Resolve script env file before backend settings import."""
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument('--env-file', default=str(DEFAULT_ENV_FILE))
    args, _unknown = parser.parse_known_args()
    env_file = Path(str(args.env_file)).expanduser()
    if env_file.is_absolute():
        return env_file
    return PROJECT_ROOT / env_file


def normalize_env_value(raw_value: str) -> str:
    """
    Normalize dotenv value.

    :param raw_value: raw dotenv value
    :return:
    """
    value = raw_value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        return value[1:-1]
    if ' #' in value:
        value = value.split(' #', 1)[0].strip()
    return value


def load_script_env_file(env_file: Path) -> Path:
    """
    Load dotenv file into process environment before settings import.

    :param env_file: dotenv path
    :return:
    """
    if not env_file.exists():
        raise FileNotFoundError(f'env file not found: {env_file}')

    for line in env_file.read_text(encoding='utf-8').splitlines():
        text_line = line.strip()
        if not text_line or text_line.startswith('#'):
            continue
        if '=' not in text_line:
            continue

        key, raw_value = text_line.split('=', 1)
        env_key = key.strip()
        if not env_key:
            continue
        os.environ[env_key] = normalize_env_value(raw_value)

    os.environ['FBA_SCRIPT_ENV_FILE'] = str(env_file)
    return env_file


SCRIPT_ENV_FILE = load_script_env_file(resolve_script_env_file())

from backend.app.question_bank.model import (  # noqa: E402
    Question,
    QuestionAnalysis,
    QuestionBank,
    QuestionMaterial,
    QuestionPlacement,
)
from backend.core.conf import settings  # noqa: E402
from backend.database.db import async_db_session  # noqa: E402

DEFAULT_OUTPUT_DIR = PROJECT_ROOT / 'backend' / 'scripts' / 'reports'
IMG_TAG_RE = re.compile(r'<img\b(?:[^>"\']+|"[^"]*"|\'[^\']*\')*>', re.IGNORECASE)
ATTR_RE = re.compile(r'(?P<name>[a-zA-Z_:][-a-zA-Z0-9_:.]*)\s*=\s*(?P<quote>"|\')(?P<value>.*?)(?P=quote)')


def print(*args, **kwargs) -> None:
    """Print with flush enabled for long-running scripts."""
    kwargs.setdefault('flush', True)
    builtins.print(*args, **kwargs)


@dataclass
class BankTarget:
    """Audit bank target."""

    bank_id: int
    bank_code: str
    bank_name: str
    question_count: int


@dataclass
class RuntimeOptions:
    """Script runtime options."""

    keyword: str
    selection: str
    dry_run: bool
    max_questions: int
    max_replacements: int
    batch_size: int
    output_dir: Path
    verify_only: bool
    verify_sample_limit: int


@dataclass
class ReplaceSample:
    """Formula image replacement sample."""

    bank_code: str
    record_type: str
    record_id: int
    question_id: int | None
    field_name: str
    formula: str
    src: str
    before: str
    after: str


@dataclass
class ReplaceStats:
    """Replacement stats."""

    scanned_records: int = 0
    changed_records: int = 0
    replaced_images: int = 0
    formula_attr: int = 0
    formula_url: int = 0
    empty_formula_url: int = 0
    samples: list[ReplaceSample] = field(default_factory=list)

    def add(self, other: ReplaceStats) -> None:
        """
        Merge another stats into current stats.

        :param other: source stats
        :return:
        """
        self.scanned_records += other.scanned_records
        self.changed_records += other.changed_records
        self.replaced_images += other.replaced_images
        self.formula_attr += other.formula_attr
        self.formula_url += other.formula_url
        self.empty_formula_url += other.empty_formula_url
        self.samples.extend(other.samples)


def parse_runtime_options() -> RuntimeOptions:
    """Parse script runtime options."""
    parser = argparse.ArgumentParser(description='替换题库中高置信公式图片')
    parser.add_argument('--env-file', default=str(SCRIPT_ENV_FILE))
    parser.add_argument('--keyword', default='PAPER_GWY_')
    parser.add_argument('--selection', default='1')
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--max-questions', type=int, default=0)
    parser.add_argument('--max-replacements', type=int, default=0)
    parser.add_argument('--batch-size', type=int, default=100)
    parser.add_argument('--output-dir', default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument('--verify-only', action='store_true')
    parser.add_argument('--verify-sample-limit', type=int, default=0)
    args = parser.parse_args()

    if args.dry_run and args.execute:
        raise ValueError('不能同时指定 --dry-run 和 --execute')

    return RuntimeOptions(
        keyword=str(args.keyword),
        selection=str(args.selection),
        dry_run=not bool(args.execute),
        max_questions=max(0, int(args.max_questions)),
        max_replacements=max(0, int(args.max_replacements)),
        batch_size=max(1, int(args.batch_size)),
        output_dir=Path(str(args.output_dir)),
        verify_only=bool(args.verify_only),
        verify_sample_limit=max(0, int(args.verify_sample_limit)),
    )


def parse_attrs(tag: str) -> dict[str, str]:
    """
    Parse simple HTML tag attributes.

    :param tag: img tag
    :return:
    """
    attrs: dict[str, str] = {}
    for match in ATTR_RE.finditer(tag):
        attrs[match.group('name').lower()] = match.group('value')
    return attrs


def decode_latex_from_url(src: str) -> str:
    """
    Decode latex query value from formula image url.

    :param src: image source
    :return:
    """
    parsed = urlparse(src)
    query = parse_qs(parsed.query, keep_blank_values=True)
    values = query.get('latex') or query.get('tex') or query.get('formula')
    if not values:
        return ''
    return unquote_plus(values[0]).strip()


def parse_index_input(raw: str, max_index: int) -> list[int]:
    """
    Parse index expression like 1,3,8-10/all.

    :param raw: raw input
    :param max_index: max index
    :return:
    """
    text_value = raw.strip().lower()
    if text_value in {'all', 'a', '*'}:
        return list(range(1, max_index + 1))

    selected: set[int] = set()
    parts = [item.strip() for item in raw.split(',') if item.strip()]
    for part in parts:
        if '-' in part:
            left, right = part.split('-', 1)
            start = int(left.strip())
            end = int(right.strip())
            if start > end:
                start, end = end, start
            for index in range(start, end + 1):
                if 1 <= index <= max_index:
                    selected.add(index)
            continue

        index = int(part)
        if 1 <= index <= max_index:
            selected.add(index)
    return sorted(selected)


def split_chunks(values: list[int], chunk_size: int) -> list[list[int]]:
    """
    Split list by chunk size.

    :param values: source values
    :param chunk_size: chunk size
    :return:
    """
    if chunk_size <= 0:
        return [values]
    return [values[index : index + chunk_size] for index in range(0, len(values), chunk_size)]


def normalize_formula(raw_formula: str) -> str:
    """
    Normalize latex formula before writing to HTML.

    :param raw_formula: raw formula
    :return:
    """
    formula = html.unescape(raw_formula).strip()
    if formula.startswith('$') and formula.endswith('$') and len(formula) >= 2:
        formula = formula.strip('$').strip()
    if formula.startswith(r'\(') and formula.endswith(r'\)'):
        formula = formula[2:-2].strip()
    if formula.startswith(r'\[') and formula.endswith(r'\]'):
        formula = formula[2:-2].strip()
    return formula


def render_inline_formula(formula: str) -> str:
    """
    Render formula as HTML-safe inline latex.

    :param formula: normalized formula
    :return:
    """
    escaped_formula = html.escape(formula, quote=False)
    return f'${escaped_formula}$'


def extract_high_confidence_formula(tag: str) -> tuple[str, str]:
    """
    Extract high confidence formula from image tag.

    :param tag: image tag
    :return:
    """
    attrs = parse_attrs(tag)
    explicit_latex = (attrs.get('data-latex') or attrs.get('data-tex') or '').strip()
    if explicit_latex:
        return normalize_formula(explicit_latex), 'formula_attr'

    src = attrs.get('src') or attrs.get('data-src') or attrs.get('_src') or ''
    formula = normalize_formula(decode_latex_from_url(src))
    if formula:
        return formula, 'formula_url'
    lower_src = src.lower()
    if 'latex=' in lower_src and ('latex.huatu.com' in lower_src or '/latex/' in lower_src):
        return '', 'empty_formula_url'

    return '', ''


def compact_text(value: str, limit: int = 240) -> str:
    """
    Build compact report text.

    :param value: source value
    :param limit: max length
    :return:
    """
    text = ' '.join(value.split())
    if len(text) <= limit:
        return text
    return f'{text[:limit]}...'


def replace_formula_images_in_html(
    *,
    source_html: str,
    bank_code: str,
    record_type: str,
    record_id: int,
    question_id: int | None,
    field_name: str,
    max_samples: int = 30,
) -> tuple[str, ReplaceStats]:
    """
    Replace high confidence formula image tags in one HTML fragment.

    :param source_html: source HTML
    :param bank_code: bank code
    :param record_type: record type
    :param record_id: record id
    :param question_id: optional question id
    :param field_name: source field name
    :param max_samples: max samples
    :return:
    """
    stats = ReplaceStats(scanned_records=1)
    if not isinstance(source_html, str) or '<img' not in source_html.lower():
        return source_html, stats

    def replace_match(match) -> str:
        tag = match.group(0)
        formula, source_type = extract_high_confidence_formula(tag)
        if not source_type:
            return tag

        replacement = ''
        if source_type != 'empty_formula_url':
            replacement = render_inline_formula(formula)
        stats.replaced_images += 1
        if source_type == 'formula_attr':
            stats.formula_attr += 1
        if source_type == 'formula_url':
            stats.formula_url += 1
        if source_type == 'empty_formula_url':
            stats.empty_formula_url += 1

        if len(stats.samples) < max_samples:
            attrs = parse_attrs(tag)
            src = attrs.get('src') or attrs.get('data-src') or attrs.get('_src') or ''
            stats.samples.append(
                ReplaceSample(
                    bank_code=bank_code,
                    record_type=record_type,
                    record_id=record_id,
                    question_id=question_id,
                    field_name=field_name,
                    formula=formula,
                    src=src,
                    before=compact_text(tag),
                    after=replacement,
                )
            )
        return replacement

    replaced_html = IMG_TAG_RE.sub(replace_match, source_html)
    if replaced_html != source_html:
        stats.changed_records = 1
    return replaced_html, stats


async def print_database_identity() -> None:
    """Print current database identity for production safety."""
    async with async_db_session() as db:
        result = await db.execute(
            text(
                """
                SELECT
                    current_database() AS database_name,
                    current_user AS database_user,
                    inet_server_addr()::text AS server_addr,
                    inet_server_port() AS server_port,
                    current_schema() AS schema_name
                """
            )
        )
        row = result.mappings().one()

    print(
        '[DB_CFG]'
        f' env_file={SCRIPT_ENV_FILE}'
        f' environment={settings.ENVIRONMENT}'
        f' host={settings.DATABASE_HOST}'
        f' port={settings.DATABASE_PORT}'
        f' database={settings.DATABASE_SCHEMA}'
        f' user={settings.DATABASE_USER}'
    )
    print(
        '[DB_ID]'
        f' current_database={row["database_name"]}'
        f' current_user={row["database_user"]}'
        f' server={row["server_addr"]}:{row["server_port"]}'
        f' schema={row["schema_name"]}'
    )


async def choose_bank_targets(keyword: str, selection: str) -> list[BankTarget]:
    """
    Choose bank targets from database.

    :param keyword: code keyword
    :param selection: index selection
    :return:
    """
    async with async_db_session() as db:
        rows = (
            await db.execute(
                select(
                    QuestionBank.id,
                    QuestionBank.code,
                    QuestionBank.name,
                    func.count(QuestionPlacement.id).label('question_count'),
                )
                .join(QuestionPlacement, QuestionPlacement.bank_id == QuestionBank.id, isouter=True)
                .where(QuestionBank.code.like(f'%{keyword}%'))
                .group_by(QuestionBank.id, QuestionBank.code, QuestionBank.name)
                .order_by(QuestionBank.code.asc())
            )
        ).all()

    banks = [
        BankTarget(
            bank_id=int(row.id),
            bank_code=str(row.code),
            bank_name=str(row.name or ''),
            question_count=int(row.question_count or 0),
        )
        for row in rows
    ]
    if not banks:
        return []

    indices = parse_index_input(selection, len(banks))
    return [banks[index - 1] for index in indices]


async def verify_remaining_formula_image_records(keyword: str) -> dict[str, int]:
    """
    Count remaining high confidence formula image markers.

    :param keyword: bank code keyword
    :return:
    """
    code_like = f'%{keyword}%'
    marker_sql = """
        (
            {field} ILIKE '%data-latex%'
            OR {field} ILIKE '%data-tex%'
            OR {field} ILIKE '%latex=%'
        )
    """
    option_marker_sql = """
        (
            q.options::text ILIKE '%data-latex%'
            OR q.options::text ILIKE '%data-tex%'
            OR q.options::text ILIKE '%latex=%'
        )
    """

    queries = {
        'question_stem': f"""
            SELECT count(DISTINCT q.id) AS value
            FROM study_question q
            JOIN study_question_placement p ON p.question_id = q.id
            JOIN study_question_bank b ON b.id = p.bank_id
            WHERE b.code LIKE :code_like
              AND p.is_active = true
              AND {marker_sql.format(field='q.stem')}
        """,
        'question_options': f"""
            SELECT count(DISTINCT q.id) AS value
            FROM study_question q
            JOIN study_question_placement p ON p.question_id = q.id
            JOIN study_question_bank b ON b.id = p.bank_id
            WHERE b.code LIKE :code_like
              AND p.is_active = true
              AND {option_marker_sql}
        """,
        'analysis_content': f"""
            SELECT count(DISTINCT a.id) AS value
            FROM study_question_analysis a
            JOIN study_question q ON q.id = a.question_id
            JOIN study_question_placement p ON p.question_id = q.id
            JOIN study_question_bank b ON b.id = p.bank_id
            WHERE b.code LIKE :code_like
              AND p.is_active = true
              AND {marker_sql.format(field='a.content')}
        """,
        'material_content': f"""
            SELECT count(DISTINCT m.id) AS value
            FROM study_question_material m
            JOIN study_question_bank b ON b.id = m.bank_id
            WHERE b.code LIKE :code_like
              AND m.is_active = true
              AND {marker_sql.format(field='m.content')}
        """,
    }

    results: dict[str, int] = {}
    async with async_db_session() as db:
        for name, sql in queries.items():
            value = (await db.execute(text(sql), {'code_like': code_like})).scalar_one()
            results[name] = int(value or 0)
    return results


def find_marker_snippet(value: str, limit: int = 420) -> str:
    """
    Build snippet around formula image marker.

    :param value: source value
    :param limit: max length
    :return:
    """
    lower_value = value.lower()
    positions = [
        position
        for position in [
            lower_value.find('data-latex'),
            lower_value.find('data-tex'),
            lower_value.find('latex='),
        ]
        if position >= 0
    ]
    if not positions:
        return compact_text(value, limit)
    start = max(0, min(positions) - 160)
    return compact_text(value[start : start + limit], limit)


async def print_verify_samples(keyword: str, sample_limit: int) -> None:
    """
    Print remaining marker samples.

    :param keyword: bank code keyword
    :param sample_limit: sample limit
    :return:
    """
    if sample_limit <= 0:
        return

    code_like = f'%{keyword}%'
    sql = """
        SELECT source_type, record_id, question_id, bank_code, content
        FROM (
            SELECT DISTINCT
                'question_stem' AS source_type,
                q.id AS record_id,
                q.id AS question_id,
                b.code AS bank_code,
                q.stem AS content
            FROM study_question q
            JOIN study_question_placement p ON p.question_id = q.id
            JOIN study_question_bank b ON b.id = p.bank_id
            WHERE b.code LIKE :code_like
              AND p.is_active = true
              AND (
                  q.stem ILIKE '%data-latex%'
                  OR q.stem ILIKE '%data-tex%'
                  OR q.stem ILIKE '%latex=%'
              )
            UNION ALL
            SELECT DISTINCT
                'question_options' AS source_type,
                q.id AS record_id,
                q.id AS question_id,
                b.code AS bank_code,
                q.options::text AS content
            FROM study_question q
            JOIN study_question_placement p ON p.question_id = q.id
            JOIN study_question_bank b ON b.id = p.bank_id
            WHERE b.code LIKE :code_like
              AND p.is_active = true
              AND (
                  q.options::text ILIKE '%data-latex%'
                  OR q.options::text ILIKE '%data-tex%'
                  OR q.options::text ILIKE '%latex=%'
              )
            UNION ALL
            SELECT DISTINCT
                'analysis_content' AS source_type,
                a.id AS record_id,
                a.question_id AS question_id,
                b.code AS bank_code,
                a.content AS content
            FROM study_question_analysis a
            JOIN study_question q ON q.id = a.question_id
            JOIN study_question_placement p ON p.question_id = q.id
            JOIN study_question_bank b ON b.id = p.bank_id
            WHERE b.code LIKE :code_like
              AND p.is_active = true
              AND (
                  a.content ILIKE '%data-latex%'
                  OR a.content ILIKE '%data-tex%'
                  OR a.content ILIKE '%latex=%'
              )
            UNION ALL
            SELECT DISTINCT
                'material_content' AS source_type,
                m.id AS record_id,
                NULL::bigint AS question_id,
                b.code AS bank_code,
                m.content AS content
            FROM study_question_material m
            JOIN study_question_bank b ON b.id = m.bank_id
            WHERE b.code LIKE :code_like
              AND m.is_active = true
              AND (
                  m.content ILIKE '%data-latex%'
                  OR m.content ILIKE '%data-tex%'
                  OR m.content ILIKE '%latex=%'
              )
        ) t
        ORDER BY source_type, bank_code, record_id
        LIMIT :sample_limit
    """
    async with async_db_session() as db:
        rows = (await db.execute(text(sql), {'code_like': code_like, 'sample_limit': sample_limit})).mappings().all()

    for row in rows:
        snippet = find_marker_snippet(str(row['content'] or ''))
        print(
            '[VERIFY_SAMPLE]'
            f' source={row["source_type"]}'
            f' bank={row["bank_code"]}'
            f' record_id={row["record_id"]}'
            f' question_id={row["question_id"]}'
            f' snippet={snippet}'
        )


def replace_question_fields(question: Question, bank: BankTarget) -> ReplaceStats:
    """
    Replace formula images in one question.

    :param question: question row
    :param bank: target bank
    :return:
    """
    total = ReplaceStats()
    stem, stats = replace_formula_images_in_html(
        source_html=question.stem,
        bank_code=bank.bank_code,
        record_type='question',
        record_id=int(question.id),
        question_id=int(question.id),
        field_name='stem',
    )
    total.add(stats)
    if stem != question.stem:
        question.stem = stem

    options = question.options
    if not isinstance(options, list):
        return total

    changed_options = False
    new_options: list[dict] = []
    for option in options:
        if not isinstance(option, dict):
            new_options.append(option)
            continue

        content = str(option.get('content') or '')
        option_code = str(option.get('option_code') or '')
        new_content, option_stats = replace_formula_images_in_html(
            source_html=content,
            bank_code=bank.bank_code,
            record_type='question_option',
            record_id=int(question.id),
            question_id=int(question.id),
            field_name=f'option_{option_code}',
        )
        total.add(option_stats)
        if new_content != content:
            changed_options = True
            option = {**option, 'content': new_content}
        new_options.append(option)

    if changed_options:
        question.options = new_options
    return total


def replace_analysis_fields(analysis: QuestionAnalysis, bank: BankTarget) -> ReplaceStats:
    """
    Replace formula images in one analysis.

    :param analysis: analysis row
    :param bank: target bank
    :return:
    """
    content, stats = replace_formula_images_in_html(
        source_html=analysis.content,
        bank_code=bank.bank_code,
        record_type='analysis',
        record_id=int(analysis.id),
        question_id=int(analysis.question_id),
        field_name=f'analysis_{analysis.type}_{analysis.version_no}',
    )
    if content != analysis.content:
        analysis.content = content
    return stats


def replace_material_fields(material: QuestionMaterial, bank: BankTarget) -> ReplaceStats:
    """
    Replace formula images in one material.

    :param material: material row
    :param bank: target bank
    :return:
    """
    content, stats = replace_formula_images_in_html(
        source_html=material.content,
        bank_code=bank.bank_code,
        record_type='material',
        record_id=int(material.id),
        question_id=None,
        field_name='material_content',
    )
    if content != material.content:
        material.content = content
    return stats


async def process_bank(bank: BankTarget, args: RuntimeOptions) -> ReplaceStats:
    """
    Process one bank.

    :param bank: target bank
    :param args: runtime options
    :return:
    """
    total = ReplaceStats()
    async with async_db_session() as db:
        qid_rows = await db.execute(
            select(QuestionPlacement.question_id)
            .where(QuestionPlacement.bank_id == bank.bank_id, QuestionPlacement.is_active.is_(True))
            .order_by(QuestionPlacement.sort_order.asc(), QuestionPlacement.question_id.asc())
        )
        question_ids = [int(value) for value in qid_rows.scalars().all()]
        if args.max_questions > 0:
            question_ids = question_ids[: args.max_questions]

        for chunk_index, qid_chunk in enumerate(split_chunks(question_ids, args.batch_size), start=1):
            questions = (await db.execute(select(Question).where(Question.id.in_(qid_chunk)))).scalars().all()
            analyses = (
                await db.execute(select(QuestionAnalysis).where(QuestionAnalysis.question_id.in_(qid_chunk)))
            ).scalars().all()

            for question in questions:
                total.add(replace_question_fields(question, bank))
                if 0 < args.max_replacements <= total.replaced_images:
                    break

            for analysis in analyses:
                if 0 < args.max_replacements <= total.replaced_images:
                    break
                total.add(replace_analysis_fields(analysis, bank))

            await db.flush()
            print(
                '[BANK_PROGRESS]'
                f' code={bank.bank_code}'
                f' chunk={chunk_index}'
                f' scanned_records={total.scanned_records}'
                f' changed_records={total.changed_records}'
                f' replaced_images={total.replaced_images}'
                f' empty_formula_url={total.empty_formula_url}'
                f' dry_run={args.dry_run}'
            )
            if 0 < args.max_replacements <= total.replaced_images:
                break

        if args.max_replacements <= 0 or total.replaced_images < args.max_replacements:
            materials = (
                await db.execute(
                    select(QuestionMaterial).where(QuestionMaterial.bank_id == bank.bank_id, QuestionMaterial.is_active)
                )
            ).scalars().all()
            for material in materials:
                total.add(replace_material_fields(material, bank))
                if 0 < args.max_replacements <= total.replaced_images:
                    break
            await db.flush()

        if args.dry_run:
            await db.rollback()
            print(f'[BANK] rollback code={bank.bank_code}')
        else:
            await db.commit()
            print(f'[BANK] commit code={bank.bank_code}')
    return total


def write_sample_report(path: Path, stats: ReplaceStats) -> None:
    """
    Write replacement sample report.

    :param path: output path
    :param stats: replacement stats
    :return:
    """
    fieldnames = [
        'bank_code',
        'record_type',
        'record_id',
        'question_id',
        'field_name',
        'formula',
        'src',
        'before',
        'after',
    ]
    with path.open('w', encoding='utf-8-sig', newline='') as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        for sample in stats.samples:
            writer.writerow({field_name: getattr(sample, field_name) for field_name in fieldnames})


async def run() -> int:
    """Program entry."""
    args = parse_runtime_options()
    await print_database_identity()

    if args.verify_only:
        results = await verify_remaining_formula_image_records(args.keyword)
        total = sum(results.values())
        for key, value in results.items():
            print(f'[VERIFY] {key}={value}')
        await print_verify_samples(args.keyword, args.verify_sample_limit)
        print(f'[VERIFY_DONE] total={total} keyword={args.keyword}')
        return 0

    targets = await choose_bank_targets(args.keyword, args.selection)
    if not targets:
        print('[TARGETS] matched=0')
        return 0

    print(
        '[TARGETS]'
        f' selected={len(targets)}'
        f' keyword={args.keyword}'
        f' selection={args.selection}'
        f' dry_run={args.dry_run}'
    )
    for target in targets[:20]:
        print(f'[TARGET] code={target.bank_code} questions={target.question_count} name={target.bank_name}')

    total = ReplaceStats()
    for index, target in enumerate(targets, start=1):
        print(f'\n[RUN] {index}/{len(targets)} code={target.bank_code}')
        bank_stats = await process_bank(target, args)
        total.add(bank_stats)
        print(
            '[BANK_DONE]'
            f' code={target.bank_code}'
            f' changed_records={bank_stats.changed_records}'
            f' replaced_images={bank_stats.replaced_images}'
            f' formula_attr={bank_stats.formula_attr}'
            f' formula_url={bank_stats.formula_url}'
            f' empty_formula_url={bank_stats.empty_formula_url}'
        )
        if 0 < args.max_replacements <= total.replaced_images:
            break

    args.output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    report_path = args.output_dir / f'qbank_formula_image_replace_{timestamp}.csv'
    write_sample_report(report_path, total)

    print(f'[REPORT] samples={report_path}')
    print(
        '[DONE]'
        f' scanned_records={total.scanned_records}'
        f' changed_records={total.changed_records}'
        f' replaced_images={total.replaced_images}'
        f' formula_attr={total.formula_attr}'
        f' formula_url={total.formula_url}'
        f' empty_formula_url={total.empty_formula_url}'
        f' dry_run={args.dry_run}'
    )
    return 0


if __name__ == '__main__':
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass
    raise SystemExit(asyncio.run(run()))
