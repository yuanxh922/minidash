import asyncio
from typing import Dict, Optional, Set


class OrderBroadcaster:
    """In-memory Pub/Sub event hub for broadcasting order tracking updates to active SSE connections."""

    def __init__(self) -> None:
        self.listeners: Dict[int, Set[asyncio.Queue]] = {}
        self._queue_loops: Dict[asyncio.Queue, asyncio.AbstractEventLoop] = {}

    def register_listener(self, order_id: int) -> asyncio.Queue:
        """Register a new asyncio.Queue listener for updates on order_id."""
        queue: asyncio.Queue = asyncio.Queue()

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = getattr(queue, "_loop", None)

        if loop is not None:
            self._queue_loops[queue] = loop

        if order_id not in self.listeners:
            self.listeners[order_id] = set()
        self.listeners[order_id].add(queue)

        return queue

    def unregister_listener(self, order_id: int, queue: asyncio.Queue) -> None:
        """Unregister an existing listener queue and clean up any listener mappings."""
        self._queue_loops.pop(queue, None)
        if order_id in self.listeners:
            self.listeners[order_id].discard(queue)
            if not self.listeners[order_id]:
                del self.listeners[order_id]

    def broadcast(self, order_id: int, payload: dict) -> None:
        """Broadcast payload to all active listener queues for the given order_id thread-safely."""
        if order_id not in self.listeners:
            return

        queues = list(self.listeners.get(order_id, set()))
        for queue in queues:
            loop = self._queue_loops.get(queue) or getattr(queue, "_loop", None)
            if loop is not None and not loop.is_closed():
                try:
                    current_loop: Optional[asyncio.AbstractEventLoop] = asyncio.get_running_loop()
                except RuntimeError:
                    current_loop = None

                if current_loop is loop:
                    queue.put_nowait(payload)
                else:
                    loop.call_soon_threadsafe(queue.put_nowait, payload)
            else:
                try:
                    queue.put_nowait(payload)
                except Exception:
                    pass


order_broadcaster = OrderBroadcaster()
