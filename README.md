# Quik Inspect API (FastAPI)

PostgreSQL (Neon) + JWT + **asyncpg**. Same REST routes as the legacy Node `server/` app so the Expo client can switch API base URL only.

## Setup

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env        # fill DATABASE_URL, JWT_SECRET
```

## Local run

```bash
source .venv/bin/activate
uvicorn app.main:app --reload --host 0.0.0.0 --port 3000
```

Point `EXPO_PUBLIC_API_URL` at `http://<LAN-IP>:3000` (same as the old server).

## Migrations

```bash
export DATABASE_URL=postgresql://...?sslmode=require
python scripts/migrate.py
```

SQL files live in `migrations/` (same schema as `server/migrations/`).

## Vercel

| Setting | Value |
|--------|--------|
| **Root directory** | `backend` |
| **Framework** | **FastAPI** (or follow [Vercel FastAPI](https://vercel.com/docs/frameworks/backend/fastapi) + `pyproject.toml` `[tool.vercel]` entrypoint `app.main:app`) |
| **Output directory** | *(empty)* |

Environment: `DATABASE_URL`, `JWT_SECRET`, optional `JWT_EXPIRES_IN`, `CORS_ORIGIN`.

Do **not** set **Output directory** to `public` unless you know you need static files only — it can prevent the API from running.

## Layout

- `app/main.py` — FastAPI `app`, CORS, router includes  
- `app/routers/` — `health`, `auth`, `facilities`, `inspections`, `checklists`  
- `app/db.py` — asyncpg pool  
- `migrations/` — Postgres DDL  
