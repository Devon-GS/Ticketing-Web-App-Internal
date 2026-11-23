from fastapi import WebSocket
from .db import SessionLocal, settings
from .models import User
from .auth import decode_token


class ConnectionManager:
    def __init__(self) -> None:
        self.active_connections: set[WebSocket] = set()

    def authenticate(self, token: str) -> User | None:
        decoded = decode_token(token)
        if decoded is None:
            return None
        user_id, token_version = decoded

        with SessionLocal() as db:
            user = db.get(User, user_id)
            if not user or not user.is_active or user.token_version != token_version:
                return None
            return user

    async def connect(self, websocket: WebSocket, token: str) -> User | None:
        user = self.authenticate(token)
        if not user:
            return None

        self.active_connections.add(websocket)
        return user

    def disconnect(self, websocket: WebSocket) -> None:
        self.active_connections.discard(websocket)

    async def broadcast_refresh(self) -> None:
        message = {"action": "refresh"}
        disconnected: list[WebSocket] = []

        for connection in tuple(self.active_connections):
            try:
                await connection.send_json(message)
            except Exception:
                disconnected.append(connection)

        for connection in disconnected:
            self.disconnect(connection)


manager = ConnectionManager()
