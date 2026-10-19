import asyncio
import json
import os
import sys
import asyncpg

CONFIG_PATH = r"C:\Users\19396\.gemini\antigravity\mcp_config.json"
DATA_DIR = r"d:\100_Work\101_Program\Proj\fba\backend\scripts\seed\data"

BANKS = [
    {
        "name": "27米1000题",
        "dev_revision_id": 17371,
        "data_file": "mi_1000_data.json",
        "cache_file": "mi_1000_results_cache.json",
    },
    {
        "name": "27余500题",
        "dev_revision_id": 17373,
        "data_file": "yu_500_data.json",
        "cache_file": "yu_500_results_cache.json",
    },
    {
        "name": "【27版】徐10套卷",
        "dev_revision_id": 17534,
        "data_file": "xutao_10juan_330_data.json",
        "cache_file": "xutao_10juan_330_results_cache.json",
    },
]

def get_dev_db_uri():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    return cfg["mcpServers"]["fba_dev"]["env"]["DATABASE_URI"]

async def get_connection(uri):
    for attempt in range(5):
        try:
            conn = await asyncio.wait_for(asyncpg.connect(uri, command_timeout=60), timeout=15)
            return conn
        except Exception as e:
            print(f"[!] 连接开发库失败: {e}，2秒后重试...", flush=True)
            await asyncio.sleep(2)
    raise ConnectionError("无法连接到开发数据库")

def load_bank_mappings(b_conf):
    data_path = os.path.join(DATA_DIR, b_conf["data_file"])
    cache_path = os.path.join(DATA_DIR, b_conf["cache_file"])
    
    with open(data_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    with open(cache_path, "r", encoding="utf-8") as f:
        cache = json.load(f)
        
    # cache: list of {question_id, point_id, confidence, ...}
    cache_by_qid = {}
    for c in cache:
        if c.get("success") and c.get("point_id"):
            cache_by_qid[c["question_id"]] = {
                "point_id": c["point_id"],
                "confidence": c.get("confidence", 0.95)
            }
            
    # data['questions']: list of {question_id, sort_order, stem, ...}
    mapping_by_order = {}
    for q in data["questions"]:
        qid = q["question_id"]
        if qid in cache_by_qid:
            mapping_by_order[q["sort_order"]] = {
                "point_id": cache_by_qid[qid]["point_id"],
                "confidence": cache_by_qid[qid]["confidence"],
                "stem_prefix": (q.get("stem") or "")[:20].strip()
            }
    return mapping_by_order

async def main():
    uri = get_dev_db_uri()
    conn = await get_connection(uri)
    print("[✓] 成功连接开发数据库", flush=True)

    try:
        total_matched = 0
        total_inserted = 0

        for b in BANKS:
            print(f"\n==========================================", flush=True)
            print(f"[*] 处理题库: {b['name']} (dev_revision_id: {b['dev_revision_id']})", flush=True)
            mapping_by_order = load_bank_mappings(b)
            print(f"[*] 本地缓存映射已加载: {len(mapping_by_order)} 道题", flush=True)

            # 查询开发库该 revision 下的所有题目
            dev_rows = await conn.fetch("""
                SELECT bi.sort_order, q.id as question_id, q.stem
                FROM public.qbank_v2_bank_item bi
                JOIN public.qbank_v2_question q ON bi.question_id = q.id
                WHERE bi.bank_revision_id = $1
                  AND bi.deleted = 0
                  AND q.deleted = 0
                ORDER BY bi.sort_order;
            """, b["dev_revision_id"])

            print(f"[*] 开发库中查出题目: {len(dev_rows)} 道", flush=True)

            records_to_insert = []
            mismatch_count = 0
            for r in dev_rows:
                s_order = r["sort_order"]
                qid = r["question_id"]
                stem_prefix = (r["stem"] or "")[:20].strip()

                if s_order in mapping_by_order:
                    target = mapping_by_order[s_order]
                    # 校验题干一致性
                    if target["stem_prefix"] and stem_prefix and target["stem_prefix"][:10] != stem_prefix[:10]:
                        mismatch_count += 1
                    records_to_insert.append({
                        "question_id": qid,
                        "point_id": target["point_id"],
                        "confidence": target["confidence"]
                    })
                else:
                    print(f"  [!] 缺失映射 sort_order={s_order}, qid={qid}", flush=True)

            print(f"[*] 成功匹配: {len(records_to_insert)}/{len(dev_rows)} 道 (题干微差异校验警告: {mismatch_count})", flush=True)
            total_matched += len(records_to_insert)

            # 分批写入 (每批 100 条)
            batch_size = 100
            for i in range(0, len(records_to_insert), batch_size):
                chunk = records_to_insert[i : i + batch_size]
                val_strs = [
                    f"({c['question_id']}, {c['point_id']}, 'primary', 1.0, 'ai', {c['confidence']}, 1, 1, NOW(), NOW(), 0)"
                    for c in chunk
                ]
                sql = f"""
                INSERT INTO public.qbank_v2_question_knowledge_point
                  (question_id, knowledge_point_id, role, weight, source, confidence, created_by, updated_by, created_time, updated_time, deleted)
                VALUES {','.join(val_strs)}
                ON CONFLICT (question_id, knowledge_point_id, deleted) DO UPDATE
                SET confidence = EXCLUDED.confidence,
                    role = EXCLUDED.role,
                    source = EXCLUDED.source,
                    updated_time = NOW();
                """
                for retry in range(3):
                    try:
                        await conn.execute(sql)
                        break
                    except Exception as e:
                        print(f"  [!] 批次写入异常: {e}，重试中...", flush=True)
                        try:
                            await conn.close()
                        except Exception:
                            pass
                        conn = await get_connection(uri)
                total_inserted += len(chunk)
            print(f"[✓] {b['name']} 写入完成: {len(records_to_insert)} 条", flush=True)

        print(f"\n==========================================", flush=True)
        print(f"[★] 全量写入完成！累计匹配 {total_matched} 题，累计落库 {total_inserted} 条！", flush=True)

        # 统计开发库知识点覆盖情况
        stat_rows = await conn.fetch("""
            SELECT 
                bi.bank_revision_id,
                COUNT(DISTINCT bi.question_id) as total_questions,
                COUNT(DISTINCT qkp.question_id) as tagged_questions
            FROM public.qbank_v2_bank_item bi
            LEFT JOIN public.qbank_v2_question_knowledge_point qkp 
              ON bi.question_id = qkp.question_id AND qkp.deleted = 0
            WHERE bi.bank_revision_id IN (17371, 17373, 17534)
              AND bi.deleted = 0
            GROUP BY bi.bank_revision_id;
        """)
        print("\n=== 开发库三套题库最终知识点覆盖率统计 ===", flush=True)
        for s in stat_rows:
            rid = s["bank_revision_id"]
            tot = s["total_questions"]
            tag = s["tagged_questions"]
            pct = (tag / tot * 100) if tot > 0 else 0
            print(f"  Revision {rid}: 已标注 {tag}/{tot} 题 ({pct:.2f}%)", flush=True)

    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(main())
