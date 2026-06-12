#!/usr/bin/env python3
"""Fix JSON by replacing }}] with }]}"""
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

    # The issue is that column nodes end with }}] but should end with }]}
    # This happens because the column content array closes with ]
    # then the column object closes with }
    # then there's an extra } before the ] that closes the columns content array

    # Fix: replace }}] with }]} at the end of column nodes
    # But we need to be careful not to replace other }}] patterns

    # Strategy: find all }}] patterns and try replacing each one
    positions = [m.start() for m in re.finditer(r'\}\}\]', json_str)]

    found = False
    for pos in reversed(positions):
        # Try replacing }}] with }]}
        attempt = json_str[:pos] + '}]}' + json_str[pos+3:]
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
        # Try: replace }]}} with }]}}
        positions = [m.start() for m in re.finditer(r'\}\]\}\}', json_str)]
        for pos in reversed(positions):
            attempt = json_str[:pos] + '}]}}' + json_str[pos+5:]
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
        # Try: replace }]}}]} with }]}}]}
        if '}]}}]}]}' in json_str:
            attempt = json_str.replace('}]}}]}]}', '}]}]}}]')
            try:
                json.loads(attempt)
                new_content = content[:match.start(2)] + attempt + content[match.end(2):]
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(new_content)
                fixed += 1
                print(f"FIXED: {os.path.basename(filepath)}")
                found = True
            except json.JSONDecodeError:
                pass

    if not found:
        # Try: replace }]}}]} with }]}]}
        if '}]}}]}]}' in json_str:
            attempt = json_str.replace('}]}}]}]}', '}]}]}]}')
            try:
                json.loads(attempt)
                new_content = content[:match.start(2)] + attempt + content[match.end(2):]
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(new_content)
                fixed += 1
                print(f"FIXED: {os.path.basename(filepath)}")
                found = True
            except json.JSONDecodeError:
                pass

    if not found:
        failed += 1
        if failed <= 3:
            try:
                json.loads(json_str)
            except json.JSONDecodeError as e:
                print(f"FAILED: {os.path.basename(filepath)} at pos {e.pos}: {e.msg}")

print(f"\nTotal: {len(files)} | Fixed: {fixed} | Failed: {failed}")
