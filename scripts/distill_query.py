#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Distill pass: read-only queries against mimocode.db for workflow pattern discovery."""
import sqlite3
import json
import sys
from datetime import datetime, timedelta

DB_PATH = r"C:\Users\19396\.local\share\mimocode\mimocode.db"
THIRTY_DAYS_AGO = datetime.now() - timedelta(days=30)
CUTOFF_MS = int(THIRTY_DAYS_AGO.timestamp() * 1000)

conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

# 1. List tables
cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [r['name'] for r in cur.fetchall()]
print("=== TABLES ===")
print(", ".join(tables))

# 2. List recent sessions (last 30 days)
print("\n=== RECENT SESSIONS ===")
try:
    cur.execute("""
        SELECT id, title, time_created, directory
        FROM session
        WHERE time_created > ?
        ORDER BY time_created DESC
        LIMIT 30
    """, (CUTOFF_MS,))
    for r in cur.fetchall():
        ts = datetime.fromtimestamp(r['time_created'] / 1000).isoformat() if r['time_created'] else '?'
        print(f"  [{r['id']}] {ts} | {r['title'][:80] if r['title'] else '(no title)'} | {r['directory']}")
except Exception as e:
    print(f"  Error: {e}")

# 3. Tool usage frequency (last 30 days)
print("\n=== TOOL USAGE FREQUENCY (last 30d) ===")
try:
    cur.execute("""
        SELECT json_extract(p.data, '$.tool') as tool,
               substr(json_extract(p.data, '$.state.input'), 1, 150) as input_preview,
               count(*) as n
        FROM message m
        JOIN part p ON p.message_id = m.id
        WHERE json_extract(m.data, '$.role') = 'assistant'
          AND json_extract(p.data, '$.type') = 'tool'
          AND m.time_created > ?
        GROUP BY tool, input_preview
        ORDER BY n DESC
        LIMIT 50
    """, (CUTOFF_MS,))
    for r in cur.fetchall():
        print(f"  {r['n']:3d}x | {r['tool']:<20s} | {r['input_preview'][:120] if r['input_preview'] else ''}")
except Exception as e:
    print(f"  Error: {e}")

# 4. Repeated keywords in user messages
print("\n=== USER MESSAGE KEYWORD PATTERNS ===")
try:
    keywords = ["again", "every time", "like last time", "same as before", "repeat", "the usual",
                "再", "每次", "重复", "一样的", "上次", "老问题"]
    for kw in keywords:
        cur.execute("""
            SELECT count(*) as n
            FROM message m
            WHERE json_extract(m.data, '$.role') = 'user'
              AND m.time_created > ?
              AND json_extract(m.data, '$.content') LIKE ?
        """, (CUTOFF_MS, f'%{kw}%'))
        n = cur.fetchone()['n']
        if n > 0:
            print(f"  '{kw}': {n} occurrences")
except Exception as e:
    print(f"  Error: {e}")

# 5. Repeated file paths in tool calls
print("\n=== REPEATED FILE PATHS IN TOOL CALLS ===")
try:
    cur.execute("""
        SELECT json_extract(p.data, '$.state.input') as inp,
               count(*) as n
        FROM message m
        JOIN part p ON p.message_id = m.id
        WHERE json_extract(m.data, '$.role') = 'assistant'
          AND json_extract(p.data, '$.type') = 'tool'
          AND m.time_created > ?
        GROUP BY inp
        HAVING n >= 3
        ORDER BY n DESC
        LIMIT 20
    """, (CUTOFF_MS,))
    for r in cur.fetchall():
        preview = (r['inp'] or '')[:150]
        print(f"  {r['n']:3d}x | {preview}")
except Exception as e:
    print(f"  Error: {e}")

# 6. Subagent usage
print("\n=== SUBAGENT / ACTOR USAGE ===")
try:
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '%actor%'")
    actor_tables = [r['name'] for r in cur.fetchall()]
    print(f"  Actor-related tables: {actor_tables}")
    if 'actor_registry' in tables:
        cur.execute("SELECT * FROM actor_registry ORDER BY rowid DESC LIMIT 20")
        for r in cur.fetchall():
            print(f"  {dict(r)}")
except Exception as e:
    print(f"  Error: {e}")

conn.close()
