from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from ..auth import create_token, verify_password, current_user
from ..db import get_db
from ..models import User
from ..schemas import LoginIn, Token, UserOut

router = APIRouter()
@router.post("/login", response_model=Token)
def login(data: LoginIn, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == data.email))
    if not user or not user.is_active or not verify_password(data.password, user.password_hash): raise HTTPException(401, "Invalid email or password")
    return {"access_token": create_token(user.id), "user": user}
@router.get("/me", response_model=UserOut)
def me(user: User = Depends(current_user)): return user
