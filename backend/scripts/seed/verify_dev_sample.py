import asyncio
import json
import asyncpg

CONFIG_PATH = r"C:\Users\19396\.gemini\antigravity\mcp_config.json"

async def check():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    uri = cfg["mcpServers"]["fba_dev"]["env"]["DATABASE_URI"]
    conn = await asyncpg.connect(uri)
    
    sample = await conn.fetch("""
        SELECT 
            bi.bank_revision_id,
            q.stem,
            kp.id as point_id,
            kp.name as point_name,
            qkp.confidence
        FROM public.qbank_v2_question_knowledge_point qkp
        JOIN public.qbank_v2_question q ON qkp.question_id = q.id
        JOIN public.qbank_v2_knowledge_point kp ON qkp.knowledge_point_id = kp.id
        JOIN public.qbank_v2_bank_item bi ON bi.question_id = q.id
        WHERE bi.bank_revision_id IN (17371, 17373, 17534)
          AND qkp.deleted = 0
        LIMIT 5;
    """)
    print("=== 开发库题目标注抽查 ===")
    for s in sample:
        stem = (s["stem"] or "")[:35].replace("\n", " ")
        print(f"Revision {s['bank_revision_id']} | 知识点 [{s['point_id']}] {s['point_name']} (置信度: {s['confidence']})")
        print(f"  题干: {stem}...\n")
    await conn.close()

if __name__ == "__main__":
    asyncio.run(check())
