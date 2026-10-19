import json

with open("d:/100_Work/101_Program/Proj/fba/backend/scripts/seed/data/benchmark_data_2026.json", "r", encoding="utf-8") as f:
    bench = json.load(f)
ch_dict = {s["chapter_id"]: (s["subject_name"], s["chapter_name"]) for s in bench["sections"]}

for bname, fname in [("米1000题", "mi_1000_data.json"), ("余500题", "yu_500_data.json")]:
    print("=" * 60)
    print(f"=== 审查 {bname} 章节匹配 ===")
    with open("d:/100_Work/101_Program/Proj/fba/backend/scripts/seed/data/" + fname, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    mismatch_count = 0
    for m in data["section_mappings"]:
        sid = m["bank_section_id"]
        b_name = m["bank_section_name"]
        b_sub = m["parent_subject_name"]
        ch_id = m["official_chapter_id"]
        off_info = ch_dict.get(ch_id, ("未知", "未知"))
        
        # 核心比对：如果原名里的关键词在官方名里完全没有，就是错位！
        # 比如：原名包含“物质”、“认识”、“资本主义”、“辛亥革命”等
        is_suspicious = False
        if "导论" in b_name and "导论" not in off_info[1]:
            is_suspicious = True
        elif "生产力" in b_name and "生产力" not in off_info[1]:
            is_suspicious = True
        
        flag = "【可疑错位!】" if is_suspicious else "  [OK]"
        if is_suspicious:
            mismatch_count += 1
        print(f"{flag} sid={sid:4d} | {b_sub} | 原名: {b_name} -> 官方: ch_{ch_id} {off_info[1]}")
    print(f"总计可疑错位: {mismatch_count}/{len(data['section_mappings'])}")
