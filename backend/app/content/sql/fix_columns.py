#!/usr/bin/env python3
"""Fix columns structure in SQL files"""
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
        continue
    except json.JSONDecodeError:
        pass

    # Fix: remove extra }] at end of columns nodes
    # Pattern: ...}]}]}]}}]} should be ...}]}]}]}}
    # The issue is that column content ends with }]}}]} but should end with }]}]}]

    # Find all columns nodes and fix them
    columns_pattern = r'"type":"columns"'
    json_fixed = json_str
    changes_made = False

    for m in re.finditer(columns_pattern, json_fixed):
        pos = m.start()
        # Find the start of this object
        start = pos
        while start > 0 and json_fixed[start] != '{':
            start -= 1

        # Find the end by matching brackets
        depth = 0
        end = start
        for i in range(start, len(json_fixed)):
            if json_fixed[i] == '{':
                depth += 1
            elif json_fixed[i] == '}':
                depth -= 1
                if depth == 0:
                    end = i + 1
                    break

        columns_json = json_fixed[start:end]

        # Try to fix the columns node
        # Common issue: extra }] at the end
        # The correct structure ends with }]}
        # But it has }]}]}

        # Try removing trailing }]
        if columns_json.endswith('}]}]}'):
            fixed_json = columns_json[:-2]  # Remove ]}
            try:
                json.loads(fixed_json)
                json_fixed = json_fixed[:start] + fixed_json + json_fixed[end:]
                changes_made = True
                break
            except json.JSONDecodeError:
                pass

        # Try removing trailing }
        if columns_json.endswith('}}]}'):
            fixed_json = columns_json[:-1]  # Remove }
            try:
                json.loads(fixed_json)
                json_fixed = json_fixed[:start] + fixed_json + json_fixed[end:]
                changes_made = True
                break
            except json.JSONDecodeError:
                pass

        # Try: the column node might have extra }]
        # Pattern: ...}]}}]} should be ...}]}]}
        if '}]}]}}]}' in columns_json:
            fixed_json = columns_json.replace('}]}]}}]}', '}]}]}]}')
            try:
                json.loads(fixed_json)
                json_fixed = json_fixed[:start] + fixed_json + json_fixed[end:]
                changes_made = True
                break
            except json.JSONDecodeError:
                pass

    if changes_made:
        try:
            json.loads(json_fixed)
            new_content = content[:match.start(2)] + json_fixed + content[match.end(2):]
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(new_content)
            fixed += 1
            print(f"FIXED: {os.path.basename(filepath)}")
            continue
        except json.JSONDecodeError:
            pass

    # Alternative approach: try fixing the entire JSON by removing extra brackets
    # Find the pattern }]}}]}  and replace with }]}}]}
    if '}]}}]}}' in json_str:
        attempt = json_str.replace('}]}}]}}', '}]}]}}')
        try:
            json.loads(attempt)
            new_content = content[:match.start(2)] + attempt + content[match.end(2):]
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(new_content)
            fixed += 1
            print(f"FIXED (global): {os.path.basename(filepath)}")
            continue
        except json.JSONDecodeError:
            pass

    failed += 1
    if failed <= 3:
        try:
            json.loads(json_str)
        except json.JSONDecodeError as e:
            print(f"FAILED: {os.path.basename(filepath)} at pos {e.pos}: {e.msg}")

print(f"\nTotal: {len(files)} | Fixed: {fixed} | Failed: {failed}")
