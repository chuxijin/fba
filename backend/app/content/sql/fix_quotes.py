#!/usr/bin/env python3
"""Fix Chinese quotes inside double-quoted strings"""
import re

filepath = "D:/100_Work/101_Program/Proj/fba/backend/app/content/sql/fill_l6_part2.py"

with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

lines = content.split('\n')
fixed = 0

for i, line in enumerate(lines):
    stripped = line.strip()
    # Check if line has Chinese quotes (U+201C and U+201D) inside double-quoted Python string
    if '“' in stripped or '”' in stripped:
        # Check if the line uses double quotes as outer delimiter
        # Simple heuristic: if the line starts with spaces + double quote
        if re.match(r'^\s+"', line):
            # Replace outer double quotes with single quotes
            first = line.index('"')
            last = line.rindex('"')
            if first != last and first < last:
                line = line[:first] + "'" + line[first+1:last] + "'" + line[last+1:]
                lines[i] = line
                fixed += 1

with open(filepath, 'w', encoding='utf-8') as f:
    f.write('\n'.join(lines))

print(f"Fixed {fixed} lines")
