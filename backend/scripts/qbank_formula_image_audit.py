#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import asyncio
import builtins
import csv
import os
import re
import sys

from dataclasses import dataclass
from datetime import datetime
from html import escape
from pathlib import Path
from urllib.parse import parse_qs, unquote_plus, urlparse

from sqlalchemy import func, select, text

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

DEFAULT_ENV_FILE = PROJECT_ROOT / 'backend' / '.env.prod'
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / 'backend' / 'scripts' / 'reports'


def resolve_script_env_file() -> Path:
    """Resolve script env file before backend settings import."""
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument('--env-file', default=os.environ.get('FBA_SCRIPT_ENV_FILE', str(DEFAULT_ENV_FILE)))
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


def print(*args, **kwargs) -> None:
    """Print with flush enabled for long-running scripts."""
    kwargs.setdefault('flush', True)
    builtins.print(*args, **kwargs)


from backend.app.question_bank.model import (  # noqa: E402
    Question,
    QuestionAnalysis,
    QuestionBank,
    QuestionMaterial,
    QuestionPlacement,
)
from backend.core.conf import settings  # noqa: E402
from backend.database.db import async_db_session  # noqa: E402

IMG_TAG_RE = re.compile(r'<img\b(?:[^>"\']+|"[^"]*"|\'[^\']*\')*>', re.IGNORECASE)
ATTR_RE = re.compile(r'(?P<name>[a-zA-Z_:][-a-zA-Z0-9_:.]*)\s*=\s*(?P<quote>"|\')(?P<value>.*?)(?P=quote)')
STYLE_SIZE_RE = re.compile(r'(?P<name>width|height)\s*:\s*(?P<value>\d+(?:\.\d+)?)\s*px?', re.IGNORECASE)
TAG_RE = re.compile(r'<[^>]+>')
SPACE_RE = re.compile(r'\s+')


@dataclass
class RuntimeOptions:
    """Script runtime options."""

    env_file: Path
    keyword: str
    selection: str
    max_questions: int
    max_images: int
    output_dir: Path
    include_own_oss: bool
    list_only: bool


@dataclass
class BankTarget:
    """Audit bank target."""

    bank_id: int
    bank_code: str
    bank_name: str
    question_count: int


@dataclass
class ImageHit:
    """Image audit hit."""

    index: int
    bank_code: str
    bank_name: str
    record_type: str
    record_id: int
    question_id: int | None
    field_name: str
    image_index: int
    category: str
    suggested_action: str
    confidence: str
    src: str
    decoded_latex: str
    width: float | None
    height: float | None
    context_text: str
    img_tag: str


def parse_runtime_options() -> RuntimeOptions:
    """Parse script runtime options."""
    parser = argparse.ArgumentParser(description='审计题库公式图片与内容图片')
    parser.add_argument('--env-file', default=str(SCRIPT_ENV_FILE))
    parser.add_argument('--keyword', default='PAPER_GWY_')
    parser.add_argument('--selection', default='1')
    parser.add_argument('--max-questions', type=int, default=0)
    parser.add_argument('--max-images', type=int, default=3000)
    parser.add_argument('--output-dir', default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument('--include-own-oss', action='store_true')
    parser.add_argument('--list-only', action='store_true')
    args = parser.parse_args()

    return RuntimeOptions(
        env_file=Path(str(args.env_file)),
        keyword=str(args.keyword),
        selection=str(args.selection),
        max_questions=max(0, int(args.max_questions)),
        max_images=max(1, int(args.max_images)),
        output_dir=Path(str(args.output_dir)),
        include_own_oss=bool(args.include_own_oss),
        list_only=bool(args.list_only),
    )


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


def parse_float(value: str | None) -> float | None:
    """
    Parse numeric html size value.

    :param value: raw value
    :return:
    """
    if not value:
        return None
    match = re.search(r'\d+(?:\.\d+)?', value)
    if not match:
        return None
    return float(match.group(0))


def parse_image_size(attrs: dict[str, str]) -> tuple[float | None, float | None]:
    """
    Parse width and height from attributes or style.

    :param attrs: img attrs
    :return:
    """
    width = parse_float(attrs.get('width'))
    height = parse_float(attrs.get('height'))
    style = attrs.get('style') or ''

    if width is not None and height is not None:
        return width, height

    style_sizes: dict[str, float] = {}
    for match in STYLE_SIZE_RE.finditer(style):
        style_sizes[match.group('name').lower()] = float(match.group('value'))

    if width is None:
        width = style_sizes.get('width')
    if height is None:
        height = style_sizes.get('height')
    return width, height


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


def normalize_plain_text(html: str) -> str:
    """
    Strip tags and normalize spaces for context preview.

    :param html: source html
    :return:
    """
    text = TAG_RE.sub(' ', html)
    text = SPACE_RE.sub(' ', text)
    return text.strip()


def build_context(html: str, start: int, end: int, radius: int = 90) -> str:
    """
    Build short context around image tag.

    :param html: source html
    :param start: image tag start
    :param end: image tag end
    :param radius: context radius
    :return:
    """
    left = max(0, start - radius)
    right = min(len(html), end + radius)
    return normalize_plain_text(html[left:right])[:240]


def is_own_oss_url(src: str) -> bool:
    """
    Detect current target OSS domain.

    :param src: image source
    :return:
    """
    host = urlparse(src).netloc.lower()
    return host in {'aicdn.yzxj.vip', 'yzxj.vip'} or host.endswith('.aicdn.yzxj.vip')


def classify_image(
    src: str,
    width: float | None,
    height: float | None,
    explicit_latex: str = '',
) -> tuple[str, str, str, str]:
    """
    Classify image hit conservatively.

    :param src: image source
    :param width: image width
    :param height: image height
    :param explicit_latex: latex value from img attrs
    :return:
    """
    lower_src = src.lower()
    if explicit_latex:
        return 'formula_attr', 'auto_replace_latex', 'high', explicit_latex

    latex_value = decode_latex_from_url(src)
    parsed = urlparse(src)
    host = parsed.netloc.lower()
    path = parsed.path.lower()

    if 'latex' in host or '/latex/' in path or 'latex=' in lower_src:
        if latex_value:
            return 'formula_url', 'auto_replace_latex', 'high', latex_value
        return 'broken_formula_url', 'manual_check_or_drop_empty_formula', 'medium', ''

    if width is None or height is None:
        return 'unknown_image', 'manual_check', 'low', ''

    area = width * height
    if height <= 80 and width <= 900:
        return 'inline_formula_like', 'manual_check_formula', 'medium', ''

    if height <= 120 and width <= 520 and area <= 50000:
        return 'inline_formula_like', 'manual_check_formula', 'medium', ''

    if width >= 300 and height >= 120:
        return 'content_image', 'keep_image', 'medium', ''

    return 'unknown_image', 'manual_check', 'low', ''


def iter_image_hits(
    *,
    html: str,
    bank: BankTarget,
    record_type: str,
    record_id: int,
    question_id: int | None,
    field_name: str,
    start_index: int,
    include_own_oss: bool,
) -> list[ImageHit]:
    """
    Extract image hits from one HTML fragment.

    :param html: source html
    :param bank: bank target
    :param record_type: record type
    :param record_id: source record id
    :param question_id: optional question id
    :param field_name: source field name
    :param start_index: global start index
    :param include_own_oss: whether include own OSS images
    :return:
    """
    if not isinstance(html, str) or '<img' not in html.lower():
        return []

    hits: list[ImageHit] = []
    for image_index, match in enumerate(IMG_TAG_RE.finditer(html), start=1):
        tag = match.group(0)
        attrs = parse_attrs(tag)
        src = attrs.get('src') or attrs.get('data-src') or attrs.get('_src') or ''
        if not src:
            continue
        if is_own_oss_url(src) and not include_own_oss:
            continue

        width, height = parse_image_size(attrs)
        explicit_latex = (attrs.get('data-latex') or attrs.get('data-tex') or '').strip()
        category, action, confidence, latex_value = classify_image(src, width, height, explicit_latex)
        hits.append(
            ImageHit(
                index=start_index + len(hits) + 1,
                bank_code=bank.bank_code,
                bank_name=bank.bank_name,
                record_type=record_type,
                record_id=record_id,
                question_id=question_id,
                field_name=field_name,
                image_index=image_index,
                category=category,
                suggested_action=action,
                confidence=confidence,
                src=src,
                decoded_latex=latex_value,
                width=width,
                height=height,
                context_text=build_context(html, match.start(), match.end()),
                img_tag=tag,
            )
        )
    return hits


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


async def collect_bank_hits(bank: BankTarget, args: RuntimeOptions, start_index: int) -> list[ImageHit]:
    """
    Collect image hits from one bank.

    :param bank: target bank
    :param args: runtime options
    :param start_index: global start index
    :return:
    """
    hits: list[ImageHit] = []
    async with async_db_session() as db:
        qid_rows = await db.execute(
            select(QuestionPlacement.question_id)
            .where(QuestionPlacement.bank_id == bank.bank_id, QuestionPlacement.is_active.is_(True))
            .order_by(QuestionPlacement.sort_order.asc(), QuestionPlacement.question_id.asc())
        )
        question_ids = [int(value) for value in qid_rows.scalars().all()]
        if args.max_questions > 0:
            question_ids = question_ids[: args.max_questions]

        for qid_chunk in split_chunks(question_ids, 100):
            questions = (await db.execute(select(Question).where(Question.id.in_(qid_chunk)))).scalars().all()
            analyses = (
                await db.execute(select(QuestionAnalysis).where(QuestionAnalysis.question_id.in_(qid_chunk)))
            ).scalars().all()

            for question in questions:
                hits.extend(
                    iter_image_hits(
                        html=question.stem,
                        bank=bank,
                        record_type='question',
                        record_id=int(question.id),
                        question_id=int(question.id),
                        field_name='stem',
                        start_index=start_index + len(hits),
                        include_own_oss=args.include_own_oss,
                    )
                )
                options = question.options
                if not isinstance(options, list):
                    continue
                for option in options:
                    if not isinstance(option, dict):
                        continue
                    content = str(option.get('content') or '')
                    option_code = str(option.get('option_code') or '')
                    hits.extend(
                        iter_image_hits(
                            html=content,
                            bank=bank,
                            record_type='question_option',
                            record_id=int(question.id),
                            question_id=int(question.id),
                            field_name=f'option_{option_code}',
                            start_index=start_index + len(hits),
                            include_own_oss=args.include_own_oss,
                        )
                    )

            for analysis in analyses:
                hits.extend(
                    iter_image_hits(
                        html=analysis.content,
                        bank=bank,
                        record_type='analysis',
                        record_id=int(analysis.id),
                        question_id=int(analysis.question_id),
                        field_name=f'analysis_{analysis.type}_{analysis.version_no}',
                        start_index=start_index + len(hits),
                        include_own_oss=args.include_own_oss,
                    )
                )

            if len(hits) >= args.max_images:
                return hits[: args.max_images]

        materials = (
            await db.execute(
                select(QuestionMaterial).where(QuestionMaterial.bank_id == bank.bank_id, QuestionMaterial.is_active)
            )
        ).scalars().all()
        for material in materials:
            hits.extend(
                iter_image_hits(
                    html=material.content,
                    bank=bank,
                    record_type='material',
                    record_id=int(material.id),
                    question_id=None,
                    field_name='material_content',
                    start_index=start_index + len(hits),
                    include_own_oss=args.include_own_oss,
                )
            )
            if len(hits) >= args.max_images:
                return hits[: args.max_images]

    return hits


def format_size(width: float | None, height: float | None) -> str:
    """
    Format image size.

    :param width: width
    :param height: height
    :return:
    """
    if width is None and height is None:
        return ''
    return f'{width or ""}×{height or ""}'


def write_csv_report(path: Path, hits: list[ImageHit]) -> None:
    """
    Write CSV report.

    :param path: output path
    :param hits: image hits
    :return:
    """
    fieldnames = [
        'index',
        'bank_code',
        'bank_name',
        'record_type',
        'record_id',
        'question_id',
        'field_name',
        'image_index',
        'category',
        'suggested_action',
        'confidence',
        'width',
        'height',
        'decoded_latex',
        'src',
        'context_text',
        'img_tag',
    ]
    with path.open('w', encoding='utf-8-sig', newline='') as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        for hit in hits:
            writer.writerow({field: getattr(hit, field) for field in fieldnames})


def render_summary(hits: list[ImageHit]) -> str:
    """
    Render summary HTML.

    :param hits: image hits
    :return:
    """
    category_counts: dict[str, int] = {}
    action_counts: dict[str, int] = {}
    for hit in hits:
        category_counts[hit.category] = category_counts.get(hit.category, 0) + 1
        action_counts[hit.suggested_action] = action_counts.get(hit.suggested_action, 0) + 1

    rows = ['<h2>汇总</h2>', '<div class="summary-grid">']
    rows.append('<div><h3>分类</h3><table><tbody>')
    for key, count in sorted(category_counts.items()):
        rows.append(f'<tr><th>{escape(key)}</th><td>{count}</td></tr>')
    rows.append('</tbody></table></div>')
    rows.append('<div><h3>建议动作</h3><table><tbody>')
    for key, count in sorted(action_counts.items()):
        rows.append(f'<tr><th>{escape(key)}</th><td>{count}</td></tr>')
    rows.append('</tbody></table></div></div>')
    return ''.join(rows)


def write_html_report(path: Path, hits: list[ImageHit], csv_name: str) -> None:
    """
    Write HTML report.

    :param path: output path
    :param hits: image hits
    :param csv_name: CSV file name
    :return:
    """
    rows = [
        '<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        '<title>题库公式图片预审</title>',
        '<style>',
        'body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;margin:24px;color:#1f2937}',
        'table{border-collapse:collapse;width:100%;font-size:13px}th,td{border:1px solid #e5e7eb;padding:8px}',
        'th{background:#f9fafb;text-align:left}.summary-grid{display:grid;grid-template-columns:1fr 1fr;gap:16px}',
        '.hit{border:1px solid #e5e7eb;border-radius:10px;padding:14px;margin:14px 0}.meta{color:#6b7280;font-size:12px}',
        '.preview{max-width:420px;max-height:220px;border:1px solid #e5e7eb;background:#fff;margin:8px 0}',
        '.url{word-break:break-all;font-family:ui-monospace,Consolas,monospace;font-size:12px}',
        '.tag{word-break:break-all;background:#f9fafb;padding:8px;border-radius:6px;font-size:12px}',
        '.formula_url{border-left:6px solid #22c55e}.inline_formula_like{border-left:6px solid #f59e0b}',
        '.content_image{border-left:6px solid #3b82f6}.unknown_image,.broken_formula_url{border-left:6px solid #ef4444}',
        '</style></head><body>',
        '<h1>题库公式图片预审</h1>',
        f'<p class="meta">生成时间：{escape(datetime.now().isoformat(timespec="seconds"))}</p>',
        f'<p>CSV：<a href="{escape(csv_name)}">{escape(csv_name)}</a></p>',
        render_summary(hits),
        '<h2>明细</h2>',
    ]

    for hit in hits:
        latex_block = ''
        if hit.decoded_latex:
            latex_block = f'<p><strong>解码公式：</strong><code>{escape(hit.decoded_latex)}</code></p>'
        rows.extend(
            [
                f'<section class="hit {escape(hit.category)}">',
                f'<h3>#{hit.index} {escape(hit.category)} / {escape(hit.suggested_action)}</h3>',
                '<p class="meta">'
                f'{escape(hit.bank_code)}｜{escape(hit.record_type)}:{hit.record_id}'
                f'｜question_id={escape(str(hit.question_id or ""))}'
                f'｜field={escape(hit.field_name)}｜size={escape(format_size(hit.width, hit.height))}'
                f'｜confidence={escape(hit.confidence)}'
                '</p>',
                f'<img class="preview" src="{escape(hit.src)}" loading="lazy">',
                latex_block,
                f'<p><strong>上下文：</strong>{escape(hit.context_text)}</p>',
                f'<p class="url"><strong>URL：</strong>{escape(hit.src)}</p>',
                f'<pre class="tag">{escape(hit.img_tag)}</pre>',
                '</section>',
            ]
        )

    rows.append('</body></html>')
    path.write_text(''.join(rows), encoding='utf-8')


async def run() -> int:
    """Program entry."""
    args = parse_runtime_options()
    await print_database_identity()

    targets = await choose_bank_targets(args.keyword, args.selection)
    if not targets:
        print('[TARGETS] matched=0')
        return 0

    print(f'[TARGETS] selected={len(targets)} keyword={args.keyword} selection={args.selection}')
    for target in targets[:20]:
        print(f'[TARGET] code={target.bank_code} questions={target.question_count} name={target.bank_name}')
    if args.list_only:
        return 0

    all_hits: list[ImageHit] = []
    for index, target in enumerate(targets, start=1):
        print(f'[RUN] {index}/{len(targets)} code={target.bank_code}')
        hits = await collect_bank_hits(target, args, len(all_hits))
        all_hits.extend(hits)
        print(f'[BANK_DONE] code={target.bank_code} image_hits={len(hits)} total={len(all_hits)}')
        if len(all_hits) >= args.max_images:
            all_hits = all_hits[: args.max_images]
            break

    args.output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    csv_path = args.output_dir / f'qbank_formula_image_audit_{timestamp}.csv'
    html_path = args.output_dir / f'qbank_formula_image_audit_{timestamp}.html'

    write_csv_report(csv_path, all_hits)
    write_html_report(html_path, all_hits, csv_path.name)

    print(f'[REPORT] csv={csv_path}')
    print(f'[REPORT] html={html_path}')
    print(f'[DONE] image_hits={len(all_hits)} include_own_oss={args.include_own_oss}')
    return 0


if __name__ == '__main__':
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass
    raise SystemExit(asyncio.run(run()))
