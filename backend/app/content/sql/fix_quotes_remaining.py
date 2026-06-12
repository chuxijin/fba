#!/usr/bin/env python3
"""Fix double quotes inside double-quoted strings in fill_remaining.py"""
import re

filepath = "D:/100_Work/101_Program/Proj/fba/backend/app/content/sql/fill_remaining.py"

with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

lines = content.split('\n')
fixed = 0

for i, line in enumerate(lines):
    stripped = line.strip()
    if not stripped or not stripped.startswith('"'):
        continue
    quote_count = stripped.count('"')
    if quote_count <= 2:
        continue
    first = line.index('"')
    last = line.rindex('"')
    if first < last:
        new_line = line[:first] + "'" + line[first+1:last] + "'" + line[last+1:]
        lines[i] = new_line
        fixed += 1

with open(filepath, 'w', encoding='utf-8') as f:
    f.write('\n'.join(lines))

print(f"Fixed {fixed} lines")
