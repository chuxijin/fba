import asyncio
import json
import asyncpg

CONFIG_PATH = r"C:\Users\19396\.gemini\antigravity\mcp_config.json"

async def main():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    uri_dev = cfg["mcpServers"]["fba_dev"]["env"]["DATABASE_URI"]
    conn_dev = await asyncpg.connect(uri_dev)
    
    # 查找开发库中所有的题库 Revision
    rows = await conn_dev.fetch("""
        SELECT 
            r.id as revision_id,
            r.name as revision_name,
            COUNT(bi.id) as item_count
        FROM public.qbank_v2_bank_revision r
        LEFT JOIN public.qbank_v2_bank_item bi ON bi.bank_revision_id = r.id AND bi.deleted = 0
        WHERE r.deleted = 0
        GROUP BY r.id, r.name
        HAVING COUNT(bi.id) > 0
        ORDER BY item_count DESC
    """)
    print("=== 开发库中包含题目的所有题库 ===")
    for r in rows:
        rid = r["revision_id"]
        name = r["revision_name"]
        cnt = r["item_count"]
        # 获取首尾题目的信息
        first_q = await conn_dev.fetchrow(f"""
            SELECT bi.sort_order, q.id as qid, q.stem 
            FROM public.qbank_v2_bank_item bi
            JOIN public.qbank_v2_question q ON bi.question_id = q.id
            WHERE bi.bank_revision_id = {rid} AND bi.deleted = 0
            ORDER BY bi.sort_order
            LIMIT 1
        """)
        f_stem = (first_q["stem"] or "")[:35].replace("\n", " ") if first_q else ""
        print(f"rid={rid:5d} | {name:30s} | 题量: {cnt:4d} | 首题: {f_stem}...")
        
    await conn_dev.close()

if __name__ == "__main__":
    asyncio.run(main())
