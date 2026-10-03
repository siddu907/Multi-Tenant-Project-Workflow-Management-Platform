from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from app.core.security import decode_token
from app.database import get_db
from app.repositories.user_repository import get_by_id
from app.websocket.manager import manager

router = APIRouter()

@router.websocket("/ws/notifications")
async def websocket_notifications(websocket: WebSocket, token: str | None = None, db: Session = Depends(get_db)):
    if not token:
        await websocket.close(code=1008)
        return
    try:
        payload = decode_token(token)
        user_id = int(payload.get("sub", 0))
    except Exception:
        await websocket.close(code=1008)
        return
    user = get_by_id(db, user_id)
    if payload.get("type") != "access" or user is None or not user.is_active:
        await websocket.close(code=1008)
        return
    await manager.connect(user.id, websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(user.id, websocket)
