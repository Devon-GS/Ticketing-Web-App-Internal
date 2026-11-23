from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import inspect, select, text
from .db import Base, SessionLocal, engine, settings
from .models import Label, User
from .auth import hash_password, verify_password
from .routers import auth, tickets, admin
from .realtime import manager

KNOWN_DEFAULTS = {
    "development-secret", "replace-this-with-a-long-random-secret",
    "replace-this-in-production", "ChangeMe123!", "Admin123!", "admin",
}

def validate_startup_settings() -> None:
    if settings.environment.casefold() != "production":
        return
    required = {
        "JWT_SECRET": settings.jwt_secret,
        "ADMIN_USERNAME": settings.admin_username,
        "ADMIN_PASSWORD": settings.admin_password,
    }
    known_defaults = {value.casefold() for value in KNOWN_DEFAULTS}
    if any(not value.strip() or value.casefold() in known_defaults for value in required.values()):
        raise RuntimeError("Production requires non-default JWT_SECRET, ADMIN_USERNAME, and ADMIN_PASSWORD")

def migrate_legacy_users():
    if not inspect(engine).has_table("users"):
        return
    with engine.begin() as connection:
        columns = {column["name"] for column in inspect(engine).get_columns("users")}
        if "token_version" not in columns:
            connection.execute(text("ALTER TABLE users ADD COLUMN token_version INTEGER NOT NULL DEFAULT 0"))
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
        admin = db.scalar(select(User).where(User.username == settings.admin_username))
        if not admin:
            db.add(User(username=settings.admin_username, full_name="System Administrator", password_hash=hash_password(settings.admin_password), role="admin"))
        else:
            # Keep the configured bootstrap admin usable when credentials change in .env.
            if not verify_password(settings.admin_password, admin.password_hash):
                admin.password_hash = hash_password(settings.admin_password)
                admin.token_version += 1
            admin.is_active = True
            admin.role = "admin"
        if not db.scalar(select(Label)):
            db.add_all([Label(name="urgent", color="#dc2626"), Label(name="normal", color="#2563eb"), Label(name="overdue account", color="#d97706")])
        db.commit()
    yield

docs_url = None if settings.environment.casefold() == "production" else "/docs"
redoc_url = None if settings.environment.casefold() == "production" else "/redoc"
app = FastAPI(title="Ticketing API", version="1.0.0", lifespan=lifespan, docs_url=docs_url, redoc_url=redoc_url)
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

@app.middleware("http")
async def security_headers(request, call_next):
    response = await call_next(request)
    response.headers["Content-Security-Policy"] = "default-src 'self'; base-uri 'none'; object-src 'none'; frame-ancestors 'none'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self' ws: wss:; font-src 'self'; form-action 'self'"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response


@app.websocket("/api/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()

    try:
        message = await websocket.receive_json()
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
    except WebSocketDisconnect:
        pass
    finally:
        manager.disconnect(websocket)

app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(tickets.router, prefix="/api/tickets", tags=["tickets"])
app.include_router(admin.router, prefix="/api/admin", tags=["admin"])

@app.get("/api/health")
def health(): return {"status": "ok"}
