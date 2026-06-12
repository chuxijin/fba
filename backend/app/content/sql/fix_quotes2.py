#!/usr/bin/env python3
"""Fix double quotes inside double-quoted strings"""
import re

filepath = "D:/100_Work/101_Program/Proj/fba/backend/app/content/sql/fill_l6_part2.py"

with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

# Find all lines that have pattern: spaces + "text with "inner" quotes"
# These lines start with spaces followed by double quote and contain inner double quotes
# We need to change outer quotes to single quotes

lines = content.split('\n')
fixed = 0

for i, line in enumerate(lines):
    stripped = line.strip()

    # Skip lines that are clearly not string literals
    if not stripped:
        continue

    # Check if line starts with double quote (string literal)
    if not stripped.startswith('"'):
        continue

    # Check if there are inner double quotes (more than 2 double quotes total)
    quote_count = stripped.count('"')
    if quote_count <= 2:
        continue

    # This line has inner double quotes - change outer to single quotes
    # Find first and last double quote
    first = line.index('"')
    last = line.rindex('"')

    if first < last:
        # Change outer quotes to single quotes
        new_line = line[:first] + "'" + line[first+1:last] + "'" + line[last+1:]
        lines[i] = new_line
        fixed += 1

with open(filepath, 'w', encoding='utf-8') as f:
    f.write('\n'.join(lines))

print(f"Fixed {fixed} lines")
