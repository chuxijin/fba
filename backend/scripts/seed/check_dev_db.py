import asyncio
import json
import asyncpg

CONFIG_PATH = r"C:\Users\19396\.gemini\antigravity\mcp_config.json"

async def main():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    uri = cfg["mcpServers"]["fba_dev"]["env"]["DATABASE_URI"]
    
    conn = await asyncpg.connect(uri)
    rows = await conn.fetch("""
        SELECT 
            r.id as revision_id,
            r.name as revision_name,
            COUNT(bi.id) as item_count
        FROM public.qbank_v2_bank_item bi
        JOIN public.qbank_v2_bank_revision r ON bi.bank_revision_id = r.id
        WHERE bi.deleted = 0
        GROUP BY r.id, r.name
        ORDER BY item_count DESC
        LIMIT 25
    """)
    print("=== 开发库题量前25名 Revision ===")
    for r in rows:
        print(f"rid={r['revision_id']}: {r['revision_name']} ({r['item_count']} items)")
    await conn.close()

if __name__ == "__main__":
    asyncio.run(main())
