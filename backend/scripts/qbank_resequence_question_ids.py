#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio
import os

from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import URL
from sqlalchemy import text as sa_text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine


@dataclass
class QuestionFkRef:
    """FK reference to study_question.id."""

    conname: str
    table_schema: str
    table_name: str
    column_name: str
    is_deferrable: bool
    is_initially_deferred: bool

    @property
    def full_table_name(self) -> str:
        """Return quoted full table name."""
        return f'{quote_ident(self.table_schema)}.{quote_ident(self.table_name)}'


@dataclass
class QuestionStats:
    """Question table stats."""

    total: int
    min_id: int | None
    max_id: int | None


def quote_ident(value: str) -> str:
    """
    Quote SQL identifier safely.

    :param value: raw identifier
    :return:
    """
    safe = str(value).replace('"', '""')
    return f'"{safe}"'


def ask_yes_no(prompt: str, default_yes: bool) -> bool:
    """
    Read yes/no input.

    :param prompt: prompt text
    :param default_yes: default value
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
        print("Please input y or n.")


def parse_dotenv(path: Path) -> dict[str, str]:
    """
    Parse a simple dotenv file.

    :param path: dotenv path
    :return:
    """
    result: dict[str, str] = {}
    if not path.exists():
        return result

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].strip()
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key:
            continue
        if value and len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        result[key] = value
    return result


_SESSION_FACTORY: async_sessionmaker[AsyncSession] | None = None


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """
    Build async DB session factory from env and backend/.env.

    :return:
    """
    global _SESSION_FACTORY
    if _SESSION_FACTORY is not None:
        return _SESSION_FACTORY

    dotenv = parse_dotenv(Path("backend/.env"))

    def env_value(name: str, default: str = "") -> str:
        value = os.getenv(name)
        if value is not None and value != "":
            return value
        return dotenv.get(name, default)

    db_type = env_value("DATABASE_TYPE", "postgresql").strip().lower()
    if db_type != "postgresql":
        raise RuntimeError("This resequence script only supports PostgreSQL.")

    db_host = env_value("DATABASE_HOST")
    db_port = int(env_value("DATABASE_PORT", "5432"))
    db_user = env_value("DATABASE_USER")
    db_password = env_value("DATABASE_PASSWORD")
    db_name = env_value("DATABASE_SCHEMA", "fba")

    if not db_host or not db_user:
        raise RuntimeError("Missing DATABASE_HOST / DATABASE_USER in env.")

    db_url = URL.create(
        drivername="postgresql+asyncpg",
        username=db_user,
        password=db_password,
        host=db_host,
        port=db_port,
        database=db_name,
    )
    engine = create_async_engine(
        db_url,
        future=True,
        pool_size=5,
        max_overflow=10,
        pool_pre_ping=True,
    )
    _SESSION_FACTORY = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        autoflush=False,
        expire_on_commit=False,
    )
    return _SESSION_FACTORY


async def fetch_question_stats(db: AsyncSession) -> QuestionStats:
    """
    Fetch basic stats from study_question.

    :param db: db session
    :return:
    """
    row = (
        await db.execute(
            sa_text(
                """
                SELECT
                    COUNT(*)::BIGINT AS total,
                    MIN(id)::BIGINT AS min_id,
                    MAX(id)::BIGINT AS max_id
                FROM study_question
                """
            )
        )
    ).mappings().first()
    return QuestionStats(
        total=int(row["total"]),
        min_id=int(row["min_id"]) if row["min_id"] is not None else None,
        max_id=int(row["max_id"]) if row["max_id"] is not None else None,
    )


async def fetch_fk_refs(db: AsyncSession) -> list[QuestionFkRef]:
    """
    Fetch all FK columns referencing study_question.id.

    :param db: db session
    :return:
    """
    rows = (
        await db.execute(
            sa_text(
                """
                WITH fk AS (
                    SELECT
                        c.conname,
                        ns.nspname AS table_schema,
                        cls.relname AS table_name,
                        att.attname AS column_name,
                        c.condeferrable,
                        c.condeferred,
                        rns.nspname AS ref_schema,
                        rcls.relname AS ref_table,
                        ratt.attname AS ref_column,
                        ord.n
                    FROM pg_constraint c
                    JOIN pg_class cls ON cls.oid = c.conrelid
                    JOIN pg_namespace ns ON ns.oid = cls.relnamespace
                    JOIN pg_class rcls ON rcls.oid = c.confrelid
                    JOIN pg_namespace rns ON rns.oid = rcls.relnamespace
                    JOIN unnest(c.conkey) WITH ORDINALITY AS ord(attnum, n) ON true
                    JOIN unnest(c.confkey) WITH ORDINALITY AS rord(attnum, n) ON rord.n = ord.n
                    JOIN pg_attribute att ON att.attrelid = c.conrelid AND att.attnum = ord.attnum
                    JOIN pg_attribute ratt ON ratt.attrelid = c.confrelid AND ratt.attnum = rord.attnum
                    WHERE c.contype = 'f'
                )
                SELECT
                    conname,
                    table_schema,
                    table_name,
                    column_name,
                    condeferrable,
                    condeferred
                FROM fk
                WHERE ref_table = 'study_question'
                  AND ref_column = 'id'
                ORDER BY table_schema, table_name, conname
                """
            )
        )
    ).mappings().all()
    return [
        QuestionFkRef(
            conname=str(row["conname"]),
            table_schema=str(row["table_schema"]),
            table_name=str(row["table_name"]),
            column_name=str(row["column_name"]),
            is_deferrable=bool(row["condeferrable"]),
            is_initially_deferred=bool(row["condeferred"]),
        )
        for row in rows
    ]


async def build_mapping_table(db: AsyncSession) -> int:
    """
    Build temporary mapping table old_id -> new_id -> temp_id.

    :param db: db session
    :return:
    """
    await db.execute(
        sa_text(
            """
            CREATE TEMP TABLE tmp_question_id_map (
                old_id BIGINT PRIMARY KEY,
                new_id BIGINT NOT NULL UNIQUE,
                temp_id BIGINT NOT NULL UNIQUE
            ) ON COMMIT DROP
            """
        )
    )
    await db.execute(
        sa_text(
            """
            INSERT INTO tmp_question_id_map (old_id, new_id, temp_id)
            SELECT
                id AS old_id,
                ROW_NUMBER() OVER (ORDER BY created_time NULLS FIRST, id)::BIGINT AS new_id,
                -ROW_NUMBER() OVER (ORDER BY created_time NULLS FIRST, id)::BIGINT AS temp_id
            FROM study_question
            ORDER BY created_time NULLS FIRST, id
            """
        )
    )
    mapped = await db.scalar(sa_text("SELECT COUNT(*)::BIGINT FROM tmp_question_id_map"))
    return int(mapped or 0)


async def lock_related_tables(db: AsyncSession, refs: list[QuestionFkRef]) -> None:
    """
    Lock study_question and all FK child tables.

    :param db: db session
    :param refs: fk refs
    :return:
    """
    table_names = {"study_question"}
    for ref in refs:
        table_names.add(f"{ref.table_schema}.{ref.table_name}")

    lock_targets: list[str] = []
    for full in sorted(table_names):
        if "." in full:
            schema, table = full.split(".", 1)
            lock_targets.append(f"{quote_ident(schema)}.{quote_ident(table)}")
            continue
        lock_targets.append(quote_ident(full))

    lock_sql = f"LOCK TABLE {', '.join(lock_targets)} IN ACCESS EXCLUSIVE MODE"
    await db.execute(sa_text(lock_sql))


async def switch_constraints_to_deferred_mode(db: AsyncSession, refs: list[QuestionFkRef]) -> None:
    """
    Temporarily make FK constraints deferrable and deferred in current txn.

    :param db: db session
    :param refs: fk refs
    :return:
    """
    changed = 0
    for ref in refs:
        if ref.is_deferrable and ref.is_initially_deferred:
            continue
        sql = (
            f"ALTER TABLE {ref.full_table_name} "
            f"ALTER CONSTRAINT {quote_ident(ref.conname)} DEFERRABLE INITIALLY DEFERRED"
        )
        await db.execute(sa_text(sql))
        changed += 1
    await db.execute(sa_text("SET CONSTRAINTS ALL DEFERRED"))
    print(f"[RESEQUENCE] constraints_deferred changed={changed}")


async def restore_constraint_modes(db: AsyncSession, refs: list[QuestionFkRef]) -> None:
    """
    Restore FK constraints to their original deferrable mode.

    :param db: db session
    :param refs: fk refs
    :return:
    """
    restored = 0
    for ref in refs:
        if ref.is_deferrable:
            mode = "DEFERRABLE INITIALLY DEFERRED" if ref.is_initially_deferred else "DEFERRABLE INITIALLY IMMEDIATE"
        else:
            mode = "NOT DEFERRABLE"
        sql = f"ALTER TABLE {ref.full_table_name} ALTER CONSTRAINT {quote_ident(ref.conname)} {mode}"
        await db.execute(sa_text(sql))
        restored += 1
    print(f"[RESEQUENCE] constraints_restored count={restored}")


async def restore_constraint_modes_post_commit(refs: list[QuestionFkRef]) -> None:
    """
    Restore FK constraint modes in a fresh transaction after data commit.

    :param refs: fk refs
    :return:
    """
    session_factory = get_session_factory()
    async with session_factory() as db:
        await db.execute(sa_text("SET lock_timeout = '0'"))
        await db.execute(sa_text("SET statement_timeout = '0'"))
        await lock_related_tables(db, refs)
        await restore_constraint_modes(db, refs)
        await db.commit()
    print("[RESEQUENCE] constraints restored in post-commit transaction")


async def update_fk_columns(
    db: AsyncSession,
    refs: list[QuestionFkRef],
    source_col: str,
    target_col: str,
    phase_name: str,
) -> None:
    """
    Rewrite FK columns by mapping table.

    :param db: db session
    :param refs: fk refs
    :param source_col: source mapping column
    :param target_col: target mapping column
    :param phase_name: phase label
    :return:
    """
    total = 0
    for ref in refs:
        column_identifier = quote_ident(ref.column_name)
        source_identifier = quote_ident(source_col)
        target_identifier = quote_ident(target_col)
        sql = (
            f"UPDATE {ref.full_table_name} t "  # nosec B608
            f"SET {column_identifier} = m.{target_identifier} "
            f"FROM tmp_question_id_map m "
            f"WHERE t.{column_identifier} = m.{source_identifier}"
        )
        result = await db.execute(sa_text(sql))
        affected = int(result.rowcount or 0)
        total += affected
    print(f"[RESEQUENCE] {phase_name} fk_rows={total}")


async def validate_fk_integrity(db: AsyncSession, refs: list[QuestionFkRef]) -> None:
    """
    Validate all FK columns have matching question rows.

    :param db: db session
    :param refs: fk refs
    :return:
    """
    for ref in refs:
        column_identifier = quote_ident(ref.column_name)
        sql = (
            f"SELECT COUNT(*)::BIGINT AS c "  # nosec B608
            f"FROM {ref.full_table_name} t "
            f"LEFT JOIN study_question q ON q.id = t.{column_identifier} "
            f"WHERE t.{column_identifier} IS NOT NULL "
            f"AND q.id IS NULL"
        )
        count = await db.scalar(sa_text(sql))
        missing = int(count or 0)
        if missing > 0:
            raise RuntimeError(
                f"FK broken after resequence: {ref.table_schema}.{ref.table_name}.{ref.column_name} missing={missing}"
            )


async def validate_question_span(db: AsyncSession) -> None:
    """
    Validate study_question id span is exactly 1..N.

    :param db: db session
    :return:
    """
    stats = await fetch_question_stats(db)
    if stats.total == 0:
        return
    if stats.min_id != 1 or stats.max_id != stats.total:
        raise RuntimeError(
            f"Question id span invalid after resequence: total={stats.total} min={stats.min_id} max={stats.max_id}"
        )


async def reset_question_sequence(db: AsyncSession) -> None:
    """
    Reset question id sequence to current max id.

    :param db: db session
    :return:
    """
    await db.execute(
        sa_text(
            """
            SELECT setval(
                pg_get_serial_sequence('study_question', 'id'),
                GREATEST((SELECT COALESCE(MAX(id), 1) FROM study_question), 1),
                true
            )
            """
        )
    )


async def resequence_question_ids(commit: bool) -> None:
    """
    Execute resequence workflow.

    :param commit: commit transaction if true
    :return:
    """
    session_factory = get_session_factory()
    async with session_factory() as db:
        before = await fetch_question_stats(db)
        refs = await fetch_fk_refs(db)
        print(
            "[RESEQUENCE] before"
            f" total={before.total}"
            f" min_id={before.min_id}"
            f" max_id={before.max_id}"
            f" fk_refs={len(refs)}"
        )
        if before.total == 0:
            print("[RESEQUENCE] study_question is empty, nothing to do.")
            return

        await db.execute(sa_text("SET lock_timeout = '0'"))
        await db.execute(sa_text("SET statement_timeout = '0'"))
        await lock_related_tables(db, refs)
        print("[RESEQUENCE] lock acquired")

        mapped = await build_mapping_table(db)
        print(f"[RESEQUENCE] mapping built rows={mapped}")
        await switch_constraints_to_deferred_mode(db, refs)

        await update_fk_columns(db, refs, source_col="old_id", target_col="temp_id", phase_name="phase1_to_temp")
        result_question_temp = await db.execute(
            sa_text(
                """
                UPDATE study_question q
                SET id = m.temp_id
                FROM tmp_question_id_map m
                WHERE q.id = m.old_id
                """
            )
        )
        print(f"[RESEQUENCE] phase1_to_temp question_rows={int(result_question_temp.rowcount or 0)}")

        await update_fk_columns(db, refs, source_col="temp_id", target_col="new_id", phase_name="phase2_to_new")
        result_question_new = await db.execute(
            sa_text(
                """
                UPDATE study_question q
                SET id = m.new_id
                FROM tmp_question_id_map m
                WHERE q.id = m.temp_id
                """
            )
        )
        print(f"[RESEQUENCE] phase2_to_new question_rows={int(result_question_new.rowcount or 0)}")

        await reset_question_sequence(db)
        await validate_question_span(db)
        await validate_fk_integrity(db, refs)

        after = await fetch_question_stats(db)
        print(
            "[RESEQUENCE] after"
            f" total={after.total}"
            f" min_id={after.min_id}"
            f" max_id={after.max_id}"
        )

        if commit:
            await db.commit()
            print("[RESEQUENCE] COMMIT done")
            await restore_constraint_modes_post_commit(refs)
        else:
            await db.rollback()
            print("[RESEQUENCE] ROLLBACK done (dry-run)")


async def main() -> None:
    """Interactive entrypoint."""
    print("WARNING: this will rewrite primary keys of study_question and all FK references.")
    print("Please make sure all write traffic is stopped and backup is taken.")
    if not ask_yes_no("Continue", False):
        print("Cancelled.")
        return

    dry_run = ask_yes_no("Run in dry-run mode", True)
    commit = not dry_run
    if commit:
        if not ask_yes_no("Final confirm COMMIT", False):
            print("Cancelled.")
            return

    await resequence_question_ids(commit=commit)


if __name__ == "__main__":
    asyncio.run(main())
