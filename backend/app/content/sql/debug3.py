#!/usr/bin/env python3
import re
filepath = 'D:/100_Work/101_Program/Proj/fba/backend/app/content/sql/kp_xc_analogy_extension_inclusive.sql'
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()
match = re.search(r'CAST\(\$\$(.*?)\$\$ AS jsonb\)', content, re.DOTALL)
json_str = match.group(1).strip()

# Find all }}] patterns
positions = [m.start() for m in re.finditer(r'\}\}\]', json_str)]
print(f"Found {len(positions)} }}] patterns")
for pos in positions:
    print(f"  pos {pos}: ...{json_str[max(0,pos-10):pos+10]}...")

# Try replacing each one
for pos in positions:
    attempt = json_str[:pos] + '}]}' + json_str[pos+3:]
    try:
        import json
        json.loads(attempt)
        print(f"\nSUCCESS: replacing at pos {pos}")
        break
    except json.JSONDecodeError as e:
        print(f"  pos {pos} -> error at {e.pos}: {e.msg}")
