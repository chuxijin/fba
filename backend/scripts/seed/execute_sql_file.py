import asyncio
import json
import sys
import asyncpg

CONFIG_PATH = r"C:\Users\19396\.gemini\antigravity\mcp_config.json"

def get_db_uri(env: str = "prod"):
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    server_key = "fba_dev" if env == "dev" else "fba_prod"
    return cfg["mcpServers"][server_key]["env"]["DATABASE_URI"]

async def execute_file(file_path: str, env: str = "prod"):
    uri = get_db_uri(env)
    print(f"[*] 目标环境: {env.upper()}, 正在读取 SQL 文件: {file_path}")
    with open(file_path, "r", encoding="utf-8") as f:
        sql_content = f.read().strip()
    
    if not sql_content:
        print("[!] 文件内容为空，跳过执行。")
        return

    statements = [s.strip() for s in sql_content.split(";") if s.strip()]
    print(f"[*] 包含 {len(statements)} 条独立 SQL 语句，正在建立数据库连接...")

    # 重试连接机制
    conn = None
    for attempt in range(3):
        try:
            conn = await asyncio.wait_for(asyncpg.connect(uri), timeout=15)
            break
        except Exception as e:
            print(f"[!] 连接尝试 {attempt+1} 失败 ({e})，重试中...")
            await asyncio.sleep(2)
            
    if not conn:
        raise ConnectionError(f"无法连接到 {env.upper()} 数据库")

    try:
        async with conn.transaction():
            for idx, stmt in enumerate(statements, 1):
                preview = stmt[:80].replace("\n", " ")
                print(f"  -> 执行语句 [{idx}/{len(statements)}]: {preview}...")
                status = await conn.execute(stmt)
                print(f"     状态: {status}")
        print(f"[✓] 事务提交成功: {file_path}")
    except Exception as e:
        print(f"[✗] 执行失败并回滚: {e}")
        raise
    finally:
        await conn.close()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python execute_sql_file.py <path_to_sql_file> [--dev]")
        sys.exit(1)
    target_env = "dev" if "--dev" in sys.argv else "prod"
    asyncio.run(execute_file(sys.argv[1], env=target_env))
