#!/usr/bin/env python3
"""Fix JSON by finding columns closing pattern and repairing it"""
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

    # Strategy: find the error, then try all possible single-char fixes
    try:
        json.loads(json_str)
    except json.JSONDecodeError as e:
        pos = e.pos

    found = False

    # Try: swap chars at pos-1 and pos
    if pos > 0 and pos < len(json_str):
        attempt = json_str[:pos-1] + json_str[pos] + json_str[pos-1] + json_str[pos+1:]
        try:
            json.loads(attempt)
            new_content = content[:match.start(2)] + attempt + content[match.end(2):]
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(new_content)
            fixed += 1
            print("FIXED (swap):", os.path.basename(filepath))
            found = True
        except json.JSONDecodeError:
            pass

    if not found:
        # Try: delete char at pos
        attempt = json_str[:pos] + json_str[pos+1:]
        try:
            json.loads(attempt)
            new_content = content[:match.start(2)] + attempt + content[match.end(2):]
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(new_content)
            fixed += 1
            print("FIXED (delete):", os.path.basename(filepath))
            found = True
        except json.JSONDecodeError:
            pass

    if not found:
        # Try: delete char at pos-1
        if pos > 0:
            attempt = json_str[:pos-1] + json_str[pos:]
            try:
                json.loads(attempt)
                new_content = content[:match.start(2)] + attempt + content[match.end(2):]
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(new_content)
                fixed += 1
                print("FIXED (delete prev):", os.path.basename(filepath))
                found = True
            except json.JSONDecodeError:
                pass

    if not found:
        # Try: replace char at pos with different bracket
        char = json_str[pos] if pos < len(json_str) else ''
        replacements = {
            '}': [']', ',', ''],
            ']': ['}', ',', ''],
            ',': ['}', ']', ''],
        }
        for rep in replacements.get(char, []):
            attempt = json_str[:pos] + rep + json_str[pos+1:]
            try:
                json.loads(attempt)
                new_content = content[:match.start(2)] + attempt + content[match.end(2):]
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(new_content)
                fixed += 1
                print("FIXED (replace):", os.path.basename(filepath))
                found = True
                break
            except json.JSONDecodeError:
                continue

    if not found:
        # Try: insert char before pos
        for ins in [']', '}', ',']:
            attempt = json_str[:pos] + ins + json_str[pos:]
            try:
                json.loads(attempt)
                new_content = content[:match.start(2)] + attempt + content[match.end(2):]
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(new_content)
                fixed += 1
                print("FIXED (insert):", os.path.basename(filepath))
                found = True
                break
            except json.JSONDecodeError:
                continue

    if not found:
        failed += 1
        if failed <= 3:
            print("FAILED:", os.path.basename(filepath), "at pos", pos)

print("\nTotal:", len(files), "| Fixed:", fixed, "| Failed:", failed)
