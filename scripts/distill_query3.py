#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Phase 3: Examine specific repeated workflow details."""
import sqlite3
import json
from datetime import datetime, timedelta

DB_PATH = r"C:\Users\19396\.local\share\mimocode\mimocode.db"
THIRTY_DAYS_AGO = datetime.now() - timedelta(days=30)
CUTOFF_MS = int(THIRTY_DAYS_AGO.timestamp() * 1000)

conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

# 1. The grade_one workflow - look at what commands were run around it
print("=== GRADE_ONE WORKFLOW DETAILS ===")
cur.execute("""
    SELECT json_extract(p.data, '$.state.input') as inp,
           json_extract(p.data, '$.state.output') as outp
    FROM message m
    JOIN part p ON p.message_id = m.id
    WHERE json_extract(m.data, '$.role') = 'assistant'
      AND json_extract(p.data, '$.type') = 'tool'
      AND json_extract(p.data, '$.tool') = 'Bash'
      AND json_extract(p.data, '$.state.input') LIKE '%grade_one%'
      AND m.time_created > ?
    ORDER BY m.time_created
    LIMIT 10
""", (CUTOFF_MS,))
for i, r in enumerate(cur.fetchall()):
    inp = json.loads(r['inp']) if r['inp'] else {}
    cmd = inp.get('command', '')[:250]
    print(f"  [{i+1}] {cmd}")

# 2. The SSH deploy workflow - git pull patterns
print("\n=== SSH DEPLOY (git pull) PATTERNS ===")
cur.execute("""
    SELECT json_extract(p.data, '$.state.input') as inp
    FROM message m
    JOIN part p ON p.message_id = m.id
    WHERE json_extract(m.data, '$.role') = 'assistant'
      AND json_extract(p.data, '$.type') = 'tool'
      AND json_extract(p.data, '$.tool') LIKE 'mcp__ssh-mcp%'
      AND m.time_created > ?
    ORDER BY m.time_created
    LIMIT 20
""", (CUTOFF_MS,))
for i, r in enumerate(cur.fetchall()):
    inp = json.loads(r['inp']) if r['inp'] else {}
    cmd = inp.get('cmdString', '')[:200]
    print(f"  [{i+1}] {cmd}")

# 3. The pytest patterns - what tests are run
print("\n=== PYTEST PATTERNS ===")
cur.execute("""
    SELECT json_extract(p.data, '$.state.input') as inp,
           json_extract(p.data, '$.state.output') as outp
    FROM message m
    JOIN part p ON p.message_id = m.id
    WHERE json_extract(m.data, '$.role') = 'assistant'
      AND json_extract(p.data, '$.type') = 'tool'
      AND json_extract(p.data, '$.tool') = 'Bash'
      AND json_extract(p.data, '$.state.input') LIKE '%pytest%'
      AND m.time_created > ?
    ORDER BY m.time_created
    LIMIT 15
""", (CUTOFF_MS,))
for i, r in enumerate(cur.fetchall()):
    inp = json.loads(r['inp']) if r['inp'] else {}
    cmd = inp.get('command', '')[:250]
    print(f"  [{i+1}] {cmd}")

# 4. Module scaffolding patterns (touch/init.py)
print("\n=== MODULE SCAFFOLDING PATTERNS ===")
cur.execute("""
    SELECT json_extract(p.data, '$.state.input') as inp
    FROM message m
    JOIN part p ON p.message_id = m.id
    WHERE json_extract(m.data, '$.role') = 'assistant'
      AND json_extract(p.data, '$.type') = 'tool'
      AND json_extract(p.data, '$.tool') = 'Bash'
      AND json_extract(p.data, '$.state.input') LIKE '%touch%__init__%'
      AND m.time_created > ?
    ORDER BY m.time_created
    LIMIT 10
""", (CUTOFF_MS,))
for i, r in enumerate(cur.fetchall()):
    inp = json.loads(r['inp']) if r['inp'] else {}
    cmd = inp.get('command', '')[:300]
    print(f"  [{i+1}] {cmd}")

# 5. MCP fba list_tables + describe_table patterns
print("\n=== DB SCHEMA EXPLORATION PATTERNS ===")
cur.execute("""
    SELECT json_extract(p.data, '$.tool') as tool,
           json_extract(p.data, '$.state.input') as inp,
           json_extract(p.data, '$.state.output') as outp,
           m.time_created
    FROM message m
    JOIN part p ON p.message_id = m.id
    WHERE json_extract(m.data, '$.role') = 'assistant'
      AND json_extract(p.data, '$.type') = 'tool'
      AND json_extract(p.data, '$.tool') LIKE 'mcp__fba__%'
      AND m.time_created > ?
    ORDER BY m.time_created
    LIMIT 20
""", (CUTOFF_MS,))
for i, r in enumerate(cur.fetchall()):
    inp = json.loads(r['inp']) if r['inp'] else {}
    outp_preview = (r['outp'] or '')[:100]
    print(f"  [{i+1}] {r['tool']} | inp={json.dumps(inp)[:100]} | out={outp_preview}")

# 6. git status + git log patterns (pre-deploy check?)
print("\n=== GIT STATUS/LOG PATTERNS ===")
cur.execute("""
    SELECT json_extract(p.data, '$.state.input') as inp
    FROM message m
    JOIN part p ON p.message_id = m.id
    WHERE json_extract(m.data, '$.role') = 'assistant'
      AND json_extract(p.data, '$.type') = 'tool'
      AND json_extract(p.data, '$.tool') = 'Bash'
      AND (json_extract(p.data, '$.state.input') LIKE '%git status%'
           OR json_extract(p.data, '$.state.input') LIKE '%git log%')
      AND m.time_created > ?
    ORDER BY m.time_created
    LIMIT 20
""", (CUTOFF_MS,))
for i, r in enumerate(cur.fetchall()):
    inp = json.loads(r['inp']) if r['inp'] else {}
    cmd = inp.get('command', '')[:200]
    print(f"  [{i+1}] {cmd}")

conn.close()
