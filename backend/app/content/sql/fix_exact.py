#!/usr/bin/env python3
"""Fix JSON by exact pattern matching"""
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

    # The issue is that columns nodes have }]}}]} at the end
    # but should have }]}]}
    # This happens because the column node closes with }]}}
    # but the columns content array closes with ] and columns object closes with }
    # So it should be }]}}]} but has }]}}]}}

    # Let me try to find and fix this specific pattern
    # Look for the sequence: }]}}]}  (which is wrong)
    # and replace with: }]}]}  (which is correct)

    # Actually, let me trace the exact issue:
    # The columns node structure is:
    # {"type":"columns","content":[
    #   {"type":"column","content":[...]},
    #   {"type":"column","content":[...]}
    # ]}
    #
    # The second column ends with: }]}}  (closing listItem, bulletList, column)
    # Then we need: ]}  (closing columns content array, columns object)
    # So total should be: }]}]}
    # But the file has: }]}]}]}
    # There's an extra }]}

    # Let me try replacing }]}}]} with }]}]}
    if '}]}}]}]}' in json_str:
        attempt = json_str.replace('}]}}]}]}', '}]}]}]}')
        try:
            json.loads(attempt)
            new_content = content[:match.start(2)] + attempt + content[match.end(2):]
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(new_content)
            fixed += 1
            print(f"FIXED: {os.path.basename(filepath)}")
            continue
        except json.JSONDecodeError:
            pass

    # Try: }]}}]} should be }]}}]}
    if '}]}}]}]}' in json_str:
        attempt = json_str.replace('}]}}]}]}', '}]}]}}]')
        try:
            json.loads(attempt)
            new_content = content[:match.start(2)] + attempt + content[match.end(2):]
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(new_content)
            fixed += 1
            print(f"FIXED: {os.path.basename(filepath)}")
            continue
        except json.JSONDecodeError:
            pass

    # Try: find the error position and fix
    try:
        json.loads(json_str)
    except json.JSONDecodeError as e:
        pos = e.pos
        # Look at what's around the error
        before = json_str[max(0, pos-5):pos]
        after = json_str[pos:min(len(json_str), pos+5)]

        # If the error is at a }, try replacing it with ]
        if json_str[pos] == '}':
            attempt = json_str[:pos] + ']' + json_str[pos+1:]
            try:
                json.loads(attempt)
                new_content = content[:match.start(2)] + attempt + content[match.end(2):]
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(new_content)
                fixed += 1
                print(f"FIXED (replace): {os.path.basename(filepath)}")
                continue
            except json.JSONDecodeError:
                pass

        # If the error is at a ], try replacing it with }
        if json_str[pos] == ']':
            attempt = json_str[:pos] + '}' + json_str[pos+1:]
            try:
                json.loads(attempt)
                new_content = content[:match.start(2)] + attempt + content[match.end(2):]
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(new_content)
                fixed += 1
                print(f"FIXED (replace): {os.path.basename(filepath)}")
                continue
            except json.JSONDecodeError:
                pass

        # Try deleting the character at error position
        attempt = json_str[:pos] + json_str[pos+1:]
        try:
            json.loads(attempt)
            new_content = content[:match.start(2)] + attempt + content[match.end(2):]
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(new_content)
            fixed += 1
            print(f"FIXED (delete): {os.path.basename(filepath)}")
            continue
        except json.JSONDecodeError:
            pass

        # Try inserting a ] before the error position
        attempt = json_str[:pos] + ']' + json_str[pos:]
        try:
            json.loads(attempt)
            new_content = content[:match.start(2)] + attempt + content[match.end(2):]
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(new_content)
            fixed += 1
            print(f"FIXED (insert): {os.path.basename(filepath)}")
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
