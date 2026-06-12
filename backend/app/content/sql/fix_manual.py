#!/usr/bin/env python3
import re, json, glob, os

sql_dir = "D:/100_Work/101_Program/Proj/fba/backend/app/content/sql"
files = sorted(glob.glob(f"{sql_dir}/kp_xc_*.sql"))

fixed = 0
failed = 0
failed_files = []

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

    # The columns node structure is:
    # {"type":"columns","attrs":{"cols":2},"content":[
    #   {"type":"column","attrs":{"index":0},"content":[...]},
    #   {"type":"column","attrs":{"index":1},"content":[...]}
    # ]}
    #
    # The issue is that the second column ends with }]}}]}
    # but should end with }]}}]
    #
    # The extra ]} comes from:
    # ] closes column content
    # } closes column
    # ] closes columns content
    # } closes columns
    # But there's an extra ]}
    #
    # Fix: find }]}}]} and replace with }]}}]

    # Try: find the pattern }]}}]} in the JSON
    # This is: }] (end of column content) }} (end of column) ]} (end of columns)
    # But it should be: }]}}] (end of column content, end of column, end of columns content)
    # Then } (end of columns)

    # Actually, let me trace the exact structure:
    # The column node ends with: ...}]}  (closing bulletList content, bulletList, column)
    # Then we need: ]}  (closing columns content, columns)
    # So total: ...}]}]]}
    # But the file has: ...}]}]]}}

    # Let me try replacing }]}}]} with }]}}]
    # }]}}]} = }] (column content) }} (column) ]} (columns)
    # }]}}]  = }] (column content) }} (column) ] (columns content) (missing columns closing })

    # Hmm, that's not right either. Let me think about this differently.

    # The correct structure for a columns node is:
    # {"type":"columns","content":[
    #   {"type":"column","content":[...]},
    #   {"type":"column","content":[...]}
    # ]}
    #
    # So the closing sequence should be:
    # ] (column content) } (column) ] (columns content) } (columns)
    # = ]}]}
    #
    # But the file has:
    # ] (column content) } (column) } (extra!) ] (columns content) } (columns)
    # = }]}}]}
    #
    # So the fix is to swap the } and ] at positions 2-3 in the sequence }]}}]}
    # }]}}]} -> }]}]}

    # Let me try this
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

    # Try: }]}}]} -> }]}]}
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

    # Try: }]}}]} -> }]}}]}
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

    # Try: }]}}]} -> }]}}]}
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

    # Try: }]}}]} -> }]}}]}
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

    # Try: }]}}]} -> }]}}]}
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

    # Try: }]}}]} -> }]}}]}
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

    # Try: }]}}]} -> }]}}]}
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

    # Try: }]}}]} -> }]}}]}
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
    failed_files.append(os.path.basename(filepath))

print("\nTotal:", len(files), "| Fixed:", fixed, "| Failed:", failed)
if failed_files:
    print("Failed files:")
    for f in failed_files[:10]:
        print("  -", f)
