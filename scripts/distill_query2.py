#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Phase 2: Deeper analysis of repeated workflows."""
import sqlite3
import json
from datetime import datetime, timedelta

DB_PATH = r"C:\Users\19396\.local\share\mimocode\mimocode.db"
THIRTY_DAYS_AGO = datetime.now() - timedelta(days=30)
CUTOFF_MS = int(THIRTY_DAYS_AGO.timestamp() * 1000)

conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

# 1. Detailed bash command patterns
print("=== BASH COMMAND PATTERNS (deduplicated) ===")
cur.execute("""
    SELECT json_extract(p.data, '$.state.input') as inp,
           count(*) as n
    FROM message m
    JOIN part p ON p.message_id = m.id
    WHERE json_extract(m.data, '$.role') = 'assistant'
      AND json_extract(p.data, '$.type') = 'tool'
      AND json_extract(p.data, '$.tool') = 'Bash'
      AND m.time_created > ?
    GROUP BY inp
    ORDER BY n DESC
    LIMIT 30
""", (CUTOFF_MS,))
for r in cur.fetchall():
    inp = json.loads(r['inp']) if r['inp'] else {}
    cmd = inp.get('command', '')[:200]
    print(f"  {r['n']:3d}x | {cmd}")

# 2. MCP query patterns
print("\n=== MCP QUERY PATTERNS ===")
cur.execute("""
    SELECT json_extract(p.data, '$.tool') as tool,
           json_extract(p.data, '$.state.input') as inp,
           count(*) as n
    FROM message m
    JOIN part p ON p.message_id = m.id
    WHERE json_extract(m.data, '$.role') = 'assistant'
      AND json_extract(p.data, '$.type') = 'tool'
      AND json_extract(p.data, '$.tool') LIKE 'mcp__%'
      AND m.time_created > ?
    GROUP BY tool, inp
    ORDER BY n DESC
    LIMIT 20
""", (CUTOFF_MS,))
for r in cur.fetchall():
    inp = json.loads(r['inp']) if r['inp'] else {}
    query = inp.get('query', '')[:150] if isinstance(inp, dict) else str(inp)[:150]
    print(f"  {r['n']:3d}x | {r['tool']} | {query}")

# 3. Edit target files
print("\n=== EDIT TARGET FILES ===")
cur.execute("""
    SELECT json_extract(p.data, '$.state.input') as inp,
           count(*) as n
    FROM message m
    JOIN part p ON p.message_id = m.id
    WHERE json_extract(m.data, '$.role') = 'assistant'
      AND json_extract(p.data, '$.type') = 'tool'
      AND json_extract(p.data, '$.tool') = 'Edit'
      AND m.time_created > ?
    GROUP BY inp
    ORDER BY n DESC
    LIMIT 20
""", (CUTOFF_MS,))
for r in cur.fetchall():
    inp = json.loads(r['inp']) if r['inp'] else {}
    fp = inp.get('file_path', '') if isinstance(inp, dict) else ''
    print(f"  {r['n']:3d}x | {fp}")

# 4. Read target files
print("\n=== READ TARGET FILES ===")
cur.execute("""
    SELECT json_extract(p.data, '$.state.input') as inp,
           count(*) as n
    FROM message m
    JOIN part p ON p.message_id = m.id
    WHERE json_extract(m.data, '$.role') = 'assistant'
      AND json_extract(p.data, '$.type') = 'tool'
      AND json_extract(p.data, '$.tool') = 'Read'
      AND m.time_created > ?
    GROUP BY inp
    ORDER BY n DESC
    LIMIT 20
""", (CUTOFF_MS,))
for r in cur.fetchall():
    inp = json.loads(r['inp']) if r['inp'] else {}
    fp = inp.get('file_path', '') if isinstance(inp, dict) else ''
    print(f"  {r['n']:3d}x | {fp}")

# 5. Session titles - look for repeated task types
print("\n=== SESSION TITLE THEMES ===")
cur.execute("""
    SELECT title, count(*) as n
    FROM session
    WHERE time_created > ?
    GROUP BY title
    HAVING n > 1
    ORDER BY n DESC
""", (CUTOFF_MS,))
for r in cur.fetchall():
    print(f"  {r['n']}x | {(r['title'] or '')[:100]}")

# 6. Repeated user messages
print("\n=== REPEATED USER MESSAGES ===")
cur.execute("""
    SELECT json_extract(m.data, '$.content') as content, count(*) as n
    FROM message m
    WHERE json_extract(m.data, '$.role') = 'user'
      AND m.time_created > ?
    GROUP BY content
    HAVING n > 1
    ORDER BY n DESC
    LIMIT 10
""", (CUTOFF_MS,))
for r in cur.fetchall():
    c = (r['content'] or '')[:120]
    print(f"  {r['n']}x | {c}")

conn.close()
