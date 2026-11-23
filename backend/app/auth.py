from datetime import datetime, timedelta, timezone
from collections import defaultdict, deque
from threading import Lock
from time import monotonic

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session
from .db import get_db, settings
from .models import Role, User

pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2 = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

def hash_password(value: str) -> str: return pwd.hash(value)
def verify_password(value: str, hashed: str) -> bool: return pwd.verify(value, hashed)
def create_token(user_id: int, token_version: int) -> str:
    exp = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes)
    return jwt.encode({"sub": str(user_id), "ver": token_version, "exp": exp}, settings.jwt_secret, algorithm="HS256")

def decode_token(token: str) -> tuple[int, int] | None:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
        return int(payload.get("sub", "")), int(payload.get("ver", "-1"))
    except (JWTError, ValueError, TypeError):
        return None

def current_user(token: str = Depends(oauth2), db: Session = Depends(get_db)) -> User:
    error = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid authentication credentials")
    decoded = decode_token(token)
    if decoded is None: raise error
    user_id, token_version = decoded
    user = db.get(User, user_id)
    if not user or not user.is_active or user.token_version != token_version: raise error
    return user

def admin_user(user: User = Depends(current_user)) -> User:
    if user.role != Role.admin: raise HTTPException(status_code=403, detail="Administrator access required")
    return user

class LoginRateLimiter:
    def __init__(self, max_failures: int = 5, window_seconds: int = 60) -> None:
        self.max_failures = max_failures
        self.window_seconds = window_seconds
        self.failures: dict[str, deque[float]] = defaultdict(deque)
        self.lock = Lock()

    def is_limited(self, key: str) -> bool:
        now = monotonic()
        with self.lock:
            attempts = self.failures[key]
            while attempts and now - attempts[0] >= self.window_seconds:
                attempts.popleft()
            return len(attempts) >= self.max_failures

    def record_failure(self, key: str) -> None:
        now = monotonic()
        with self.lock:
            attempts = self.failures[key]
            while attempts and now - attempts[0] >= self.window_seconds:
                attempts.popleft()
            attempts.append(now)

    def clear(self, key: str) -> None:
        with self.lock:
            self.failures.pop(key, None)

login_rate_limiter = LoginRateLimiter()

def login_rate_limit_error() -> HTTPException:
    return HTTPException(status_code=429, detail="Too many failed login attempts. Try again later.", headers={"Retry-After": "60"})
