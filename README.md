# Ticketing Web App

Docker-ready ticketing application built with React, TypeScript, Vite, FastAPI and PostgreSQL.

## Quick start

1. Copy `.env.example` to `.env` and set every production secret and origin value. `.env` is ignored by Git.
2. Run `docker compose up --build`.
3. Open http://localhost:5173.

The API creates the first admin user from `ADMIN_USERNAME` and `ADMIN_PASSWORD` on startup. Production startup fails if required secrets or `ALLOWED_ORIGINS` are missing or weak. There is no public user-registration endpoint; users are created by an authenticated administrator.

## Services

- Frontend: http://localhost:5173
- API: http://localhost:8000
- API docs: http://localhost:8000/docs
- PostgreSQL: localhost:5432

The API runs database initialization on startup for this initial version. The schema is defined in `backend/app/models.py`; Alembic can be added when the schema begins to evolve across environments.

## Production VPS deployment

Run the frontend and backend on a VPS behind a reverse proxy such as Nginx or Caddy. Keep the Docker-published database and API ports bound to `127.0.0.1`; expose only the reverse proxy publicly.

1. Provision a Neon PostgreSQL database and set `DATABASE_URL` to the Neon connection string with TLS enabled (for example, `postgresql+psycopg://USER:PASSWORD@HOST/DB?sslmode=require`). Do not use local Docker database credentials in production.
2. Set `ENVIRONMENT=production`, a long random `JWT_SECRET`, a unique `ADMIN_USERNAME`, a strong `ADMIN_PASSWORD`, and the public HTTPS origin in `ALLOWED_ORIGINS` and `ALLOWED_WS_ORIGINS`. Production startup rejects missing or known default values.
3. Set `API_PORT_BINDING` and `DB_PORT_BINDING` only if the local loopback ports need to change. The default bindings are `127.0.0.1:8000` and `127.0.0.1:5432`.
4. Configure the reverse proxy to serve the frontend on your HTTPS domain and proxy `/api/` and `/api/ws` to the local frontend container. Preserve WebSocket upgrade headers for `/api/ws`; same-origin browser connections use `wss://` automatically. Set `TRUSTED_PROXY_IPS` only to the proxy/container addresses whose forwarded client-IP headers are trusted.
5. Obtain and renew a Let's Encrypt certificate with Certbot or the reverse proxy's ACME support. Terminate TLS at the proxy and forward requests internally to the local HTTP containers. Do not add HTTPS redirects to the local Docker configuration.
6. Start the stack with `docker compose up -d --build` and verify the health endpoint through the proxy. Keep `/docs` and `/redoc` disabled in production.

The frontend nginx configuration emits the single frontend CSP and HSTS policy. Its CSP restricts connections to the same origin, which permits same-origin HTTPS/WebSocket traffic without allowing arbitrary `ws:` or `wss:` destinations. Deploy it behind HTTPS before enabling public access; HSTS is emitted by nginx for the production frontend.

Required production variables are documented in `.env.example`: `ENVIRONMENT`, `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `DATABASE_URL`, `JWT_SECRET`, `ADMIN_USERNAME`, `ADMIN_PASSWORD`, `ALLOWED_ORIGINS`, and `ALLOWED_WS_ORIGINS`. Optional hardening variables are `JWT_EXPIRE_MINUTES`, `TRUSTED_PROXY_IPS`, `WEBSOCKET_AUTH_TIMEOUT_SECONDS`, `WEBSOCKET_MAX_AUTH_MESSAGE_BYTES`, and `WEBSOCKET_MAX_CONNECTIONS`.
