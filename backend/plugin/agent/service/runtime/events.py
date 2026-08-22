import asyncio
import json

from collections import defaultdict
from collections.abc import AsyncIterator


class AgentEventBus:
    """进程内 Agent SSE 事件总线"""

    def __init__(self) -> None:
        self._queues: dict[int, set[asyncio.Queue[str]]] = defaultdict(set)
        self._terminal_events: dict[int, str] = {}

    async def publish(self, run_id: int, payload: dict) -> None:
        data = f'data: {json.dumps(payload, ensure_ascii=False, default=str)}\n\n'
        if payload.get('status') in {'succeeded', 'failed', 'cancelled'}:
            self._terminal_events[run_id] = data
            if len(self._terminal_events) > 1000:
                self._terminal_events.pop(next(iter(self._terminal_events)))
        for queue in tuple(self._queues.get(run_id, set())):
            await queue.put(data)

    async def stream(self, run_id: int) -> AsyncIterator[str]:
        queue: asyncio.Queue[str] = asyncio.Queue()
        self._queues[run_id].add(queue)
        try:
            terminal = self._terminal_events.get(run_id)
            if terminal is not None:
                yield terminal
                return
            while True:
                item = await queue.get()
                yield item
                try:
                    payload = json.loads(item.removeprefix('data: ').strip())
                except json.JSONDecodeError:
                    payload = {}
                if payload.get('status') in {'succeeded', 'failed', 'cancelled'}:
                    break
        finally:
            self._queues[run_id].discard(queue)
            if not self._queues[run_id]:
                self._queues.pop(run_id, None)


agent_event_bus = AgentEventBus()
