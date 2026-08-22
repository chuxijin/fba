from __future__ import annotations

import argparse
import asyncio
import os
import sys

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

os.environ.setdefault('FBA_DEV', '1')

from backend.database.redis import redis_client  # noqa: E402


async def run(*, key: str, idempotency_key: str | None) -> None:
    await redis_client.init()
    try:
        print({'counter_key': key, 'value': await redis_client.get(key), 'ttl': await redis_client.ttl(key)})
        if idempotency_key:
            print({
                'idempotency_key': idempotency_key,
                'value': await redis_client.get(idempotency_key),
                'ttl': await redis_client.ttl(idempotency_key),
            })
    finally:
        await redis_client.aclose()


def main() -> None:
    parser = argparse.ArgumentParser(description='只读检查申论 Agent 试看 Redis 计数')
    parser.add_argument('--key', required=True)
    parser.add_argument('--idempotency-key')
    args = parser.parse_args()
    asyncio.run(run(key=args.key, idempotency_key=args.idempotency_key))


if __name__ == '__main__':
    main()
