#!/usr/bin/env python3
import re, json, sys, glob

sql_dir = "D:/100_Work/101_Program/Proj/fba/backend/app/content/sql"
files = sorted(glob.glob(f"{sql_dir}/kp_xc_*.sql"))

errors = []
for filepath in files:
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    match = re.search(r'CAST\(\$\$(.*?)\$\$ AS jsonb\)', content, re.DOTALL)
    if match:
        json_str = match.group(1).strip()
        try:
            json.loads(json_str)
        except json.JSONDecodeError as e:
            fname = filepath.split('/')[-1]
            errors.append((fname, e.pos, e.msg, json_str[max(0,e.pos-30):e.pos+30]))

print(f"Total files: {len(files)}")
print(f"JSON errors: {len(errors)}")
for fname, pos, msg, ctx in errors[:5]:
    print(f"\n{fname}: pos {pos} - {msg}")
    print(f"  Context: {ctx}")
