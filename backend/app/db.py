from collections.abc import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://ticketing:ticketing@db:5432/ticketing"
    jwt_secret: str = ""
    jwt_expire_minutes: int = 30
    environment: str = "production"
    admin_username: str = ""
    admin_password: str = ""
    allowed_origins: str = ""
    allowed_ws_origins: str = ""
    trusted_proxy_ips: str = ""
    websocket_auth_timeout_seconds: int = 10
    websocket_max_auth_message_bytes: int = 4096
    websocket_max_connections: int = 100
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()
engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

class Base(DeclarativeBase):
    pass

def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
