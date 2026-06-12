#!/usr/bin/env python3
"""Fix columns node closing brackets"""
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

    try:
        json.loads(json_str)
        continue
    except json.JSONDecodeError:
        pass

    # Find all columns nodes and fix their closing
    # The issue is that columns nodes have }]}}]}} at the end
    # but should have }]}}}

    # Strategy: find "type":"columns" and trace to its closing
    found = False

    # Try: replace }]}}]}} with }]}}}
    for old, new in [
        ('}]}}]}]}', '}]}]}}'),
        ('}]}}]}]}', '}]}]}]}'),
        ('}]}}]}]}', '}]}]}'),
        ('}]}]}]}', '}]}]}'),
        ('}]}]}]}', '}]}]}}'),
        ('}}]}]}', '}}]}]}'),
        ('}]}]}}', '}]}]}'),
        ('}}]}}', '}}]}]}'),
    ]:
        if old in json_str:
            attempt = json_str.replace(old, new)
            try:
                json.loads(attempt)
                new_content = content[:match.start(2)] + attempt + content[match.end(2):]
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(new_content)
                fixed += 1
                print("FIXED:", os.path.basename(filepath))
                found = True
                break
            except json.JSONDecodeError:
                continue

    if found:
        continue

    # Try: find }]}}]}] pattern and replace
    if '}]}}]}]}' in json_str:
        attempt = json_str.replace('}]}}]}]}', '}]}]}}]')
        try:
            json.loads(attempt)
            new_content = content[:match.start(2)] + attempt + content[match.end(2):]
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(new_content)
            fixed += 1
            print("FIXED:", os.path.basename(filepath))
            continue
        except json.JSONDecodeError:
            pass

    # Try: find }]}}]}] pattern and replace with }]}}]}
    if '}]}}]}]}' in json_str:
        attempt = json_str.replace('}]}}]}]}', '}]}]}}]')
        try:
            json.loads(attempt)
            new_content = content[:match.start(2)] + attempt + content[match.end(2):]
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(new_content)
            fixed += 1
            print("FIXED:", os.path.basename(filepath))
            continue
        except json.JSONDecodeError:
            pass

    failed += 1
    if failed <= 5:
        print("FAILED:", os.path.basename(filepath))

print("\nTotal:", len(files), "| Fixed:", fixed, "| Failed:", failed)
