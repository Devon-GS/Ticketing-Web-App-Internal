from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.exc import IntegrityError
from sqlalchemy import select
from sqlalchemy.orm import Session
from ..auth import client_ip, create_token, current_user, hash_password, login_rate_limiter, login_rate_limit_error, normalize_token_version, normalize_username, verify_password
from ..db import get_db
from ..models import User
from ..schemas import LoginIn, PasswordChange, Token, UserOut, UsernameAvailability, UsernameUpdate

router = APIRouter()
@router.post("/login", response_model=Token)
def login(data: LoginIn, request: Request, db: Session = Depends(get_db)):
    ip_key = f"ip:{client_ip(request)}"
    username_key = f"username:{normalize_username(data.username)}"
    if login_rate_limiter.is_limited(username_key):
        raise login_rate_limit_error()
    user = db.scalar(select(User).where(User.username == normalize_username(data.username)))
    if not user or not user.is_active or not verify_password(data.password, user.password_hash):
        login_rate_limiter.record_failure(username_key)
        login_rate_limiter.record_failure(ip_key)
        raise HTTPException(401, "Invalid username or password")
    login_rate_limiter.clear(username_key)
    login_rate_limiter.clear(ip_key)
    user.token_version = normalize_token_version(user.token_version)
    db.commit()
    db.refresh(user)
    return {"access_token": create_token(user.id, user.token_version), "user": user}
@router.get("/me", response_model=UserOut)
def me(user: User = Depends(current_user)): return user

@router.get("/username-availability", response_model=UsernameAvailability)
def username_availability(username: str = Query(min_length=3, max_length=80), user: User = Depends(current_user), db: Session = Depends(get_db)):
    existing = db.scalar(select(User).where(User.username == normalize_username(username)))
    return {"available": existing is None or existing.id == user.id}

@router.patch("/me", response_model=UserOut)
def update_me(data: UsernameUpdate, user: User = Depends(current_user), db: Session = Depends(get_db)):
    normalized = normalize_username(data.username)
    existing = db.scalar(select(User).where(User.username == normalized, User.id != user.id))
    if existing:
        raise HTTPException(409, "Username already exists")
    user.username = normalized
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Username already exists")
    db.refresh(user)
    return user

@router.post("/me/password")
async def change_password(data: PasswordChange, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if not verify_password(data.current_password, user.password_hash):
        raise HTTPException(400, "Current password is incorrect")
    if data.new_password != data.confirm_password:
        raise HTTPException(400, "New password and confirmation do not match")
    if data.current_password == data.new_password:
        raise HTTPException(400, "New password must be different from your current password")
    user.password_hash = hash_password(data.new_password)
    user.token_version += 1
    db.commit()
    from ..realtime import manager
    await manager.close_user_connections(user.id)
    return {"message": "Password updated successfully"}
