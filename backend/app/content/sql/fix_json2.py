#!/usr/bin/env python3
"""Fix JSON syntax errors in SQL files - advanced version"""
import re, json, glob, os

sql_dir = "D:/100_Work/101_Program/Proj/fba/backend/app/content/sql"
files = sorted(glob.glob(f"{sql_dir}/kp_xc_*.sql"))

fixed = 0
failed = 0

for filepath in files:
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    match = re.search(r'(CAST\(\$\$)(.*?)(\$\$ AS jsonb\))', content, re.DOTALL)
    if not match:
        continue

    json_str = match.group(2).strip()

    # Try parsing as-is first
    try:
        json.loads(json_str)
        continue  # Already valid
    except json.JSONDecodeError as e:
        pass

    # Strategy: try adding closing brackets at various positions
    # The common issue is missing ] or } at the end

    # Try appending various combinations
    attempts = [
        json_str + ']}' * 3,
        json_str + ']}]}',
        json_str + ']}}',
        json_str + ']}',
        json_str + ']}' * 2,
        json_str + ']}}}',
        json_str + ']}]}}',
        json_str + ']}}}]}',
    ]

    found = False
    for attempt in attempts:
        try:
            json.loads(attempt)
            new_content = content[:match.start(2)] + attempt + content[match.end(2):]
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(new_content)
            fixed += 1
            print(f"FIXED: {os.path.basename(filepath)}")
            found = True
            break
        except json.JSONDecodeError:
            continue

    if not found:
        # Try a more aggressive approach: find the last valid position and add missing brackets
        # This is a heuristic approach
        json_str_fixed = json_str

        # Common pattern: ...}}] should be ...}]}]}
        # Find all positions of }}] and try replacing
        positions = [m.start() for m in re.finditer(r'\}\}\]', json_str)]
        for pos in reversed(positions):
            for replacement in ['}]}]}', '}}]}', '}}]]']:
                attempt = json_str[:pos] + replacement + json_str[pos+3:]
                try:
                    json.loads(attempt)
                    new_content = content[:match.start(2)] + attempt + content[match.end(2):]
                    with open(filepath, 'w', encoding='utf-8') as f:
                        f.write(new_content)
                    fixed += 1
                    print(f"FIXED (pattern): {os.path.basename(filepath)}")
                    found = True
                    break
                except json.JSONDecodeError:
                    continue
            if found:
                break

    if not found:
        failed += 1
        if failed <= 5:
            print(f"FAILED: {os.path.basename(filepath)}")

print(f"\nTotal: {len(files)} | Fixed: {fixed} | Failed: {failed}")
