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
    except json.JSONDecodeError:
        pass

    # Strategy: find the columns node and fix it
    # The columns node should have content: [column1, column2]
    # Each column has content: [nodes...]
    # The issue is that the closing is wrong

    # Find all "type":"columns" positions
    columns_positions = [m.start() for m in re.finditer(r'"type":"columns"', json_str)]

    found = False
    for col_pos in columns_positions:
        # Find the start of this object (go back to find {)
        start = col_pos
        while start > 0 and json_str[start] != '{':
            start -= 1

        # Find the end by matching brackets
        depth = 0
        end = start
        for i in range(start, len(json_str)):
            if json_str[i] == '{':
                depth += 1
            elif json_str[i] == '}':
                depth -= 1
                if depth == 0:
                    end = i + 1
                    break

        columns_json = json_str[start:end]

        # Try to fix this specific columns node
        # The issue is usually that the closing is }]}}]} instead of }]}}]

        # Try various fixes
        fixes = [
            (']}}]}]}', ']}}]}'),  # Remove extra ]}
            ('}]}]}]}', '}]}]}'),   # Remove extra ]}
            ('}}]}]}', '}}]}'),    # Remove extra ]}
            ('}]}]}}', '}]}]}'),   # Fix bracket order
            ('}}]}}', '}}]}'),     # Fix bracket order
        ]

        for old, new in fixes:
            if old in columns_json:
                fixed_json = columns_json.replace(old, new)
                try:
                    json.loads(fixed_json)
                    json_fixed = json_str[:start] + fixed_json + json_str[end:]
                    try:
                        json.loads(json_fixed)
                        new_content = content[:match.start(2)] + json_fixed + content[match.end(2):]
                        with open(filepath, 'w', encoding='utf-8') as f:
                            f.write(new_content)
                        fixed += 1
                        print("FIXED:", os.path.basename(filepath))
                        found = True
                        break
                    except json.JSONDecodeError:
                        continue
                except json.JSONDecodeError:
                    continue

        if found:
            break

    if not found:
        # Last resort: try to fix the entire JSON by finding and fixing the error
        try:
            json.loads(json_str)
        except json.JSONDecodeError as e:
            pos = e.pos
            # Try removing the character at error position
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

            # Try swapping with next character
            if pos + 1 < len(json_str):
                attempt = json_str[:pos] + json_str[pos+1] + json_str[pos] + json_str[pos+2:]
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
            print("FAILED:", os.path.basename(filepath))

print("\nTotal:", len(files), "| Fixed:", fixed, "| Failed:", failed)
