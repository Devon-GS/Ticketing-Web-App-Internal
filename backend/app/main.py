from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select
from .db import Base, SessionLocal, engine, settings
from .models import Label, User
from .auth import hash_password
from .routers import auth, tickets, admin

@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        if not db.scalar(select(User).where(User.email == settings.admin_email)):
            db.add(User(email=settings.admin_email, full_name="System Administrator", password_hash=hash_password(settings.admin_password), role="admin"))
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
