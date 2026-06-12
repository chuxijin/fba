#!/usr/bin/env python3
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
    except json.JSONDecodeError as e:
        pos = e.pos

    # The issue is that the columns node has an extra } before ]}
    # Pattern: ...]}]}} should be ...]}]}
    # Let me try replacing }]}} with }]}

    # Find all }]}} patterns
    found = False
    for m in re.finditer(r'\}\]\}\}', json_str):
        p = m.start()
        attempt = json_str[:p] + '}]}]' + json_str[p+4:]
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

    # Try: replace }]}}]} with }]}]}
    if '}]}}]}]}' in json_str:
        attempt = json_str.replace('}]}}]}]}', '}]}]}]}')
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

    # Try: replace }]}}]} with }]}}]}
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

    # Try: remove the character at error position
    attempt = json_str[:pos] + json_str[pos+1:]
    try:
        json.loads(attempt)
        new_content = content[:match.start(2)] + attempt + content[match.end(2):]
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(new_content)
        fixed += 1
        print("FIXED (delete):", os.path.basename(filepath))
        continue
    except json.JSONDecodeError:
        pass

    # Try: swap characters at error position and before
    if pos > 0:
        attempt = json_str[:pos-1] + json_str[pos] + json_str[pos-1] + json_str[pos+1:]
        try:
            json.loads(attempt)
            new_content = content[:match.start(2)] + attempt + content[match.end(2):]
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(new_content)
            fixed += 1
            print("FIXED (swap):", os.path.basename(filepath))
            continue
        except json.JSONDecodeError:
            pass

    failed += 1
    if failed <= 3:
        print("FAILED:", os.path.basename(filepath), "at pos", pos)

print("\nTotal:", len(files), "| Fixed:", fixed, "| Failed:", failed)
