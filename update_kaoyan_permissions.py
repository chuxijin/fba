import asyncio
from backend.database.db import async_db_session
from sqlalchemy import text

async def main():
    async with async_db_session() as session:
        result = await session.execute(text("""
            UPDATE study_question_bank
            SET access_entitlement_code = 'qbank_premium_bank_access'
            WHERE cat_id IN (
                SELECT id FROM sys_category 
                WHERE code LIKE '%kaoyan%' 
                  AND code NOT LIKE '%real_exam%'
            );
        """))
        await session.commit()
        print(f"Updated {result.rowcount} rows.")

if __name__ == '__main__':
    asyncio.run(main())
