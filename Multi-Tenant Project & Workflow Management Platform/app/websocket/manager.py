import asyncio
import json
from asyncio import AbstractEventLoop

from fastapi import WebSocket

class ConnectionManager:
    def __init__(self):
        self.active_connections: dict[int, set[WebSocket]] = {}
        self._event_loop: AbstractEventLoop | None = None

    async def connect(self, user_id: int, websocket: WebSocket):
        await websocket.accept()
        self._event_loop = asyncio.get_running_loop()
        self.active_connections.setdefault(user_id, set()).add(websocket)

    def disconnect(self, user_id: int, websocket: WebSocket):
        connections = self.active_connections.get(user_id)
        if connections is None:
            return
        connections.discard(websocket)
        if not connections:
            self.active_connections.pop(user_id, None)
        if not self.active_connections:
            self._event_loop = None

    async def send_personal_message(self, message: str, user_id: int):
        for websocket in list(self.active_connections.get(user_id, set())):
            await websocket.send_text(message)

    async def broadcast(self, message: str, user_id: int):
        await self.send_personal_message(message, user_id)

    def send_from_background(self, message: str, user_id: int) -> None:
        loop = self._event_loop
        if loop is None or loop.is_closed() or user_id not in self.active_connections:
            return

        def schedule_send() -> None:
            asyncio.create_task(self.send_personal_message(message, user_id))

        loop.call_soon_threadsafe(schedule_send)

    def push_notification_from_background(self, notification, user_id: int) -> None:
        self.send_from_background(
            json.dumps(
                {
                    "id": notification.id,
                    "type": notification.type,
                    "message": notification.message,
                    "created_at": notification.created_at.isoformat() if notification.created_at else None,
                }
            ),
            user_id,
        )


manager = ConnectionManager()
