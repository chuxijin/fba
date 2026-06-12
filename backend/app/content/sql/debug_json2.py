#!/usr/bin/env python3
"""Debug JSON structure - find columns nodes"""
import re, json

filepath = "D:/100_Work/101_Program/Proj/fba/backend/app/content/sql/kp_xc_analogy_extension_inclusive.sql"
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

match = re.search(r'CAST\(\$\$(.*?)\$\$ AS jsonb\)', content, re.DOTALL)
json_str = match.group(1).strip()

# Find all columns nodes
columns_pattern = r'"type":"columns"'
for m in re.finditer(columns_pattern, json_str):
    pos = m.start()
    # Find the start of this object (go back to find {)
    start = pos
    while start > 0 and json_str[start] != '{':
        start -= 1
    # Find the end (match brackets)
    depth = 0
    end = start
    for i in range(start, len(json_str)):
        if json_str[i] == '{':
            depth += 1
        elif json_str[i] == '}':
            depth -= 1
            if depth == 0:
                end = i + 1
                break
    columns_json = json_str[start:end]
    print(f"Columns node at pos {start}-{end}:")
    print(f"  Length: {len(columns_json)}")
    print(f"  Last 100 chars: {columns_json[-100:]}")
    try:
        json.loads(columns_json)
        print(f"  Status: VALID")
    except json.JSONDecodeError as e:
        print(f"  Status: ERROR at {e.pos}: {e.msg}")
        print(f"  Error context: {columns_json[max(0,e.pos-20):e.pos+20]}")
