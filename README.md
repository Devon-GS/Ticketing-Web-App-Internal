# Ticketing Web App

Docker-ready ticketing application built with React, TypeScript, Vite, FastAPI and PostgreSQL.

## Quick start

1. Copy `.env.example` to `.env` and change `JWT_SECRET`.
2. Run `docker compose up --build`.
3. Open http://localhost:5173.

The API creates the first admin user from `ADMIN_USERNAME` and `ADMIN_PASSWORD` on startup.

Default local credentials are `admin` / `ChangeMe123!` unless overridden in `.env`.

## Services

- Frontend: http://localhost:5173
- API: http://localhost:8000
- API docs: http://localhost:8000/docs
- PostgreSQL: localhost:5432

The API runs database initialization on startup for this initial version. The schema is defined in `backend/app/models.py`; Alembic can be added when the schema begins to evolve across environments.
