"""清理指定的拼团并发测试临时 schema；不接受业务 schema 名。"""
import argparse
import asyncio
import re

from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.schema import DropSchema

from backend.core.conf import settings
from backend.database.db import get_database_url


async def cleanup(schema: str) -> None:
    if settings.ENVIRONMENT != 'dev' or not re.fullmatch(r'gb_test_[0-9a-f]{32}', schema):
        raise ValueError('只能清理开发环境中明确指定的 gb_test_ 临时 schema')
    engine = create_async_engine(get_database_url())
    try:
        async with engine.begin() as connection:
            await connection.execute(DropSchema(schema, cascade=True, if_exists=True))
    finally:
        await engine.dispose()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--schema', required=True)
    args = parser.parse_args()
    asyncio.run(cleanup(args.schema))
    print('指定的临时测试 schema 已清理')
