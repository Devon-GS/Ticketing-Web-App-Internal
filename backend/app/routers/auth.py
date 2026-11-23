from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select
from sqlalchemy.orm import Session
from ..auth import create_token, current_user, hash_password, login_rate_limiter, login_rate_limit_error, verify_password
from ..db import get_db
from ..models import User
from ..schemas import LoginIn, PasswordChange, Token, UserOut, UsernameAvailability, UsernameUpdate

router = APIRouter()
@router.post("/login", response_model=Token)
def login(data: LoginIn, request: Request, db: Session = Depends(get_db)):
    client_host = request.client.host if request.client else "unknown"
    rate_limit_keys = [f"ip:{client_host}", f"username:{data.username.casefold()}"]
    if any(login_rate_limiter.is_limited(key) for key in rate_limit_keys):
        raise login_rate_limit_error()
    user = db.scalar(select(User).where(User.username == data.username))
    if not user or not user.is_active or not verify_password(data.password, user.password_hash):
        for key in rate_limit_keys:
            login_rate_limiter.record_failure(key)
        raise HTTPException(401, "Invalid username or password")
    login_rate_limiter.clear(rate_limit_keys[1])
    return {"access_token": create_token(user.id, user.token_version), "user": user}
@router.get("/me", response_model=UserOut)
def me(user: User = Depends(current_user)): return user

@router.get("/username-availability", response_model=UsernameAvailability)
def username_availability(username: str = Query(min_length=3, max_length=80), user: User = Depends(current_user), db: Session = Depends(get_db)):
    existing = db.scalar(select(User).where(User.username == username))
    return {"available": existing is None or existing.id == user.id}

@router.patch("/me", response_model=UserOut)
def update_me(data: UsernameUpdate, user: User = Depends(current_user), db: Session = Depends(get_db)):
    existing = db.scalar(select(User).where(User.username == data.username, User.id != user.id))
    if existing:
        raise HTTPException(409, "Username already exists")
    user.username = data.username
    db.commit()
    db.refresh(user)
    return user

@router.post("/me/password")
def change_password(data: PasswordChange, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if not verify_password(data.current_password, user.password_hash):
        raise HTTPException(400, "Current password is incorrect")
    if data.new_password != data.confirm_password:
        raise HTTPException(400, "New password and confirmation do not match")
    if data.current_password == data.new_password:
        raise HTTPException(400, "New password must be different from your current password")
    user.password_hash = hash_password(data.new_password)
    user.token_version += 1
    db.commit()
    return {"message": "Password updated successfully"}
