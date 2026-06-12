#!/usr/bin/env python3
"""Fix JSON by adding missing closing brackets"""
import re, json, glob, os

sql_dir = "D:/100_Work/101_Program/Proj/fba/backend/app/content/sql"
files = sorted(glob.glob(f"{sql_dir}/kp_xc_*.sql"))

fixed = 0
failed = 0

for filepath in files:
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    start_marker = 'CAST($$'
    end_marker = '$$ AS jsonb)'
    start_idx = content.find(start_marker)
    end_idx = content.find(end_marker)

    if start_idx == -1 or end_idx == -1:
        continue

    json_str = content[start_idx + len(start_marker):end_idx].strip()

    try:
        json.loads(json_str)
        continue
    except json.JSONDecodeError:
        pass

    # Count brackets
    open_b = json_str.count('{')
    close_b = json_str.count('}')
    open_k = json_str.count('[')
    close_k = json_str.count(']')

    diff_b = open_b - close_b
    diff_k = open_k - close_k

    if diff_b > 0 or diff_k > 0:
        attempt = json_str + ']' * diff_k + '}' * diff_b
        try:
            json.loads(attempt)
            new_content = content[:start_idx + len(start_marker)] + attempt + content[end_idx:]
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(new_content)
            fixed += 1
            print("FIXED:", os.path.basename(filepath), "(+" + str(diff_k) + " ], +" + str(diff_b) + " })")
            continue
        except json.JSONDecodeError:
            pass

    # Try removing extra closing brackets from the end
    if diff_b < 0 or diff_k < 0:
        attempt = json_str
        for _ in range(abs(diff_b)):
            pos = attempt.rfind('}')
            if pos > 0:
                attempt = attempt[:pos] + attempt[pos+1:]
        for _ in range(abs(diff_k)):
            pos = attempt.rfind(']')
            if pos > 0:
                attempt = attempt[:pos] + attempt[pos+1:]
        try:
            json.loads(attempt)
            new_content = content[:start_idx + len(start_marker)] + attempt + content[end_idx:]
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(new_content)
            fixed += 1
            print("FIXED:", os.path.basename(filepath), "(removed extra brackets)")
            continue
        except json.JSONDecodeError:
            pass

    failed += 1
    if failed <= 5:
        print("FAILED:", os.path.basename(filepath), "diff_b={}, diff_k={}".format(diff_b, diff_k))

print("\nTotal:", len(files), "| Fixed:", fixed, "| Failed:", failed)
