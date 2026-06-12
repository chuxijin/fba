#!/usr/bin/env python3
"""Robust JSON fixer - tries multiple strategies"""
import re, json, glob, os

sql_dir = "D:/100_Work/101_Program/Proj/fba/backend/app/content/sql"
files = sorted(glob.glob(f"{sql_dir}/kp_xc_*.sql"))

fixed = 0
failed = 0
failed_files = []

for filepath in files:
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # Find JSON between $$ markers
    start_marker = 'CAST($$'
    end_marker = '$$ AS jsonb)'
    start_idx = content.find(start_marker)
    end_idx = content.find(end_marker)

    if start_idx == -1 or end_idx == -1:
        continue

    json_str = content[start_idx + len(start_marker):end_idx].strip()

    # Try parsing as-is first
    try:
        json.loads(json_str)
        continue
    except json.JSONDecodeError:
        pass

    # Strategy 1: Try adding missing closing brackets
    open_braces = json_str.count('{')
    close_braces = json_str.count('}')
    open_brackets = json_str.count('[')
    close_brackets = json_str.count(']')

    missing_braces = open_braces - close_braces
    missing_brackets = open_brackets - close_brackets

    if missing_braces > 0 or missing_brackets > 0:
        attempt = json_str + ']' * missing_brackets + '}' * missing_braces
        try:
            json.loads(attempt)
            new_content = content[:start_idx + len(start_marker)] + attempt + content[end_idx:]
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(new_content)
            fixed += 1
            print("FIXED (brackets):", os.path.basename(filepath))
            continue
        except json.JSONDecodeError:
            pass

    # Strategy 2: Try removing extra closing brackets
    if missing_braces < 0 or missing_brackets < 0:
        # Try removing from the end
        attempt = json_str
        for _ in range(abs(missing_braces)):
            pos = attempt.rfind('}')
            if pos > 0:
                attempt = attempt[:pos] + attempt[pos+1:]
        for _ in range(abs(missing_brackets)):
            pos = attempt.rfind(']')
            if pos > 0:
                attempt = attempt[:pos] + attempt[pos+1:]
        try:
            json.loads(attempt)
            new_content = content[:start_idx + len(start_marker)] + attempt + content[end_idx:]
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(new_content)
            fixed += 1
            print("FIXED (remove):", os.path.basename(filepath))
            continue
        except json.JSONDecodeError:
            pass

    # Strategy 3: Try fixing at error position
    try:
        json.loads(json_str)
    except json.JSONDecodeError as e:
        pos = e.pos

        # Try all possible single-char fixes at error position
        for char in ['}', ']', ',', '"', '']:
            for offset in [0, -1, 1]:
                p = pos + offset
                if p < 0 or p >= len(json_str):
                    continue
                attempt = json_str[:p] + char + json_str[p+1:]
                try:
                    json.loads(attempt)
                    new_content = content[:start_idx + len(start_marker)] + attempt + content[end_idx:]
                    with open(filepath, 'w', encoding='utf-8') as f:
                        f.write(new_content)
                    fixed += 1
                    print("FIXED (char):", os.path.basename(filepath))
                    break
                except json.JSONDecodeError:
                    continue
            else:
                continue
            break
        else:
            # Try inserting char before error position
            for char in ['}', ']', ',', '"']:
                attempt = json_str[:pos] + char + json_str[pos:]
                try:
                    json.loads(attempt)
                    new_content = content[:start_idx + len(start_marker)] + attempt + content[end_idx:]
                    with open(filepath, 'w', encoding='utf-8') as f:
                        f.write(new_content)
                    fixed += 1
                    print("FIXED (insert):", os.path.basename(filepath))
                    break
                except json.JSONDecodeError:
                    continue
            else:
                failed += 1
                failed_files.append(os.path.basename(filepath))
                if failed <= 5:
                    print("FAILED:", os.path.basename(filepath), "at pos", pos)
            continue

print("\nTotal:", len(files), "| Fixed:", fixed, "| Failed:", failed)
if failed_files:
    print("Failed files:")
    for f in failed_files[:10]:
        print("  -", f)
