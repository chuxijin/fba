#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio
import sys

from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.question_bank.crud.crud_question import option_content_dao, question_option_dao
from backend.app.question_bank.model import (
    Question,
    QuestionAnalysis,
    QuestionBank,
    QuestionMaterial,
    QuestionPlacement,
)
from backend.app.question_bank.schema.question import UpsertQuestionOptionItem
from backend.database.db import async_db_session
from backend.scripts.qbank_image_mirror import QbankImageMirror


@dataclass
class BankTarget:
    bank_id: int
    bank_code: str
    bank_name: str
    question_count: int


@dataclass
class MirrorRunStats:
    question_total: int = 0
    question_updated: int = 0
    analysis_total: int = 0
    analysis_updated: int = 0
    option_question_total: int = 0
    option_question_updated: int = 0
    material_total: int = 0
    material_updated: int = 0

    def add(self, other: MirrorRunStats) -> None:
        """
        Merge another stats into current stats.

        :param other: source stats
        :return:
        """
        self.question_total += other.question_total
        self.question_updated += other.question_updated
        self.analysis_total += other.analysis_total
        self.analysis_updated += other.analysis_updated
        self.option_question_total += other.option_question_total
        self.option_question_updated += other.option_question_updated
        self.material_total += other.material_total
        self.material_updated += other.material_updated


def ask(prompt: str, default: str | None = None) -> str:
    """
    Read interactive input.

    :param prompt: prompt text
    :param default: optional default text
    :return:
    """
    if default is None:
        return input(f"{prompt}: ").strip()

    value = input(f"{prompt} [{default}]: ").strip()
    if value:
        return value
    return default


def ask_int(prompt: str, default: int) -> int:
    """
    Read int input.

    :param prompt: prompt text
    :param default: default int
    :return:
    """
    while True:
        raw = ask(prompt, str(default))
        try:
            return int(raw)
        except ValueError:
            print("请输入整数")


def ask_yes_no(prompt: str, default_yes: bool = True) -> bool:
    """
    Read yes/no input.

    :param prompt: prompt text
    :param default_yes: default bool
    :return:
    """
    default = "Y/n" if default_yes else "y/N"
    while True:
        raw = input(f"{prompt} [{default}]: ").strip().lower()
        if not raw:
            return default_yes
        if raw in {"y", "yes"}:
            return True
        if raw in {"n", "no"}:
            return False
        print("请输入 y 或 n")


def parse_index_input(raw: str, max_index: int) -> list[int]:
    """
    Parse index expression like 1,3,8-10/all.

    :param raw: raw input
    :param max_index: max index
    :return:
    """
    text_value = raw.strip().lower()
    if text_value in {"all", "a", "*"}:
        return list(range(1, max_index + 1))

    selected: set[int] = set()
    parts = [item.strip() for item in raw.split(",") if item.strip()]
    for part in parts:
        if "-" in part:
            left, right = part.split("-", 1)
            start = int(left.strip())
            end = int(right.strip())
            if start > end:
                start, end = end, start
            for idx in range(start, end + 1):
                if 1 <= idx <= max_index:
                    selected.add(idx)
            continue
        idx = int(part)
        if 1 <= idx <= max_index:
            selected.add(idx)
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


async def choose_bank_targets() -> list[BankTarget]:
    """Choose bank targets from database."""
    keyword = ask("输入题库 code 关键字（支持模糊）", "PAPER_")
    code_like = f"%{keyword}%"
    async with async_db_session() as db:
        stmt = (
            select(
                QuestionBank.id,
                QuestionBank.code,
                QuestionBank.name,
                func.count(QuestionPlacement.id).label("question_count"),
            )
            .join(QuestionPlacement, QuestionPlacement.bank_id == QuestionBank.id, isouter=True)
            .where(QuestionBank.code.like(code_like))
            .group_by(QuestionBank.id, QuestionBank.code, QuestionBank.name)
            .order_by(QuestionBank.code.asc())
        )
        rows = (await db.execute(stmt)).all()

    banks: list[BankTarget] = []
    for row in rows:
        banks.append(
            BankTarget(
                bank_id=int(row.id),
                bank_code=str(row.code),
                bank_name=str(row.name or ""),
                question_count=int(row.question_count or 0),
            )
        )

    if not banks:
        print("未找到匹配题库")
        return []

    print(f"\n匹配题库 {len(banks)} 个（最多显示前 120 个）:")
    show_count = min(120, len(banks))
    for index in range(show_count):
        bank = banks[index]
        print(
            f"{index + 1:>3}. code={bank.bank_code} "
            f"questions={bank.question_count} name={bank.bank_name}"
        )
    if len(banks) > show_count:
        print(f"... 其余 {len(banks) - show_count} 个未显示，可先缩小关键字后再选")

    while True:
        raw = ask("输入序号（支持 1,3,8-10；all=全部）", "1")
        try:
            indices = parse_index_input(raw, len(banks))
        except Exception:
            print("序号格式错误，请重试")
            continue
        if not indices:
            print("请至少选择一个题库")
            continue
        selected = [banks[index - 1] for index in indices]
        print("已选择:")
        for bank in selected:
            print(f"  - {bank.bank_code} ({bank.bank_name})")
        return selected


async def mirror_html_text(
    *,
    mirror: QbankImageMirror,
    html: str,
    bank_code: str,
    field_name: str,
    question_id: int | None = None,
    scope_segment: str | None = None,
) -> tuple[str, bool]:
    """
    Mirror html text and return changed flag.

    :param mirror: mirror service
    :param html: source html
    :param bank_code: bank code
    :param field_name: field name
    :param question_id: optional question id
    :param scope_segment: optional scope segment
    :return:
    """
    if not isinstance(html, str):
        return html, False
    if "<img" not in html.lower():
        return html, False

    mirrored = await mirror.mirror_html(
        html=html,
        bank_code=bank_code,
        field_name=field_name,
        question_id=question_id,
        scope_segment=scope_segment,
    )
    return mirrored, mirrored != html


async def process_bank(
    *,
    db: AsyncSession,
    mirror: QbankImageMirror,
    target: BankTarget,
    args: SimpleNamespace,
) -> MirrorRunStats:
    """
    Mirror one bank existing data.

    :param db: db session
    :param mirror: mirror service
    :param target: target bank
    :param args: run args
    :return:
    """
    stats = MirrorRunStats()
    try:
        await db.execute(select(func.set_config("lock_timeout", "8s", True)))
        await db.execute(select(func.set_config("statement_timeout", "120s", True)))
    except Exception as exc:
        print(f"[BANK][WARN] set timeout failed code={target.bank_code} error={exc!s}")

    qid_stmt = (
        select(QuestionPlacement.question_id)
        .where(
            QuestionPlacement.bank_id == target.bank_id,
            QuestionPlacement.is_active.is_(True),
        )
        .order_by(QuestionPlacement.sort_order.asc(), QuestionPlacement.question_id.asc())
    )
    qids = [int(value) for value in (await db.execute(qid_stmt)).scalars().all()]
    if args.max_questions > 0:
        qids = qids[: args.max_questions]

    stats.question_total = len(qids)
    print(
        f"[BANK] code={target.bank_code} name={target.bank_name} "
        f"questions={len(qids)} dry_run={args.dry_run}"
    )

    chunk_size = max(1, args.batch_size)
    chunks = split_chunks(qids, chunk_size)
    for chunk_index, qid_chunk in enumerate(chunks, start=1):
        question_rows = (
            await db.execute(select(Question).where(Question.id.in_(qid_chunk)))
        ).scalars().all()
        question_map = {row.id: row for row in question_rows}

        analysis_rows = (
            await db.execute(select(QuestionAnalysis).where(QuestionAnalysis.question_id.in_(qid_chunk)))
        ).scalars().all()
        analysis_map: dict[int, list[QuestionAnalysis]] = {}
        for row in analysis_rows:
            analysis_map.setdefault(int(row.question_id), []).append(row)

        stats.analysis_total += len(analysis_rows)

        for qid in qid_chunk:
            question = question_map.get(qid)
            if question is not None:
                stem, changed = await mirror_html_text(
                    mirror=mirror,
                    html=question.stem,
                    bank_code=target.bank_code,
                    field_name="stem",
                    question_id=qid,
                )
                if changed:
                    question.stem = stem
                    stats.question_updated += 1

            for analysis in analysis_map.get(qid, []):
                content, changed = await mirror_html_text(
                    mirror=mirror,
                    html=analysis.content,
                    bank_code=target.bank_code,
                    field_name=f"analysis_{analysis.type}_{analysis.version_no}",
                    question_id=qid,
                )
                if not changed:
                    continue
                analysis.content = content
                stats.analysis_updated += 1

            options = await question_option_dao.list_by_question(db, question_id=qid)
            if options:
                stats.option_question_total += 1

            option_items: list[UpsertQuestionOptionItem] = []
            option_changed = False
            for option in options:
                source_content = option.content_ref.content if option.content_ref else ""
                mirrored_content, changed = await mirror_html_text(
                    mirror=mirror,
                    html=source_content,
                    bank_code=target.bank_code,
                    field_name=f"option_{option.option_code}",
                    question_id=qid,
                )
                if changed:
                    option_changed = True
                option_items.append(
                    UpsertQuestionOptionItem(
                        option_code=option.option_code,
                        content=mirrored_content,
                        sort_order=option.sort_order,
                        is_active=option.is_active,
                    )
                )

            if option_changed and option_items:
                await question_option_dao.replace_by_items(
                    db,
                    question_id=qid,
                    items=option_items,
                    option_content_crud=option_content_dao,
                )
                stats.option_question_updated += 1

        await db.flush()
        print(
            "[BANK_PROGRESS]"
            f" code={target.bank_code}"
            f" chunk={chunk_index}/{len(chunks)}"
            f" q_updated={stats.question_updated}"
            f" a_updated={stats.analysis_updated}"
            f" option_q_updated={stats.option_question_updated}"
            f" uploaded={mirror.stats.uploaded_images}"
            f" cache_hit={mirror.stats.cache_hit}"
            f" failed={mirror.stats.failed_images}"
            f" public={mirror.stats.public_urls}"
            f" signed={mirror.stats.signed_urls}"
            f" unknown={mirror.stats.unknown_urls}"
        )

    material_rows = (
        await db.execute(
            select(QuestionMaterial).where(
                QuestionMaterial.bank_id == target.bank_id,
                QuestionMaterial.is_active.is_(True),
            )
        )
    ).scalars().all()
    stats.material_total = len(material_rows)

    for index, material in enumerate(material_rows, start=1):
        content, changed = await mirror_html_text(
            mirror=mirror,
            html=material.content,
            bank_code=target.bank_code,
            field_name="material_content",
            scope_segment=f"material_{material.id}",
        )
        if changed:
            material.content = content
            stats.material_updated += 1
        if index % 20 == 0 or index == len(material_rows):
            print(
                "[BANK_MATERIAL]"
                f" code={target.bank_code}"
                f" done={index}/{len(material_rows)}"
                f" updated={stats.material_updated}"
            )

    await db.flush()
    if args.dry_run:
        await db.rollback()
        print(f"[BANK] rollback code={target.bank_code}")
    else:
        await db.commit()
        print(f"[BANK] commit code={target.bank_code}")
    return stats


async def run() -> int:
    """Program entry."""
    targets = await choose_bank_targets()
    if not targets:
        return 0

    dry_run = ask_yes_no("是否 DryRun（仅演练不提交）", True)
    max_questions = ask_int("每个题库最多处理题目数（0=不限）", 0)
    batch_size = ask_int("题目处理批次大小（建议 20-100）", 50)
    timeout_raw = ask("图片下载超时秒数", "20")
    try:
        timeout_seconds = float(timeout_raw)
    except ValueError:
        timeout_seconds = 20.0
    safe_interval_raw = ask("图片请求安全间隔秒数（建议 2-5）", "2.5")
    try:
        safe_interval_seconds = float(safe_interval_raw)
    except ValueError:
        safe_interval_seconds = 2.5
    sample_limit = ask_int("输出前后 URL 对照样本条数（0=不输出）", 5)

    run_args = SimpleNamespace(
        dry_run=dry_run,
        max_questions=max(0, max_questions),
        batch_size=max(1, batch_size),
    )

    mirror = QbankImageMirror(
        cache_file=PROJECT_ROOT / "backend" / "scripts" / "cache" / "qbank_image_cache.json",
        request_timeout=max(5.0, timeout_seconds),
        sample_limit=max(0, sample_limit),
        safe_interval_seconds=max(0.0, safe_interval_seconds),
        safe_interval_jitter_seconds=min(1.0, max(0.0, safe_interval_seconds * 0.2)),
    )

    async with async_db_session() as init_db:
        await mirror.initialize(init_db)

    total_stats = MirrorRunStats()
    for index, target in enumerate(targets, start=1):
        print(f"\n[RUN] {index}/{len(targets)} code={target.bank_code}")
        async with async_db_session() as db:
            bank_stats = await process_bank(db=db, mirror=mirror, target=target, args=run_args)
        total_stats.add(bank_stats)

    mirror.save_cache()
    print(
        "[DONE]"
        f" question={total_stats.question_updated}/{total_stats.question_total}"
        f" analysis={total_stats.analysis_updated}/{total_stats.analysis_total}"
        f" option_question={total_stats.option_question_updated}/{total_stats.option_question_total}"
        f" material={total_stats.material_updated}/{total_stats.material_total}"
        f" uploaded={mirror.stats.uploaded_images}"
        f" cache_hit={mirror.stats.cache_hit}"
        f" failed={mirror.stats.failed_images}"
        f" public={mirror.stats.public_urls}"
        f" signed={mirror.stats.signed_urls}"
        f" unknown={mirror.stats.unknown_urls}"
        f" dry_run={dry_run}"
    )
    if mirror.rewrite_samples:
        print(f"[MIRROR_SAMPLE] count={len(mirror.rewrite_samples)}")
        for index, sample in enumerate(mirror.rewrite_samples, start=1):
            print(
                "[MIRROR_SAMPLE]"
                f" #{index}"
                f" field={sample.field_name}"
                f" scope={sample.scope_segment}"
                f" cache={'Y' if sample.from_cache else 'N'}"
            )
            print(f"[MIRROR_SAMPLE]   before={sample.source_url}")
            print(f"[MIRROR_SAMPLE]   after ={sample.mirrored_url}")
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    raise SystemExit(asyncio.run(run()))
