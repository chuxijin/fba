with open('d:/100_Work/101_Program/Proj/fba/backend/scripts/seed/step2_sections.sql', encoding='utf-8') as f:
    lines = f.readlines()

header = lines[:2]
footer = lines[-1:]
body = lines[2:-1]

mid = len(body) // 2

p2_a = header + body[:mid] + footer
p2_b = header + body[mid:] + footer

with open('d:/100_Work/101_Program/Proj/fba/backend/scripts/seed/step2_partA.sql', 'w', encoding='utf-8') as f:
    f.writelines(p2_a)

with open('d:/100_Work/101_Program/Proj/fba/backend/scripts/seed/step2_partB.sql', 'w', encoding='utf-8') as f:
    f.writelines(p2_b)

print(f'Part A: {len(body[:mid])} items, Part B: {len(body[mid:])} items')
