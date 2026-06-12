#!/usr/bin/env python3
"""Fix remaining Chinese quote issues in fill_remaining.py"""

filepath = "D:/100_Work/101_Program/Proj/fba/backend/app/content/sql/fill_remaining.py"

with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

lines = content.split('\n')
fixed = 0

for i, line in enumerate(lines):
    stripped = line.strip()
    if not stripped:
        continue
    # Skip lines that are not string literals
    if not stripped.startswith('"') and not stripped.startswith("'"):
        continue
    # Skip lines that start with single quote (already fixed)
    if stripped.startswith("'"):
        continue
    # Check if line has inner double quotes
    quote_count = stripped.count('"')
    if quote_count <= 2:
        continue
    # Skip the docstring line
    if stripped.startswith('"""'):
        continue
    # Skip f-string lines
    if 'f"""' in stripped:
        continue
    # This line has inner double quotes - change outer to single quotes
    first = line.index('"')
    last = line.rindex('"')
    if first < last:
        new_line = line[:first] + "'" + line[first+1:last] + "'" + line[last+1:]
        lines[i] = new_line
        fixed += 1

with open(filepath, 'w', encoding='utf-8') as f:
    f.write('\n'.join(lines))

print(f"Fixed {fixed} lines")
