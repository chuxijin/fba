import asyncio
import json
import re
from pathlib import Path
from typing import Any
import asyncpg

CONFIG_PATH = r"C:\Users\19396\.gemini\antigravity\mcp_config.json"
DATA_DIR = Path(__file__).resolve().parent / "data"
OFFICIAL_DATA_PATH = DATA_DIR / "benchmark_data_2026.json"


def get_prod_uri() -> str:
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    return cfg["mcpServers"]["fba_prod"]["env"]["DATABASE_URI"]


def clean_name(name: str) -> str:
    if not name:
        return ""
    # 去除括号及其中内容，如“（含绪论）”
    name = re.sub(r"（[^）]*）|\([^)]*\)", "", name)
    # 去除空白
    return name.strip()


async def main():
    uri = get_prod_uri()
    print("[*] 正在加载官方大纲字典...")
    with open(OFFICIAL_DATA_PATH, "r", encoding="utf-8") as f:
        official_data = json.load(f)

    all_sections = official_data["sections"]
    
    # 学科 -> section_ids
    subject_sections: dict[str, list[int]] = {}
    # chapter_id -> section_ids
    chapter_sections: dict[int, list[int]] = {}
    # (subject_name, clean_chapter_name) -> chapter_id
    chapter_map: dict[tuple[str, str], int] = {}

    subject_aliases = {
        "马原": "马克思主义基本原理概论",
        "马克思基本原理": "马克思主义基本原理概论",
        "马克思主义基本原理": "马克思主义基本原理概论",
        "毛中特": "毛泽东思想和中国特色社会主义理论体系概论",
        "新思想": "新时代中国特色社会主义思想概论",
        "史纲": "中国近现代史纲要",
        "中国近代史纲要": "中国近现代史纲要",
        "中国近现代史纲要": "中国近现代史纲要",
        "思修": "思想道德修养与法律基础",
        "思修法基": "思想道德修养与法律基础",
        "当代": "形势政策以及当代世界经济与政治",
        "时政": "形势政策以及当代世界经济与政治",
        "时事政治": "形势政策以及当代世界经济与政治",
    }

    for s in all_sections:
        sub_name = s["subject_name"]
        ch_id = s["chapter_id"]
        ch_name = clean_name(s["chapter_name"])
        sec_id = s["section_id"]

        subject_sections.setdefault(sub_name, []).append(sec_id)
        chapter_sections.setdefault(ch_id, []).append(sec_id)
        chapter_map[(sub_name, ch_name)] = ch_id

    conn = await asyncpg.connect(uri)
    try:
        # ==========================================
        # 1. 处理【徐10套卷】 (bank_revision_id = 1621)
        # ==========================================
        print("\n=== 处理【徐10套卷】(id=1621) ===")
        # 10套卷的 section 是 depth=0 的卷名称
        sections_1621 = await conn.fetch("""
            SELECT id, name, sort_order 
            FROM fba.qbank_v2_bank_section 
            WHERE bank_revision_id = 1621 AND deleted = 0
            ORDER BY sort_order, id
        """)
        
        items_1621 = await conn.fetch("""
            SELECT 
                bi.id as item_id,
                bi.bank_revision_id,
                bi.section_id,
                bi.sort_order,
                q.id as question_id,
                q.question_type,
                q.stem,
                q.option_data,
                qe.content as explanation
            FROM fba.qbank_v2_bank_item bi
            JOIN fba.qbank_v2_question q ON bi.question_id = q.id
            LEFT JOIN fba.qbank_v2_question_explanation qe ON qe.question_id = q.id AND qe.deleted = 0
            WHERE bi.bank_revision_id = 1621
            ORDER BY bi.section_id, bi.sort_order
        """)

        # 每套卷按题号映射学科候选池
        # 单选 1-4 (idx 0-3): 马原
        # 单选 5-8 (idx 4-7): 毛中特 + 新思想
        # 单选 9-12 (idx 8-11): 史纲
        # 单选 13-14 (idx 12-13): 思修法基
        # 单选 15-16 (idx 14-15): 时政当代
        # 多选 17-21 (idx 16-20): 马原
        # 多选 22-26 (idx 21-25): 毛中特 + 新思想
        # 多选 27-29 (idx 26-28): 史纲
        # 多选 30-31 (idx 29-30): 思修法基
        # 多选 32-33 (idx 31-32): 时政当代

        def get_subject_for_xu_index(idx: int) -> tuple[str, list[int]]:
            if (0 <= idx <= 3) or (16 <= idx <= 20):
                sub = "马克思主义基本原理概论"
                return sub, subject_sections["马克思主义基本原理概论"]
            elif (4 <= idx <= 7) or (21 <= idx <= 25):
                sub = "毛中特与新思想概论"
                cands = subject_sections.get("毛泽东思想和中国特色社会主义理论体系概论", []) + \
                        subject_sections.get("新时代中国特色社会主义思想概论", [])
                return sub, cands
            elif (8 <= idx <= 11) or (26 <= idx <= 28):
                sub = "中国近现代史纲要"
                return sub, subject_sections["中国近现代史纲要"]
            elif (12 <= idx <= 13) or (29 <= idx <= 30):
                sub = "思想道德修养与法律基础"
                return sub, subject_sections["思想道德修养与法律基础"]
            else:
                sub = "形势政策以及当代世界经济与政治"
                return sub, subject_sections["形势政策以及当代世界经济与政治"]

        # 构建徐10套卷数据
        sec_name_map_1621 = {s["id"]: s["name"] for s in sections_1621}
        # 为了方便流水线复用，构建虚拟 section_mappings: (section_id, sub_idx_range)
        # 或者直接在 question 对象中携带 candidate_section_ids 与 context_label
        # 为统一起见，我们按 (section_id * 100 + subject_group_code) 注册映射
        xu10_section_mappings = []
        xu10_questions = []

        mapping_registry = {}
        for r in items_1621:
            sec_id = r["section_id"]
            sec_name = sec_name_map_1621.get(sec_id, f"卷{sec_id}")
            idx_in_paper = r["sort_order"] % 33  # 卷内序号 0~32
            sub_label, cands = get_subject_for_xu_index(idx_in_paper)
            
            mapping_key = (sec_id, sub_label)
            if mapping_key not in mapping_registry:
                synth_sec_id = sec_id * 100 + len(mapping_registry) % 100
                mapping_entry = {
                    "bank_section_id": synth_sec_id,
                    "parent_subject_name": sub_label,
                    "bank_section_name": f"{sec_name} ({sub_label})",
                    "target_chapter_name": sub_label,
                    "official_chapter_id": None,
                    "candidate_section_ids": cands
                }
                mapping_registry[mapping_key] = mapping_entry
                xu10_section_mappings.append(mapping_entry)
            else:
                synth_sec_id = mapping_registry[mapping_key]["bank_section_id"]

            xu10_questions.append({
                "item_id": r["item_id"],
                "question_id": r["question_id"],
                "bank_section_id": synth_sec_id,
                "sort_order": r["sort_order"],
                "question_type": r["question_type"],
                "stem": r["stem"],
                "option_data": r["option_data"],
                "explanation": r["explanation"]
            })

        out_xu10 = {
            "bank_name": "【27版】徐10套卷",
            "bank_revision_id": 1621,
            "section_mappings": xu10_section_mappings,
            "questions": xu10_questions
        }
        p_xu10 = DATA_DIR / "xutao_10juan_330_data.json"
        with open(p_xu10, "w", encoding="utf-8") as f:
            json.dump(out_xu10, f, ensure_ascii=False, indent=2)
        print(f"[✓] 徐10套卷已导出: {len(xu10_questions)} 题, {len(xu10_section_mappings)} 个学科试卷段 -> {p_xu10.name}")

        # ==========================================
        # 2. 处理【米1000题】(1462) 与 【余500题】(1464)
        # ==========================================
        for rid, name, out_fname in [
            (1462, "27米1000题", "mi_1000_data.json"),
            (1464, "27余500题", "yu_500_data.json")
        ]:
            print(f"\n=== 处理【{name}】(id={rid}) ===")
            sections = await conn.fetch("""
                SELECT 
                    s.id as section_id,
                    s.name as section_name,
                    p.id as parent_id,
                    p.name as parent_name
                FROM fba.qbank_v2_bank_section s
                LEFT JOIN fba.qbank_v2_bank_section p ON s.parent_id = p.id
                WHERE s.bank_revision_id = $1 AND s.depth = 1 AND s.deleted = 0
                ORDER BY s.sort_order, s.id
            """, rid)

            items = await conn.fetch("""
                SELECT 
                    bi.id as item_id,
                    bi.bank_revision_id,
                    bi.section_id,
                    bi.sort_order,
                    q.id as question_id,
                    q.question_type,
                    q.stem,
                    q.option_data,
                    qe.content as explanation
                FROM fba.qbank_v2_bank_item bi
                JOIN fba.qbank_v2_question q ON bi.question_id = q.id
                LEFT JOIN fba.qbank_v2_question_explanation qe ON qe.question_id = q.id AND qe.deleted = 0
                WHERE bi.bank_revision_id = $1
                ORDER BY bi.section_id, bi.sort_order
            """, rid)

            sec_mappings = []
            unmatched_secs = []

            for s in sections:
                sid = s["section_id"]
                sname = s["section_name"]
                pname = s["parent_name"] or ""
                
                # 标准化学科名
                canon_sub = subject_aliases.get(pname, pname)
                c_sname = clean_name(sname)

                # 寻找匹配的官方 chapter_id
                matched_ch_id = None

                # 1. (canon_sub, c_sname) 精确匹配
                if (canon_sub, c_sname) in chapter_map:
                    matched_ch_id = chapter_map[(canon_sub, c_sname)]
                else:
                    # 2. 前缀/模糊匹配（如“第一章”、“导论”）
                    for (ch_sub, ch_clean), ch_id in chapter_map.items():
                        if ch_sub == canon_sub:
                            # 提取章号如“第一章”或“导论”
                            c_num_match = re.match(r"^(第[一二三四五六七八九十百]+章|导论|绪论)", c_sname)
                            target_num_match = re.match(r"^(第[一二三四五六七八九十百]+章|导论|绪论)", ch_clean)
                            if c_num_match and target_num_match and c_num_match.group(1) == target_num_match.group(1):
                                matched_ch_id = ch_id
                                break

                if matched_ch_id:
                    cand_ids = chapter_sections.get(matched_ch_id, [])
                else:
                    # 降级：如果章未对齐，用整个学科的节
                    cand_ids = subject_sections.get(canon_sub, [])
                    unmatched_secs.append((sid, sname, pname, canon_sub))

                sec_mappings.append({
                    "bank_section_id": sid,
                    "parent_subject_name": canon_sub,
                    "bank_section_name": sname,
                    "target_chapter_name": sname,
                    "official_chapter_id": matched_ch_id,
                    "candidate_section_ids": cand_ids
                })

            if unmatched_secs:
                print(f"[!] {len(unmatched_secs)} 个章节使用学科降级候选池:")
                for u in unmatched_secs[:5]:
                    print(f"    - sid={u[0]}: {u[1]} (学科: {u[3]}) -> 候选数: {len(subject_sections.get(u[3], []))}")
            else:
                print(f"[✓] 章节 100% 精确对齐到官方大纲章节！")

            questions_data = []
            for r in items:
                questions_data.append({
                    "item_id": r["item_id"],
                    "question_id": r["question_id"],
                    "bank_section_id": r["section_id"],
                    "sort_order": r["sort_order"],
                    "question_type": r["question_type"],
                    "stem": r["stem"],
                    "option_data": r["option_data"],
                    "explanation": r["explanation"]
                })

            out_data = {
                "bank_name": name,
                "bank_revision_id": rid,
                "section_mappings": sec_mappings,
                "questions": questions_data
            }
            p_out = DATA_DIR / out_fname
            with open(p_out, "w", encoding="utf-8") as f:
                json.dump(out_data, f, ensure_ascii=False, indent=2)
            print(f"[✓] {name}已导出: {len(questions_data)} 题, {len(sec_mappings)} 个章节 -> {p_out.name}")

    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(main())
