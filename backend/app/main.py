from contextlib import asynccontextmanager
import asyncio
import json
import logging

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import inspect, select, text
from .db import Base, SessionLocal, engine, settings
from .models import Label, Role, User
from .auth import hash_password, normalize_username
from .routers import auth, tickets, admin
from .realtime import manager

logger = logging.getLogger(__name__)

KNOWN_DEFAULTS = {
    "development-secret", "replace-this-with-a-long-random-secret",
    "replace-this-in-production", "ChangeMe123!", "Admin123!", "admin",
}

def configured_origins(value: str, *, development_fallback: bool = False) -> list[str]:
    origins = [item.strip().rstrip("/") for item in value.split(",") if item.strip()]
    if not origins and development_fallback:
        return ["http://localhost:5173"]
    return origins

def validate_startup_settings() -> None:
    environment = settings.environment.casefold()
    if environment not in {"production", "development"}:
        raise RuntimeError("ENVIRONMENT must be either production or development")
    if environment == "development":
        return
    required = {
        "JWT_SECRET": settings.jwt_secret,
        "ADMIN_USERNAME": settings.admin_username,
        "ADMIN_PASSWORD": settings.admin_password,
    }
    known_defaults = {value.casefold() for value in KNOWN_DEFAULTS}
    if (len(settings.jwt_secret) < 32
            or any(not value.strip() or value.casefold() in known_defaults for value in required.values())
            or len(settings.admin_password) < 12
            or not configured_origins(settings.allowed_origins)):
        raise RuntimeError("Production requires non-default JWT_SECRET, ADMIN_USERNAME, and ADMIN_PASSWORD")

def migrate_legacy_users():
    if not inspect(engine).has_table("users"):
        return
    with engine.begin() as connection:
        columns = {column["name"] for column in inspect(engine).get_columns("users")}
        if "token_version" not in columns:
            connection.execute(text("ALTER TABLE users ADD COLUMN token_version INTEGER NOT NULL DEFAULT 0"))
        connection.execute(text("UPDATE users SET token_version = 0 WHERE token_version IS NULL"))
        if "username" not in columns and "email" in columns:
            connection.execute(text("ALTER TABLE users ADD COLUMN username VARCHAR(80)"))
            connection.execute(text("UPDATE users SET username = split_part(email, '@', 1) WHERE username IS NULL"))
            connection.execute(text("ALTER TABLE users ALTER COLUMN username SET NOT NULL"))
            connection.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ix_users_username ON users (username)"))

@asynccontextmanager
async def lifespan(app: FastAPI):
    validate_startup_settings()
    migrate_legacy_users()
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        admin = db.scalar(select(User).where(User.role == Role.admin).limit(1))
        if admin:
            logger.info("Administrator account '%s' already exists; skipping bootstrap admin creation", admin.username)
        else:
            db.add(User(username=normalize_username(settings.admin_username), full_name="System Administrator", password_hash=hash_password(settings.admin_password), role=Role.admin))
            logger.info("Created bootstrap administrator account '%s'", settings.admin_username)
        if not db.scalar(select(Label)):
            db.add_all([Label(name="urgent", color="#dc2626"), Label(name="normal", color="#2563eb"), Label(name="overdue account", color="#d97706")])
        db.commit()
    yield

docs_url = None if settings.environment.casefold() == "production" else "/docs"
redoc_url = None if settings.environment.casefold() == "production" else "/redoc"
app = FastAPI(title="Ticketing API", version="1.0.0", lifespan=lifespan, docs_url=docs_url, redoc_url=redoc_url)
app.add_middleware(
    CORSMiddleware,
    allow_origins=configured_origins(settings.allowed_origins, development_fallback=settings.environment.casefold() == "development"),
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

@app.middleware("http")
async def security_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response


@app.websocket("/api/ws")
async def websocket_endpoint(websocket: WebSocket):
    origin = websocket.headers.get("origin", "").rstrip("/")
    allowed_ws_origins = configured_origins(
        settings.allowed_ws_origins or settings.allowed_origins,
        development_fallback=settings.environment.casefold() == "development",
    )
    if not origin or origin not in allowed_ws_origins:
        await websocket.close(code=1008, reason="Origin not allowed")
        return
    if manager.at_capacity():
        await websocket.close(code=1013, reason="Connection capacity reached")
        return
    await websocket.accept()

    try:
        raw_message = await asyncio.wait_for(websocket.receive(), timeout=settings.websocket_auth_timeout_seconds)
        if raw_message.get("type") != "websocket.receive":
            await websocket.close(code=1008, reason="Authentication required")
            return
        raw_data = raw_message.get("text")
        if not isinstance(raw_data, str) or len(raw_data.encode("utf-8")) > settings.websocket_max_auth_message_bytes:
            await websocket.close(code=1009, reason="Authentication message too large")
            return
        try:
            message = json.loads(raw_data)
        except (TypeError, json.JSONDecodeError):
            message = None
        if not isinstance(message, dict) or message.get("type") != "auth" or not isinstance(message.get("token"), str):
            await websocket.close(code=1008, reason="Authentication required")
            return

        user = await manager.connect(websocket, message["token"])
        if not user:
            await websocket.close(code=1008, reason="Invalid authentication credentials")
            return

        await websocket.send_json({"type": "auth_ok"})
        while True:
            await websocket.receive_text()
    except (WebSocketDisconnect, asyncio.TimeoutError):
        pass
    finally:
        manager.disconnect(websocket)

app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(tickets.router, prefix="/api/tickets", tags=["tickets"])
app.include_router(admin.router, prefix="/api/admin", tags=["admin"])

@app.get("/api/health")
def health(): return {"status": "ok"}
