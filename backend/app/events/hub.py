import asyncio
from collections import defaultdict
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SessionEvent:
    event_type: str
    session_id: str


class SessionEventHub:
    def __init__(self) -> None:
        self._subscribers: dict[str, set[asyncio.Queue[SessionEvent]]] = defaultdict(set)
        self._lock = asyncio.Lock()

    async def subscribe(self, session_id: str) -> asyncio.Queue[SessionEvent]:
        queue: asyncio.Queue[SessionEvent] = asyncio.Queue(maxsize=32)
        async with self._lock:
            self._subscribers[session_id].add(queue)
        return queue

    async def unsubscribe(self, session_id: str, queue: asyncio.Queue[SessionEvent]) -> None:
        async with self._lock:
            subscribers = self._subscribers.get(session_id)
            if subscribers is None:
                return
            subscribers.discard(queue)
            if not subscribers:
                self._subscribers.pop(session_id, None)

    async def publish(self, event_type: str, session_id: str) -> None:
        event = SessionEvent(event_type=event_type, session_id=session_id)
        async with self._lock:
            queues = tuple(self._subscribers.get(session_id, set()))
        for queue in queues:
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                # The browser always refetches REST state after an event; dropping
                # a redundant notification is safer than blocking a write transaction.
                continue


_session_event_hub = SessionEventHub()


def get_session_event_hub() -> SessionEventHub:
    return _session_event_hub
