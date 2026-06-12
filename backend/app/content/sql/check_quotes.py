#!/usr/bin/env python3
"""Check character encoding of problematic lines"""

filepath = "D:/100_Work/101_Program/Proj/fba/backend/app/content/sql/fill_l6_part2.py"

with open(filepath, 'r', encoding='utf-8') as f:
    lines = f.readlines()

problem_lines = [37, 52, 67, 82, 97, 143, 204, 295, 310, 340, 401, 416, 446, 462, 477, 507, 537, 613, 643, 734, 764, 780, 795, 810, 813, 855, 885, 916, 946, 961, 1010, 1025, 1055, 1070]

for i in problem_lines:
    if i <= len(lines):
        line = lines[i-1].strip()
        # Find Chinese-looking quote characters
        for j, ch in enumerate(line):
            if ord(ch) > 127 and ch not in '，。、；：？！（）【】《》—…·':
                print(f"Line {i}, pos {j}: U+{ord(ch):04X} = {ch}")
        print(f"Line {i}: {line[:80]}")
        print()
