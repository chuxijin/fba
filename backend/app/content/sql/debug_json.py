#!/usr/bin/env python3
"""Debug JSON structure in failing files"""
import re, json

filepath = "D:/100_Work/101_Program/Proj/fba/backend/app/content/sql/kp_xc_analogy_extension_inclusive.sql"
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

match = re.search(r'CAST\(\$\$(.*?)\$\$ AS jsonb\)', content, re.DOTALL)
json_str = match.group(1).strip()

try:
    json.loads(json_str)
    print("JSON is valid!")
except json.JSONDecodeError as e:
    print(f"Error at pos {e.pos}: {e.msg}")
    print(f"\nContext around error (100 chars before, 100 after):")
    start = max(0, e.pos - 100)
    end = min(len(json_str), e.pos + 100)
    print(f"Before: {json_str[start:e.pos]}")
    print(f"Error char: '{json_str[e.pos]}' at pos {e.pos}")
    print(f"After: {json_str[e.pos+1:end]}")

    # Try to find the columns structure
    print(f"\nLooking for columns patterns:")
    # Find all }}] patterns
    for m in re.finditer(r'\}\}\]', json_str):
        pos = m.start()
        print(f"  }}] at pos {pos}: ...{json_str[max(0,pos-20):pos+10]}...")
