from fastapi import WebSocket
from jose import JWTError, jwt

from .db import SessionLocal, settings
from .models import User


class ConnectionManager:
    def __init__(self) -> None:
        self.active_connections: set[WebSocket] = set()

    def authenticate(self, token: str) -> User | None:
        try:
            user_id = int(jwt.decode(token, settings.jwt_secret, algorithms=["HS256"]).get("sub", ""))
        except (JWTError, ValueError, TypeError):
            return None

        with SessionLocal() as db:
            user = db.get(User, user_id)
            if not user or not user.is_active:
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
