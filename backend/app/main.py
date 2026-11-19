from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import inspect, select, text
from .db import Base, SessionLocal, engine, settings
from .models import Label, User
from .auth import hash_password, verify_password
from .routers import auth, tickets, admin

def migrate_legacy_users():
    if not inspect(engine).has_table("users"):
        return
    with engine.begin() as connection:
        columns = {column["name"] for column in inspect(engine).get_columns("users")}
        if "username" not in columns and "email" in columns:
            connection.execute(text("ALTER TABLE users ADD COLUMN username VARCHAR(80)"))
            connection.execute(text("UPDATE users SET username = split_part(email, '@', 1) WHERE username IS NULL"))
            connection.execute(text("ALTER TABLE users ALTER COLUMN username SET NOT NULL"))
            connection.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ix_users_username ON users (username)"))

@asynccontextmanager
async def lifespan(app: FastAPI):
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
            admin.is_active = True
            admin.role = "admin"
        if not db.scalar(select(Label)):
            db.add_all([Label(name="urgent", color="#dc2626"), Label(name="normal", color="#2563eb"), Label(name="overdue account", color="#d97706")])
        db.commit()
    yield

app = FastAPI(title="Ticketing API", version="1.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(tickets.router, prefix="/api/tickets", tags=["tickets"])
app.include_router(admin.router, prefix="/api/admin", tags=["admin"])

@app.get("/api/health")
def health(): return {"status": "ok"}
