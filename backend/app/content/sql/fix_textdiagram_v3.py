#!/usr/bin/env python3
"""Fix textDiagram node - replace }]}} with }}"""
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

    # The issue is }]}} should be }}
    # This happens at the end of textDiagram nodes
    # The }]}} is: " closes diagramSource, ] is wrong, } closes attrs, } closes textDiagram
    # Should be: " closes diagramSource, } closes attrs, } closes textDiagram

    # Fix: replace }]}} with }}
    if '}]}}' in json_str:
        attempt = json_str.replace('}]}}', '}}')
        try:
            json.loads(attempt)
            new_content = content[:start_idx + len(start_marker)] + attempt + content[end_idx:]
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(new_content)
            fixed += 1
            print("FIXED:", os.path.basename(filepath))
            continue
        except json.JSONDecodeError:
            pass

    # Fix: replace }]}} with }}
    if '}]}}' in json_str:
        attempt = json_str.replace('}]}}', '}}')
        try:
            json.loads(attempt)
            new_content = content[:start_idx + len(start_marker)] + attempt + content[end_idx:]
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(new_content)
            fixed += 1
            print("FIXED:", os.path.basename(filepath))
            continue
        except json.JSONDecodeError:
            pass

    # Fix: replace }]}} with }}
    if '}]}}' in json_str:
        attempt = json_str.replace('}]}}', '}}')
        try:
            json.loads(attempt)
            new_content = content[:start_idx + len(start_marker)] + attempt + content[end_idx:]
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
