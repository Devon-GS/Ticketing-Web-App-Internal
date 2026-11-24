from fastapi import WebSocket
from .db import SessionLocal, settings
from .models import User
from .auth import decode_token, normalize_token_version


class ConnectionManager:
    def __init__(self) -> None:
        self.active_connections: dict[WebSocket, int] = {}

    def authenticate(self, token: str) -> User | None:
        decoded = decode_token(token)
        if decoded is None:
            return None
        user_id, token_version = decoded

        with SessionLocal() as db:
            user = db.get(User, user_id)
            if not user or not user.is_active or normalize_token_version(user.token_version) != token_version:
                return None
            return user

    async def connect(self, websocket: WebSocket, token: str) -> User | None:
        user = self.authenticate(token)
        if not user:
            return None

        self.active_connections[websocket] = user.id
        return user

    def disconnect(self, websocket: WebSocket) -> None:
        self.active_connections.pop(websocket, None)

    async def close_user_connections(self, user_id: int) -> None:
        connections = [connection for connection, connection_user_id in self.active_connections.items() if connection_user_id == user_id]
        for connection in connections:
            try:
                await connection.close(code=1008, reason="Session revoked")
            except Exception:
                pass
            self.disconnect(connection)

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
