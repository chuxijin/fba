#!/usr/bin/env python3
"""Fix remaining JSON issues by analyzing columns structure"""
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

    # The issue is with columns structure. The correct structure is:
    # {"type":"columns","content":[
    #   {"type":"column","content":[...]},
    #   {"type":"column","content":[...]}
    # ]}
    #
    # Common errors:
    # 1. Missing ] before closing } of columns
    # 2. Extra ] after columns closing }
    # 3. Wrong bracket types

    # Strategy: find all columns nodes and try to fix their structure
    # Look for the pattern: ...}]}}] or ...}]}}]}  etc.

    # Try replacing common wrong patterns
    patterns = [
        # Pattern: column ends with }]}}] but should be }]}}]}]
        (r'\}\]\}\}\]', '}]}}]}]'),
        # Pattern: column ends with }]}} but should be }]}]}
        (r'\}\]\}\}', '}]}]}'),
        # Pattern: column ends with }]}] but should be }]}}]
        (r'\}\}\]\]', '}}]}]'),
        # Pattern: extra ] at end
        (r'\}\]\}$', '}}'),
        # Pattern: missing ] for columns content
        (r'\}\]\}\}$', '}]}]}'),
    ]

    found = False
    for pattern, replacement in patterns:
        attempt = re.sub(pattern, replacement, json_str)
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
        # Try a brute force approach: find the error position and try all possible fixes
        try:
            json.loads(json_str)
        except json.JSONDecodeError as e:
            pos = e.pos
            # Try inserting various characters at the error position
            for char in [']', '}', '],', '},', ']}', '}]', ']]', '}}', ']}]', '}]}', ']}}', '}]}', ']}}]', '}]}]']:
                attempt = json_str[:pos] + char + json_str[pos:]
                try:
                    json.loads(attempt)
                    new_content = content[:match.start(2)] + attempt + content[match.end(2):]
                    with open(filepath, 'w', encoding='utf-8') as f:
                        f.write(new_content)
                    fixed += 1
                    print(f"FIXED (insert): {os.path.basename(filepath)}")
                    found = True
                    break
                except json.JSONDecodeError:
                    continue

            if not found:
                # Try deleting the character at error position
                attempt = json_str[:pos] + json_str[pos+1:]
                try:
                    json.loads(attempt)
                    new_content = content[:match.start(2)] + attempt + content[match.end(2):]
                    with open(filepath, 'w', encoding='utf-8') as f:
                        f.write(new_content)
                    fixed += 1
                    print(f"FIXED (delete): {os.path.basename(filepath)}")
                    found = True
                except json.JSONDecodeError:
                    pass

    if not found:
        failed += 1
        if failed <= 5:
            try:
                json.loads(json_str)
            except json.JSONDecodeError as e:
                print(f"FAILED: {os.path.basename(filepath)} at pos {e.pos}: {e.msg}")

print(f"\nTotal: {len(files)} | Fixed: {fixed} | Failed: {failed}")
