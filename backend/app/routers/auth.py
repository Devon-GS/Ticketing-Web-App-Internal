from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session
from ..auth import create_token, hash_password, verify_password, current_user
from ..db import get_db
from ..models import User
from ..schemas import LoginIn, PasswordChange, Token, UserOut, UsernameAvailability, UsernameUpdate

router = APIRouter()
@router.post("/login", response_model=Token)
def login(data: LoginIn, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.username == data.username))
    if not user or not user.is_active or not verify_password(data.password, user.password_hash): raise HTTPException(401, "Invalid username or password")
    return {"access_token": create_token(user.id), "user": user}
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
    db.commit()
    return {"message": "Password updated successfully"}
