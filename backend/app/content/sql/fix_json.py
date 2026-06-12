#!/usr/bin/env python3
"""Fix JSON syntax errors in SQL files"""
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
    except json.JSONDecodeError:
        pass

    # Common fix: columns structure - missing ] before closing }
    # Pattern: ...}}]}  should be ...}}]}]}
    # Try fixing by balancing brackets

    # Count brackets
    open_braces = json_str.count('{')
    close_braces = json_str.count('}')
    open_brackets = json_str.count('[')
    close_brackets = json_str.count(']')

    # Try adding missing closing brackets/braces
    if close_brackets < open_brackets:
        json_str_fixed = json_str + ']' * (open_brackets - close_brackets)
        try:
            json.loads(json_str_fixed)
            new_content = content[:match.start(2)] + json_str_fixed + content[match.end(2):]
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(new_content)
            fixed += 1
            print(f"FIXED (brackets): {os.path.basename(filepath)}")
            continue
        except json.JSONDecodeError:
            pass

    if close_braces < open_braces:
        json_str_fixed = json_str + '}' * (open_braces - close_braces)
        try:
            json.loads(json_str_fixed)
            new_content = content[:match.start(2)] + json_str_fixed + content[match.end(2):]
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(new_content)
            fixed += 1
            print(f"FIXED (braces): {os.path.basename(filepath)}")
            continue
        except json.JSONDecodeError:
            pass

    # Try both
    json_str_fixed = json_str + ']' * max(0, open_brackets - close_brackets) + '}' * max(0, open_braces - close_braces)
    try:
        json.loads(json_str_fixed)
        new_content = content[:match.start(2)] + json_str_fixed + content[match.end(2):]
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(new_content)
        fixed += 1
        print(f"FIXED (both): {os.path.basename(filepath)}")
        continue
    except json.JSONDecodeError:
        pass

    # More complex fix: try to find and fix the specific issue
    # The common issue is }}] should be }}]}
    json_str_fixed = json_str.replace('}}]}}', '}}]}}]')
    try:
        json.loads(json_str_fixed)
        new_content = content[:match.start(2)] + json_str_fixed + content[match.end(2):]
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(new_content)
        fixed += 1
        print(f"FIXED (pattern): {os.path.basename(filepath)}")
        continue
    except json.JSONDecodeError:
        pass

    # Try: missing ] before final }
    # Pattern: ...}]}}  should be ...}]}}]
    json_str_fixed = re.sub(r'\}\]\}\}$', '}]}}]', json_str)
    try:
        json.loads(json_str_fixed)
        new_content = content[:match.start(2)] + json_str_fixed + content[match.end(2):]
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(new_content)
        fixed += 1
        print(f"FIXED (regex): {os.path.basename(filepath)}")
        continue
    except json.JSONDecodeError:
        pass

    failed += 1
    if failed <= 3:
        print(f"FAILED: {os.path.basename(filepath)} (open:{open_braces}/{open_brackets} close:{close_braces}/{close_brackets})")

print(f"\nTotal: {len(files)} | Fixed: {fixed} | Failed: {failed}")
