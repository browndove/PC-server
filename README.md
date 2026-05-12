# Quik Inspect API (FastAPI)

This **`backend/`** directory is the **FastAPI** service (Python). The legacy **`server/`** tree in the monorepo is **Node/Express** — different stack. The Expo app should point `EXPO_PUBLIC_API_URL` at wherever **this** API is hosted.

Stack: PostgreSQL + **asyncpg** + JWT. Entry module: **`app.main:app`** (`app/main.py`).

## Setup

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e .            # or: pip install -r requirements.txt
cp .env.example .env        # optional; set DATABASE_URL + JWT_SECRET as needed
```

## Run FastAPI locally

**Option A — script (native Postgres on port 5432, no Docker):** install Postgres (e.g. `brew install postgresql@16`, `brew services start postgresql@16`), then `createdb quikinspect`, then:

```bash
./scripts/run_local.sh
```

**Option B — uvicorn yourself:** run from this **`backend/`** directory (not `server/`). If your Neon URL contains **`&`**, wrap it in **single quotes** in the shell or the string is cut at `&`.

```bash
source .venv/bin/activate
export DATABASE_URL='postgresql://YOUR_USER@127.0.0.1:5432/quikinspect'
export JWT_SECRET='at-least-32-chars-for-local-dev'
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Open **`http://127.0.0.1:8000/health`**. For a phone on the same Wi‑Fi, use your LAN IP and the same port in `EXPO_PUBLIC_API_URL`.

Optional Docker DB: `docker compose up -d` in this folder, then set  
`DATABASE_URL=postgresql://postgres:postgres@127.0.0.1:54322/quikinspect`.

## Migrations

- **First boot / empty DB:** the app runs SQL in **`migrations/*.sql`** once (when `public.inspectors` does not exist yet).
- **Later changes:** run `python scripts/migrate.py` with `DATABASE_URL` set, or set **`FORCE_RUN_ALL_MIGRATIONS=1`** for one deploy to re-apply every file.
- **Disable startup DDL:** `RUN_MIGRATIONS_ON_STARTUP=0`.

## Railway / Railpack

**`railpack.json`** / **`Procfile`** use **`uvicorn main:app`** from the **deploy repo root**. Root **`main.py`** re-exports **`from app.main import app`** so `main:app` resolves. Set **`DATABASE_URL`**, **`JWT_SECRET`**, and **`PORT`** (Railway injects `PORT`).

## Vercel

| Setting | Value |
|--------|--------|
| **Root directory** | `backend` |
| **Framework** | **FastAPI** (or `pyproject.toml` `[tool.vercel]` entrypoint `app.main:app`) |
| **Output directory** | *(empty)* |

Environment: `DATABASE_URL`, `JWT_SECRET`, optional `JWT_EXPIRES_IN`, `CORS_ORIGIN`.

## Layout

- `app/main.py` — FastAPI `app`, CORS, router includes  
- `app/routers/` — `health`, `auth`, `facilities`, `inspections`, `checklists`  
- `app/db.py` — asyncpg pool  
- `migrations/` — Postgres DDL  
