from datetime import datetime
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from .models import Role, Status

class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int; email: EmailStr; full_name: str; role: Role; is_active: bool

class LoginIn(BaseModel):
    email: EmailStr; password: str

class Token(BaseModel): access_token: str; token_type: str = "bearer"; user: UserOut

class UserCreate(BaseModel):
    email: EmailStr; full_name: str = Field(min_length=2, max_length=120); password: str = Field(min_length=8); role: Role = Role.user

class UserUpdate(BaseModel):
    full_name: str | None = None; role: Role | None = None; is_active: bool | None = None

class LabelIn(BaseModel): name: str = Field(min_length=1, max_length=60); color: str = "#2563eb"
class LabelOut(LabelIn): model_config = ConfigDict(from_attributes=True); id: int

class CommentIn(BaseModel): body: str = Field(min_length=1, max_length=5000)
class CommentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int; body: str; author: UserOut; created_at: datetime

class TicketIn(BaseModel): title: str = Field(min_length=1, max_length=180); description: str = ""; label_ids: list[int] = []
class TicketOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int; title: str; description: str; status: Status; created_at: datetime; closed_at: datetime | None
    created_by: UserOut; assigned_to: UserOut | None; closed_by: UserOut | None; labels: list[LabelOut]; comments: list[CommentOut]
