from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from ..auth import admin_user, hash_password, normalize_token_version, normalize_username
from ..db import get_db
from ..models import Label, User
from ..realtime import manager
from ..schemas import LabelIn, LabelOut, PasswordReset, UserCreate, UserOut, UserUpdate

router = APIRouter()
@router.get("/users", response_model=list[UserOut])
def users(db: Session = Depends(get_db), _: User = Depends(admin_user)): return db.scalars(select(User).order_by(User.created_at.desc())).all()
@router.post("/users", response_model=UserOut)
def create_user(data: UserCreate, db: Session = Depends(get_db), _: User = Depends(admin_user)):
    username = normalize_username(data.username)
    if db.scalar(select(User).where(User.username == username)): raise HTTPException(409, "Username already exists")
    user = User(username=username, full_name=data.full_name, password_hash=hash_password(data.password), role=data.role); db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Username already exists")
    db.refresh(user); return user
@router.post("/users/{user_id}/reset-password")
async def reset_password(user_id: int, data: PasswordReset, db: Session = Depends(get_db), admin: User = Depends(admin_user)):
    user = db.get(User, user_id)
    if not user: raise HTTPException(404, "User not found")
    if user.id == admin.id: raise HTTPException(400, "Administrators must use the normal change-password flow to reset their own password")
    if data.temporary_password != data.confirm_password: raise HTTPException(400, "Temporary password and confirmation do not match")
    user.password_hash = hash_password(data.temporary_password)
    user.token_version = normalize_token_version(user.token_version) + 1
    db.commit()
    await manager.close_user_connections(user.id)
    return {"message": "Password reset successfully"}
@router.patch("/users/{user_id}", response_model=UserOut)
async def update_user(user_id: int, data: UserUpdate, db: Session = Depends(get_db), admin: User = Depends(admin_user)):
    user = db.get(User, user_id)
    if not user: raise HTTPException(404, "User not found")
    changes = data.model_dump(exclude_unset=True)
    removing_admin = user.role.value == "admin" and (changes.get("role") is not None and changes["role"].value != "admin")
    disabling_admin = user.role.value == "admin" and changes.get("is_active") is False
    if user.id == admin.id and (removing_admin or disabling_admin):
        raise HTTPException(400, "You cannot disable or demote your own administrator account")
    if removing_admin or disabling_admin:
        active_admins = db.scalar(select(func.count(User.id)).where(User.role == user.role, User.is_active.is_(True))) or 0
        if active_admins <= 1:
            raise HTTPException(400, "The last active administrator cannot be disabled or demoted")
    session_changed = "role" in changes or "is_active" in changes
    for key, value in changes.items(): setattr(user, key, value)
    if session_changed:
        user.token_version = normalize_token_version(user.token_version) + 1
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "User update conflicts with existing data")
    if session_changed:
        await manager.close_user_connections(user.id)
    return user
@router.get("/labels", response_model=list[LabelOut])
def labels(db: Session = Depends(get_db), _: User = Depends(admin_user)): return db.scalars(select(Label).order_by(Label.name)).all()
@router.post("/labels", response_model=LabelOut)
def create_label(data: LabelIn, db: Session = Depends(get_db), _: User = Depends(admin_user)):
    label = Label(**data.model_dump()); db.add(label)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Label already exists")
    db.refresh(label); return label
@router.delete("/labels/{label_id}")
def delete_label(label_id: int, db: Session = Depends(get_db), _: User = Depends(admin_user)):
    label = db.get(Label, label_id)
    if not label: raise HTTPException(404, "Label not found")
    db.delete(label); db.commit(); return {"ok": True}
