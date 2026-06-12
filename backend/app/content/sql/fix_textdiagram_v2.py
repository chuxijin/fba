#!/usr/bin/env python3
"""Fix textDiagram node closing brackets - the issue is }]}} should be }}"""
import re, json, glob, os

sql_dir = "D:/100_Work/101_Program/Proj/fba/backend/app/content/sql"
files = sorted(glob.glob(f"{sql_dir}/kp_xc_*.sql"))

fixed = 0
failed = 0

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

    try:
        json.loads(json_str)
        continue
    except json.JSONDecodeError:
        pass

    # The issue is that textDiagram nodes have }]}} at the end
    # but should have }}
    # The }]}} is: " closes diagramSource, ] closes attrs array?, } closes attrs, } closes textDiagram
    # But should be: " closes diagramSource, } closes attrs, } closes textDiagram

    # Fix: replace }]}} with }}
    # But we need to be careful - the }]}} pattern might appear in other places too

    # Strategy: find textDiagram nodes and fix their closing
    found = False

    # Try: replace all }]}} with }}
    # But only when it's at the end of a textDiagram node
    # Pattern: ..."}]}} should be ..."}}
    # The }]}} comes after the diagramSource value

    # Let's try replacing }]}} with }} globally first
    attempt = json_str.replace('}]}}', '}}')
    try:
        json.loads(attempt)
        new_content = content[:start_idx + len(start_marker)] + attempt + content[end_idx:]
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(new_content)
        fixed += 1
        print("FIXED:", os.path.basename(filepath))
        found = True
    except json.JSONDecodeError:
        pass

    if not found:
        # Try: replace }]}}]} with }]}}
        attempt = json_str.replace('}]}}]}', '}]}}')
        try:
            json.loads(attempt)
            new_content = content[:start_idx + len(start_marker)] + attempt + content[end_idx:]
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(new_content)
            fixed += 1
            print("FIXED:", os.path.basename(filepath))
            found = True
        except json.JSONDecodeError:
            pass

    if not found:
        # Try: replace }]}}]} with }]}}
        attempt = json_str.replace('}]}}]}', '}]}}')
        try:
            json.loads(attempt)
            new_content = content[:start_idx + len(start_marker)] + attempt + content[end_idx:]
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(new_content)
            fixed += 1
            print("FIXED:", os.path.basename(filepath))
            found = True
        except json.JSONDecodeError:
            pass

    if not found:
        # Try: replace }]}}]} with }]}}
        attempt = json_str.replace('}]}}]}', '}]}}')
        try:
            json.loads(attempt)
            new_content = content[:start_idx + len(start_marker)] + attempt + content[end_idx:]
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(new_content)
            fixed += 1
            print("FIXED:", os.path.basename(filepath))
            found = True
        except json.JSONDecodeError:
            pass

    if not found:
        failed += 1
        if failed <= 5:
            print("FAILED:", os.path.basename(filepath))

print("\nTotal:", len(files), "| Fixed:", fixed, "| Failed:", failed)
