#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据库触发器管理脚本
用于创建和管理资源浏览量历史记录触发器
"""
import asyncio
import os
from pathlib import Path
from typing import Literal

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.db import async_engine


class TriggerManager:
    """触发器管理器"""
    
    def __init__(self):
        self.sql_dir = Path(__file__).parent
        
    async def get_database_type(self) -> Literal["mysql", "postgresql"]:
        """
        获取数据库类型
        
        :return: 数据库类型
        """
        db_url = str(async_engine.url)
        if "mysql" in db_url:
            return "mysql"
        elif "postgresql" in db_url:
            return "postgresql"
        else:
            raise ValueError(f"不支持的数据库类型: {db_url}")
    
    async def load_trigger_sql(self, action: Literal["create", "drop"] = "create") -> str:
        """
        加载触发器SQL脚本
        
        :param action: 操作类型，create 或 drop
        :return: SQL脚本内容
        """
        db_type = await self.get_database_type()
        sql_file = self.sql_dir / db_type / "triggers.sql"
        
        if not sql_file.exists():
            raise FileNotFoundError(f"触发器SQL文件不存在: {sql_file}")
        
        with open(sql_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        if action == "drop":
            # 提取删除触发器的SQL语句
            lines = content.split('\n')
            drop_statements = []
            for line in lines:
                if line.strip().startswith('-- DROP') or line.strip().startswith('DROP'):
                    if not line.strip().startswith('--'):
                        drop_statements.append(line.strip())
            return '\n'.join(drop_statements)
        
        return content
    
    async def execute_sql(self, sql: str) -> None:
        """
        执行SQL语句
        
        :param sql: SQL语句
        """
        async with AsyncSession(async_engine) as session:
            try:
                # 分割SQL语句（处理多个语句）
                statements = []
                current_statement = ""
                
                for line in sql.split('\n'):
                    line = line.strip()
                    if not line or line.startswith('--'):
                        continue
                    
                    current_statement += line + '\n'
                    
                    # MySQL: 以分号结尾且不在DELIMITER块中
                    # PostgreSQL: 以分号结尾
                    if line.endswith(';') and 'DELIMITER' not in current_statement:
                        if current_statement.strip() and not current_statement.strip().startswith('DELIMITER'):
                            statements.append(current_statement.strip())
                        current_statement = ""
                
                # 执行每个语句
                for statement in statements:
                    if statement.strip():
                        await session.execute(text(statement))
                
                await session.commit()
                print("✅ 触发器操作执行成功")
                
            except Exception as e:
                await session.rollback()
                print(f"❌ 触发器操作执行失败: {e}")
                raise
    
    async def create_triggers(self) -> None:
        """创建触发器"""
        print("🔧 正在创建资源浏览量历史记录触发器...")
        sql = await self.load_trigger_sql("create")
        await self.execute_sql(sql)
    
    async def drop_triggers(self) -> None:
        """删除触发器"""
        print("🗑️ 正在删除资源浏览量历史记录触发器...")
        sql = await self.load_trigger_sql("drop")
        await self.execute_sql(sql)
    
    async def check_triggers(self) -> None:
        """检查触发器状态"""
        print("🔍 正在检查触发器状态...")
        db_type = await self.get_database_type()
        
        async with AsyncSession(async_engine) as session:
            if db_type == "mysql":
                result = await session.execute(
                    text("SHOW TRIGGERS LIKE 'yp_resource'")
                )
            else:  # postgresql
                result = await session.execute(
                    text("""
                        SELECT trigger_name, event_manipulation, event_object_table 
                        FROM information_schema.triggers 
                        WHERE event_object_table = 'yp_resource'
                    """)
                )
            
            triggers = result.fetchall()
            if triggers:
                print("📋 已存在的触发器:")
                for trigger in triggers:
                    print(f"  - {trigger[0]}")
            else:
                print("📋 未找到相关触发器")


async def main():
    """主函数"""
    manager = TriggerManager()
    
    print("=== 资源浏览量历史记录触发器管理 ===")
    print("1. 创建触发器")
    print("2. 删除触发器") 
    print("3. 检查触发器状态")
    print("4. 退出")
    
    while True:
        choice = input("\n请选择操作 (1-4): ").strip()
        
        try:
            if choice == "1":
                await manager.create_triggers()
            elif choice == "2":
                await manager.drop_triggers()
            elif choice == "3":
                await manager.check_triggers()
            elif choice == "4":
                print("👋 再见!")
                break
            else:
                print("❌ 无效选择，请输入 1-4")
        except Exception as e:
            print(f"❌ 操作失败: {e}")


if __name__ == "__main__":
    asyncio.run(main()) 