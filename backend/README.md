# Backend — fastapi-admin

[中文文档](./README_zh.md) · [Root README](../README.md)

Async FastAPI service for the RBAC admin console: authentication, users/roles/permissions APIs, audit logs, and dashboard stats.

## Stack

- Python **3.14**, FastAPI, Uvicorn
- SQLAlchemy **2** (async) + **PostgreSQL** (psycopg) + Alembic
- JWT access tokens + persistent refresh session families
- Argon2id (pwdlib) with bcrypt verify/migrate for legacy hashes
- Tooling: **uv**, ruff, mypy, pytest

## Project layout

```text
backend/
├── app/
│   ├── api/v1/          # Route handlers
│   ├── core/            # Config, DB, security, deps
│   ├── crud/            # Data access
│   ├── models/          # SQLAlchemy models
│   ├── schemas/         # Pydantic models
│   ├── services/        # Auth sessions, cleanup, rate limits
│   └── main.py          # ASGI app factory
├── alembic/             # Migrations
├── tests/
├── init_db.py           # Superuser + permission seed
├── main.py              # Windows-safe uvicorn entry
└── .env.example
```

## Setup

```bash
cd backend
cp .env.example .env
uv sync
```

Minimum `.env` for local development:

```ini
DATABASE_URL=postgresql+psycopg://USER:PASSWORD@localhost:5432/fastapi_admin
ENVIRONMENT=development
BACKEND_CORS_ORIGINS=http://localhost:5173,http://localhost:3000
ALLOWED_HOSTS=localhost,127.0.0.1
```

First-time bootstrap (optional but recommended):

```ini
INIT_SUPERUSER_USERNAME=admin
INIT_SUPERUSER_EMAIL=admin@example.com
INIT_SUPERUSER_PASSWORD=your-strong-password
```

```bash
uv run alembic upgrade head
uv run python init_db.py
```

`init_db.py` idempotently seeds **16** system permissions aligned with `require_permission` / the frontend `PERMISSIONS` constants. It does **not** create roles or assignments. Superuser creation is skipped if one already exists.

## Run

Prefer the project entry (SelectorEventLoop on Windows for async psycopg):

```bash
uv run python main.py
```

- API base: `http://localhost:8000/api/v1`
- OpenAPI: `http://localhost:8000/docs`

Useful flags in `.env`:

| Variable | Purpose |
| --- | --- |
| `LOG_LEVEL` | Root log level (`info` default) |
| `SQL_ECHO` | Set `true` only while debugging SQL |
| `REGISTRATION_ENABLED` | Public self-registration (off by default) |

## Permission codes (seeded)

| Module | Codes |
| --- | --- |
| Users | `user:read` `user:create` `user:update` `user:delete` `user:assign` `user:reset_password` |
| Roles | `role:read` `role:create` `role:update` `role:delete` `role:assign` |
| Permissions | `permission:read` `permission:create` `permission:update` `permission:delete` |
| Audit | `audit:read` |

## Quality

```bash
uv run ruff check .
uv run mypy app
uv run pytest
```

## More

Production hardening, DB roles, and proxy settings: [docs/DEPLOYMENT.md](../docs/DEPLOYMENT.md).
