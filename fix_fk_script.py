import asyncio
import sys
import os

sys.path.append(os.getcwd())

from sqlalchemy import text
from backend.database.db import async_engine
from backend.core.conf import settings

async def main():
    # 使用项目中已配置好的引擎
    engine = async_engine
    
    async with engine.connect() as conn:
        print("Checking foreign keys for study_question_bank...")
        
        # 针对 PostgreSQL 的查询
        if settings.DATABASE_TYPE == 'postgresql':
            sql = """
            SELECT
                tc.constraint_name, 
                kcu.column_name, 
                ccu.table_name AS foreign_table_name
            FROM 
                information_schema.table_constraints AS tc 
                JOIN information_schema.key_column_usage AS kcu
                  ON tc.constraint_name = kcu.constraint_name
                  AND tc.table_schema = kcu.table_schema
                JOIN information_schema.constraint_column_usage AS ccu
                  ON ccu.constraint_name = tc.constraint_name
                  AND ccu.table_schema = tc.table_schema
            WHERE tc.constraint_type = 'FOREIGN KEY' AND tc.table_name='study_question_bank';
            """
        # 针对 MySQL 的查询
        else:
            sql = """
            SELECT 
                CONSTRAINT_NAME as constraint_name, 
                COLUMN_NAME as column_name, 
                REFERENCED_TABLE_NAME as foreign_table_name
            FROM
                INFORMATION_SCHEMA.KEY_COLUMN_USAGE
            WHERE
                TABLE_SCHEMA = DATABASE() AND
                TABLE_NAME = 'study_question_bank' AND
                REFERENCED_TABLE_NAME IS NOT NULL;
            """
            
        result = await conn.execute(text(sql))
        rows = result.fetchall()
        
        print(f"Found {len(rows)} foreign keys:")
        for row in rows:
            print(f" - Name: {row.constraint_name}, Column: {row.column_name}, Target Table: {row.foreign_table_name}")
            
            # 如果发现目标表是 study_exam_category，直接删除
            if row.foreign_table_name == 'study_exam_category':
                print(f"!!! FOUND TARGET !!! Dropping constraint: {row.constraint_name}")
                drop_sql = f"ALTER TABLE study_question_bank DROP CONSTRAINT {row.constraint_name}"
                # MySQL 语法可能不同: DROP FOREIGN KEY
                if settings.DATABASE_TYPE == 'mysql':
                     drop_sql = f"ALTER TABLE study_question_bank DROP FOREIGN KEY {row.constraint_name}"
                     
                await conn.execute(text(drop_sql))
                await conn.commit()
                print("Domain constraint dropped successfully.")

    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(main())
