#!/usr/bin/env python3
"""Fix JSON by analyzing the exact structure"""
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
    except json.JSONDecodeError as e:
        error_pos = e.pos
        error_msg = e.msg

    # Analyze the error and try specific fixes
    # The common issue is with columns nodes

    # Strategy: try to fix by adjusting brackets around the error position
    # Look at the context around the error
    context_before = json_str[max(0, error_pos-20):error_pos]
    context_after = json_str[error_pos:min(len(json_str), error_pos+20)]

    # Try various fixes at the error position
    fixes = []

    # If error says "Expecting ',' delimiter", try replacing the char at error pos
    if "Expecting ',' delimiter" in error_msg:
        char_at = json_str[error_pos] if error_pos < len(json_str) else ''
        # Try replacing ] with }, or } with ],
        if char_at == ']':
            fixes.append(json_str[:error_pos] + '}' + json_str[error_pos+1:])
            fixes.append(json_str[:error_pos] + '},' + json_str[error_pos+1:])
        elif char_at == '}':
            fixes.append(json_str[:error_pos] + ']' + json_str[error_pos+1:])
            fixes.append(json_str[:error_pos] + '],' + json_str[error_pos+1:])

    # If error says "Expected end of input", try truncating at error pos
    if "Expected end of input" in error_msg:
        # Try truncating and adding proper closing
        truncated = json_str[:error_pos]
        for suffix in ['}]}', ']]', '}}', ']}]}', '}}}']:
            fixes.append(truncated + suffix)

    # Try each fix
    found = False
    for fix in fixes:
        try:
            json.loads(fix)
            new_content = content[:match.start(2)] + fix + content[match.end(2):]
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(new_content)
            fixed += 1
            print(f"FIXED: {os.path.basename(filepath)}")
            found = True
            break
        except json.JSONDecodeError:
            continue

    if not found:
        # Last resort: try to find the columns structure and fix it
        # Look for the pattern: ...}]}}]  which should be ...}]}]}]
        for pattern, replacement in [
            ('}]}}]', '}]}]}]'),
            ('}]}}', '}]}]}'),
            ('}]}]', '}]}]}'),
            ('}}]}}', '}}]}]}'),
        ]:
            if pattern in json_str:
                attempt = json_str.replace(pattern, replacement)
                try:
                    json.loads(attempt)
                    new_content = content[:match.start(2)] + attempt + content[match.end(2):]
                    with open(filepath, 'w', encoding='utf-8') as f:
                        f.write(new_content)
                    fixed += 1
                    print(f"FIXED (replace): {os.path.basename(filepath)}")
                    found = True
                    break
                except json.JSONDecodeError:
                    continue

    if not found:
        failed += 1
        if failed <= 3:
            print(f"FAILED: {os.path.basename(filepath)} at pos {error_pos}: {error_msg}")

print(f"\nTotal: {len(files)} | Fixed: {fixed} | Failed: {failed}")
