import asyncio
import json
import re
import sys
import asyncpg

CONFIG_PATH = r"C:\Users\19396\.gemini\antigravity\mcp_config.json"
SQL_FILE_PATH = r"d:\100_Work\101_Program\Proj\fba\backend\scripts\seed\data\sync_dev_knowledge_system.sql"

def get_dev_db_uri():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    return cfg["mcpServers"]["fba_dev"]["env"]["DATABASE_URI"]

async def get_connection(uri):
    for attempt in range(5):
        try:
            print(f"[*] 尝试连接开发库 (尝试 {attempt+1}/5)...", flush=True)
            conn = await asyncio.wait_for(asyncpg.connect(uri, command_timeout=60), timeout=15)
            print("[✓] 连接成功！", flush=True)
            return conn
        except Exception as e:
            print(f"[!] 连接开发库失败: {e}，2秒后重试...", flush=True)
            await asyncio.sleep(2)
    raise ConnectionError("无法连接到开发数据库")

def parse_knowledge_points(sql_text):
    # 提取 VALUES (...) 里面的所有行
    pattern = re.compile(r"\s*\((?P<id>\d+),\s*(?P<system_id>\d+),\s*'(?P<code>[^']+)',\s*'(?P<name>[^']+)',\s*(?P<parent_id>\d+|NULL),\s*'(?P<path>[^']+)',\s*(?P<depth>\d+),\s*(?P<sort_order>\d+),\s*'(?P<desc>[^']*)',\s*1,\s*1,\s*NOW\(\),\s*NOW\(\),\s*0\)", re.MULTILINE)
    points = []
    for m in pattern.finditer(sql_text):
        row = m.groupdict()
        points.append({
            "id": int(row["id"]),
            "system_id": int(row["system_id"]),
            "code": row["code"],
            "name": row["name"],
            "parent_id": int(row["parent_id"]) if row["parent_id"] != "NULL" else None,
            "path": row["path"],
            "depth": int(row["depth"]),
            "sort_order": int(row["sort_order"]),
            "description": row["desc"]
        })
    return points

async def main():
    uri = get_dev_db_uri()
    print("[*] 正在解析 SQL 文件中的节点...", flush=True)
    with open(SQL_FILE_PATH, "r", encoding="utf-8") as f:
        content = f.read()
    
    points = parse_knowledge_points(content)
    print(f"[*] 共解析出 {len(points)} 个知识点节点", flush=True)
    if len(points) != 217:
        print(f"[!] 警告: 预期 217 个节点，实际解析到 {len(points)} 个", flush=True)

    # 按 depth 升序排序以保证外键/层级正确
    points.sort(key=lambda x: (x["depth"], x["sort_order"]))

    conn = await get_connection(uri)
    try:
        # 1. 归档旧体系
        print("[*] 1. 检查并归档旧体系 id=4...", flush=True)
        await conn.execute("UPDATE public.qbank_v2_knowledge_system SET deleted = id, deleted_time = NOW() WHERE id = 4 AND deleted = 0;")
        await conn.execute("UPDATE public.qbank_v2_knowledge_point SET deleted = id, deleted_time = NOW() WHERE system_id = 4 AND deleted = 0;")
        print("[✓] 旧体系 id=4 已归档", flush=True)

        # 2. 注册官方体系 id=8
        print("[*] 2. 注册/更新官方大纲三级知识体系 id=8...", flush=True)
        system_sql = """
        INSERT INTO public.qbank_v2_knowledge_system 
          (id, code, name, version, description, status, domain_category_id, created_by, updated_by, created_time, updated_time, deleted)
        VALUES 
          (8, 'kaoyan_politics', '考研政治', 'kaoyan', '2026考研政治官方大纲三级知识点体系', 'active', 1, 1, 1, NOW(), NOW(), 0)
        ON CONFLICT (id) DO UPDATE 
        SET name = EXCLUDED.name, 
            code = EXCLUDED.code, 
            version = EXCLUDED.version, 
            status = EXCLUDED.status,
            deleted = 0;
        """
        await conn.execute(system_sql)
        print("[✓] 官方三级知识体系注册成功", flush=True)

        # 3. 分批写入节点 (每批 15 个，降低网络单次包负载)
        batch_size = 15
        total_batches = (len(points) + batch_size - 1) // batch_size
        print(f"[*] 3. 开始分批写入 217 个知识点节点，共 {total_batches} 批...", flush=True)

        for b_idx in range(total_batches):
            batch = points[b_idx * batch_size : (b_idx + 1) * batch_size]
            values_clauses = []
            for p in batch:
                pid_str = "NULL" if p["parent_id"] is None else str(p["parent_id"])
                desc_escaped = p["description"].replace("'", "''")
                name_escaped = p["name"].replace("'", "''")
                values_clauses.append(
                    f"({p['id']}, {p['system_id']}, '{p['code']}', '{name_escaped}', {pid_str}, '{p['path']}', {p['depth']}, {p['sort_order']}, '{desc_escaped}', 1, 1, NOW(), NOW(), 0)"
                )
            
            insert_sql = f"""
            INSERT INTO public.qbank_v2_knowledge_point
              (id, system_id, code, name, parent_id, path, depth, sort_order, description, created_by, updated_by, created_time, updated_time, deleted)
            VALUES {','.join(values_clauses)}
            ON CONFLICT (id) DO UPDATE
            SET system_id = EXCLUDED.system_id,
                code = EXCLUDED.code,
                name = EXCLUDED.name,
                parent_id = EXCLUDED.parent_id,
                path = EXCLUDED.path,
                depth = EXCLUDED.depth,
                sort_order = EXCLUDED.sort_order,
                deleted = 0;
            """
            
            # 单批执行与重试
            for retry in range(3):
                try:
                    await conn.execute(insert_sql)
                    print(f"  -> 批次 [{b_idx+1}/{total_batches}] 写入完成 ({len(batch)} 节点, depth: {batch[0]['depth']}~{batch[-1]['depth']})", flush=True)
                    break
                except Exception as e:
                    print(f"  [!] 批次 {b_idx+1} 执行异常: {e}，尝试重新连接...", flush=True)
                    try:
                        await conn.close()
                    except Exception:
                        pass
                    conn = await get_connection(uri)
            await asyncio.sleep(0.1)

        # 4. 统计与核验
        count = await conn.fetchval("SELECT COUNT(*) FROM public.qbank_v2_knowledge_point WHERE system_id = 8 AND deleted = 0;")
        print(f"\n[★] 开发库考研政治知识体系同步成功！当前生效节点数: {count}/217", flush=True)

    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(main())
