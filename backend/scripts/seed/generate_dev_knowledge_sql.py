import ast
import json
from pathlib import Path

SOURCE_PATH = r"C:\Users\19396\.gemini\antigravity\brain\738149b1-faa3-4504-9362-270670c0721b\.system_generated\steps\1107\output.txt"
OUT_SQL = Path(r"D:\100_Work\101_Program\Proj\fba\backend\scripts\seed\data\sync_dev_knowledge_system.sql")

with open(SOURCE_PATH, "r", encoding="utf-8") as f:
    nodes = ast.literal_eval(f.read())

print(f"[*] 读取到生产库 217 节点数量: {len(nodes)}")

# 生成系统表注册 SQL (先归档旧的 id=4 体系以释放唯一索引)
system_sql = """-- 1. 归档开发库旧考研政治骨架
UPDATE public.qbank_v2_knowledge_system 
SET deleted = id, deleted_time = NOW() 
WHERE id = 4 AND deleted = 0;

UPDATE public.qbank_v2_knowledge_point
SET deleted = id, deleted_time = NOW()
WHERE system_id = 4 AND deleted = 0;

-- 2. 注册官方大纲三级知识体系 (system_id = 8)
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

# 生成知识点节点插入 SQL
value_rows = []
for n in nodes:
    nid = n["id"]
    sys_id = n["system_id"]
    code = f"'{n['code']}'" if n["code"] else "NULL"
    name = "'" + n["name"].replace("'", "''") + "'"
    pid = str(n["parent_id"]) if n["parent_id"] is not None else "NULL"
    path = f"'{n['path']}'" if n["path"] else "NULL"
    depth = n["depth"]
    sort_order = n["sort_order"]
    desc = "'" + n["description"].replace("'", "''") + "'" if n.get("description") else "NULL"
    
    value_rows.append(
        f"({nid}, {sys_id}, {code}, {name}, {pid}, {path}, {depth}, {sort_order}, {desc}, 1, 1, NOW(), NOW(), 0)"
    )

nodes_sql = """-- 2. 写入 217 个知识点节点
INSERT INTO public.qbank_v2_knowledge_point
  (id, system_id, code, name, parent_id, path, depth, sort_order, description, created_by, updated_by, created_time, updated_time, deleted)
VALUES
  """ + ",\n  ".join(value_rows) + """
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

full_sql = f"{system_sql}\n\n{nodes_sql}\n"
OUT_SQL.write_text(full_sql, encoding="utf-8")
print(f"[✓] 已生成开发库同步 SQL: {OUT_SQL} ({len(full_sql)} 字符)")
