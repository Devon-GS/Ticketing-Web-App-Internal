# Ticketing Web App

Docker-ready ticketing application built with React, TypeScript, Vite, FastAPI and PostgreSQL.

## Quick start

1. Copy `.env.example` to `.env` and change `JWT_SECRET`, `ADMIN_PASSWORD`, and database credentials.
2. Run `docker compose up --build`.
3. Open http://localhost:5173.

The API creates the first admin user from `ADMIN_USERNAME` and `ADMIN_PASSWORD` on startup.

Default local credentials are `admin` / `ChangeMe123!` unless overridden in `.env`. Never use these values in production.

## Services

- Frontend: http://localhost:5173
- API: http://localhost:8000
- API docs: http://localhost:8000/docs
- PostgreSQL: localhost:5432

The API runs database initialization on startup for this initial version. The schema is defined in `backend/app/models.py`; Alembic can be added when the schema begins to evolve across environments.

## Production VPS deployment

Run the frontend and backend on a VPS behind a reverse proxy such as Nginx or Caddy. Keep the Docker-published database and API ports bound to `127.0.0.1`; expose only the reverse proxy publicly.

1. Provision a Neon PostgreSQL database and set `DATABASE_URL` to the Neon connection string, including its TLS parameters (for example, `postgresql+psycopg://USER:PASSWORD@HOST/DB?sslmode=require`). Do not use the local Docker database credentials in production.
2. Set `ENVIRONMENT=production`, a long random `JWT_SECRET`, a non-default `ADMIN_USERNAME`, and a strong `ADMIN_PASSWORD` in the deployment secret store or `.env` on the VPS. Production startup rejects known default values.
3. Set `API_PORT_BINDING` and `DB_PORT_BINDING` only if the local loopback ports need to change. The default bindings are `127.0.0.1:8000` and `127.0.0.1:5432`.
4. Configure the reverse proxy to serve the frontend on your domain and proxy `/api/` and `/api/ws` to the local frontend container. Preserve WebSocket upgrade headers for `/api/ws`.
5. Obtain and renew a Let's Encrypt certificate with Certbot or the reverse proxy's ACME support. Terminate TLS at the proxy and forward requests internally to the local HTTP containers. Do not add HTTPS redirects to the local Docker configuration.
6. Start the stack with `docker compose up -d --build` and verify the health endpoint through the proxy. Keep `/docs` and `/redoc` disabled in production.

The frontend CSP permits `self`, `ws:`, and `wss:` connections so realtime ticket refreshes continue to work.
