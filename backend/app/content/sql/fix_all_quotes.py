#!/usr/bin/env python3
"""Fix all Chinese quote issues in fill_remaining.py"""
import re

filepath = "D:/100_Work/101_Program/Proj/fba/backend/app/content/sql/fill_remaining.py"

with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

lines = content.split('\n')
fixed = 0

for i, line in enumerate(lines):
    stripped = line.strip()
    if not stripped:
        continue

    # Skip docstring and f-string lines
    if stripped.startswith('"""') or 'f"""' in stripped:
        continue

    # Skip lines that already use single quotes
    if "'" in stripped and '"' not in stripped:
        continue

    # Count double quotes
    quote_count = stripped.count('"')

    # Lines with exactly 2 quotes are fine (normal string)
    if quote_count <= 2:
        continue

    # Lines with 4+ quotes likely have inner quotes
    # Check if this is a list item with string: ["text with "quotes"", ...]
    # or a tuple item: ("code", "slug", "title", ...)

    # For list items: ["text with "inner" quotes", ...]
    # Change to: ['text with "inner" quotes', ...]
    if stripped.startswith('["') or stripped.startswith("['"):
        # This is a list item
        # Find the string content between the first " and the last "
        first = line.index('"')
        # Find the closing quote - it's followed by ] or ,
        # Look for pattern: ",]  or ",
        last = line.rindex('"')
        if first < last and last > first + 1:
            # Check if there are inner quotes
            inner = line[first+1:last]
            if '"' in inner:
                # Change outer quotes to single quotes
                new_line = line[:first] + "'" + inner + "'" + line[last+1:]
                lines[i] = new_line
                fixed += 1
                continue

    # For other lines with multiple quotes
    # Try to find string literals and change outer quotes
    # Pattern: spaces + "text with "inner" quotes" + rest
    match = re.match(r'^(\s+)"(.+)"(.*)$', line)
    if match:
        prefix, content_str, suffix = match.groups()
        # Check if content has inner quotes
        if '"' in content_str:
            # Change outer quotes to single quotes
            new_line = prefix + "'" + content_str + "'" + suffix
            lines[i] = new_line
            fixed += 1

with open(filepath, 'w', encoding='utf-8') as f:
    f.write('\n'.join(lines))

print(f"Fixed {fixed} lines")
