from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field
from .models import Role, Status

class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int; username: str; full_name: str; role: Role; is_active: bool

class LoginIn(BaseModel):
    username: str = Field(min_length=3, max_length=80, pattern=r"^[A-Za-z0-9._-]+$"); password: str = Field(min_length=1, max_length=128)

class Token(BaseModel): access_token: str; token_type: str = "bearer"; user: UserOut

class UsernameUpdate(BaseModel):
    username: str = Field(min_length=3, max_length=80, pattern=r"^[A-Za-z0-9._-]+$")

class UsernameAvailability(BaseModel):
    available: bool

class PasswordChange(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)
    confirm_password: str = Field(min_length=8, max_length=128)

class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=80, pattern=r"^[A-Za-z0-9._-]+$"); full_name: str = Field(min_length=2, max_length=120); password: str = Field(min_length=8, max_length=128); role: Role = Role.user

class UserUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=120); role: Role | None = None; is_active: bool | None = None

class LabelIn(BaseModel): name: str = Field(min_length=1, max_length=60); color: str = Field(default="#2563eb", pattern=r"^#[0-9A-Fa-f]{6}$")
class LabelOut(LabelIn): model_config = ConfigDict(from_attributes=True); id: int

class CommentIn(BaseModel): body: str = Field(min_length=1, max_length=5000)
class CommentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int; body: str; author: UserOut; created_at: datetime

class TicketIn(BaseModel): title: str = Field(min_length=1, max_length=180); description: str = Field(default="", max_length=10000); label_ids: list[int] = Field(default_factory=list, max_length=20)
class TicketOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int; title: str; description: str; status: Status; created_at: datetime; closed_at: datetime | None
    created_by: UserOut; assigned_to: UserOut | None; closed_by: UserOut | None; labels: list[LabelOut]; comments: list[CommentOut]
