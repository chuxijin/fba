import asyncio
import sys
import copy

# 确保能导入 backend
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from sqlalchemy import select
from backend.database.db import async_db_session
from backend.app.content.model.content import Content
from backend.common.log import log

def migrate_node(node):
    """
    递归迁移 Tiptap JSON 节点
    """
    if not isinstance(node, dict):
        return node
        
    # 浅拷贝，避免修改原对象过程中产生不可预知的问题
    new_node = copy.copy(node)
    
    node_type = new_node.get('type')
    
    if node_type == 'callout':
        new_node['type'] = 'highlightBlock'
        
    elif node_type == 'blockMath':
        new_node['type'] = 'katexBlock'
        if 'attrs' in new_node and 'latex' in new_node['attrs']:
            new_node['attrs']['content'] = new_node['attrs']['latex']
            del new_node['attrs']['latex']
            
    elif node_type == 'mermaidDiagram':
        new_node['type'] = 'text-diagram'
        if 'attrs' in new_node:
            if 'code' in new_node['attrs']:
                new_node['attrs']['content'] = new_node['attrs']['code']
                del new_node['attrs']['code']
            if 'type' not in new_node['attrs']:
                new_node['attrs']['type'] = 'mermaid'
        else:
            new_node['attrs'] = {'type': 'mermaid', 'content': ''}
            
    # 递归处理子节点
    if 'content' in new_node and isinstance(new_node['content'], list):
        new_node['content'] = [migrate_node(child) for child in new_node['content']]
        
    return new_node

async def run_migration():
    log.info("开始扫描并清洗 Tiptap 历史数据...")
    updated_count = 0
    total_count = 0
    
    async with async_db_session() as session:
        # 只查询有 JSON 内容的数据
        stmt = select(Content).where(Content.content_json.is_not(None))
        result = await session.execute(stmt)
        contents = result.scalars().all()
        
        total_count = len(contents)
        log.info(f"找到 {total_count} 条包含 content_json 的记录。")
        
        for content in contents:
            old_json = content.content_json
            if not old_json or not isinstance(old_json, dict):
                continue
                
            # 执行深度迁移
            new_json = migrate_node(old_json)
            
            # 判断是否有改动
            # 这里简单比较一下转换前后是否有差异即可（由于是新对象，所以使用 == 对比字典内容）
            if new_json != old_json:
                content.content_json = new_json
                updated_count += 1
                
        if updated_count > 0:
            log.info(f"检测到 {updated_count} 条记录需要修复，准备提交到数据库...")
            await session.commit()
            log.info("数据库更新完成！")
        else:
            log.info("没有发现需要修复的旧版节点（如 callout, blockMath 等），无需更新。")

if __name__ == "__main__":
    asyncio.run(run_migration())
