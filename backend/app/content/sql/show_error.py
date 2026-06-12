#!/usr/bin/env python3
import re
filepath = 'D:/100_Work/101_Program/Proj/fba/backend/app/content/sql/kp_xc_analogy_extension_inclusive.sql'
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()
match = re.search(r'CAST\(\$\$(.*?)\$\$ AS jsonb\)', content, re.DOTALL)
json_str = match.group(1).strip()
start = 1400
end = 1600
print(f'Position {start}-{end}:')
print(repr(json_str[start:end]))
